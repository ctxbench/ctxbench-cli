from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelInput
from copa.benchmark.experiment_loader import load_experiment
from copa.benchmark.models import (
    EvaluationResult,
    EvaluationBatchSummary,
    EvaluationItemResult,
    EvaluationJudgeInfo,
    EvaluationModelConfig,
    EvaluationRunResult,
    EvaluationRunSummary,
    EvaluationTrace,
    Experiment,
    RunResult,
    RunTrace,
)
from copa.benchmark.paths import resolve_eval_jsonl_path, resolve_eval_output_dir
from copa.benchmark.results import write_evaluation_files, write_evaluation_jsonl
from copa.benchmark.runspec_generator import generate_runspecs
from copa.dataset.provider import DatasetProvider
from copa.dataset.questions import EvaluationDimension, EvaluationRubricCriterion, Question

ABSTENTION_PATTERNS = (
    "not enough information",
    "insufficient information",
    "cannot determine",
    "can't determine",
    "cannot be determined",
    "not provided",
    "not available",
    "unknown",
)

EVALUATION_SYSTEM_INSTRUCTION = (
    "You are evaluating benchmark outputs, not answering the benchmark task.\n"
    "Judge only from the provided prompt and structured evaluation context.\n"
    "Do not answer as if you were the original assistant.\n"
    "Do not use external knowledge.\n"
    "Follow the requested output schema exactly.\n"
)


def _normalize(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def _strip_punctuation(value: str) -> str:
    return re.sub(r"[^\w\s]", "", value)


def _slug_tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 2]


def _extract_number(answer: str) -> int | float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", answer.replace(",", ""))
    if match is None:
        return None
    raw = match.group(0)
    return float(raw) if "." in raw else int(raw)


def _extract_year(answer: str) -> int | None:
    match = re.search(r"\b(19|20)\d{2}\b", answer)
    return int(match.group(0)) if match else None


def _normalize_expected_exact(expected: Any, answer_type: str | None) -> Any:
    if answer_type == "number":
        return _extract_number(str(expected))
    if answer_type == "year":
        return _extract_year(str(expected))
    return expected


def _normalization_rules(
    question: Question,
    normalization_hints: list[str] | None,
) -> list[str]:
    evaluation = question.evaluation
    dimensions = [] if evaluation is None else list(evaluation.dimensions)
    exact_dimension = next((item for item in dimensions if item.id == "exact-match"), None)
    if exact_dimension is not None and exact_dimension.normalization:
        return exact_dimension.normalization
    if normalization_hints:
        return list(normalization_hints)
    answer_type = evaluation.answerType if evaluation else None
    if answer_type == "number":
        return ["trim", "lowercase", "extract-number"]
    if answer_type == "year":
        return ["trim", "extract-year"]
    return ["trim", "lowercase", "collapse-whitespace"]


def _apply_normalization(value: Any, rules: list[str], answer_type: str | None) -> Any:
    if value is None:
        return None
    normalized = str(value)
    for rule in rules:
        if rule == "trim":
            normalized = normalized.strip()
        elif rule == "lowercase":
            normalized = normalized.lower()
        elif rule == "collapse-whitespace":
            normalized = " ".join(normalized.split())
        elif rule == "strip-punctuation":
            normalized = _strip_punctuation(normalized)
    if "extract-number" in rules or answer_type == "number":
        return _extract_number(normalized)
    if "extract-year" in rules or answer_type == "year":
        return _extract_year(normalized)
    return normalized


def _default_scale_label(scale: list[str], score: float) -> str | None:
    if not scale:
        return None
    if len(scale) == 1:
        return scale[0]
    index = round(score * (len(scale) - 1))
    index = max(0, min(index, len(scale) - 1))
    return scale[index]


def _scale_label_score(scale: list[str], label: str | None) -> float:
    if not scale or label is None:
        return 0.0
    try:
        index = scale.index(label)
    except ValueError:
        return 0.0
    if len(scale) == 1:
        return 1.0
    return round(index / (len(scale) - 1), 4)


def _score_dimension_results(
    dimension_results: dict[str, dict[str, Any]],
    dimensions: list[EvaluationDimension],
) -> tuple[float | None, float, float]:
    if not dimensions:
        return None, 0.0, 0.0
    weights = {dimension.id: max(dimension.weight, 0.0) for dimension in dimensions}
    total_weight = sum(weights.values())
    if total_weight <= 0:
        return None, 0.0, 0.0
    weighted = 0.0
    for dimension in dimensions:
        score = float(dimension_results.get(dimension.id, {}).get("score", 0.0))
        weighted += weights[dimension.id] * score
    return round(weighted / total_weight, 4), round(weighted, 4), total_weight


def _heuristic_scale_label(hit_count: int, total: int, scale: list[str]) -> str | None:
    if not scale:
        return None
    if len(scale) == 2:
        return scale[-1] if hit_count > 0 else scale[0]
    if total <= 0:
        return scale[0]
    ratio = hit_count / total
    if ratio >= 0.67:
        return scale[-1]
    if ratio > 0:
        return scale[1]
    return scale[0]


def _is_abstention(answer: str) -> bool:
    normalized = _normalize(answer)
    return any(pattern in normalized for pattern in ABSTENTION_PATTERNS)


def _partial_abstention(answer: str) -> bool:
    normalized = _normalize(answer)
    return _is_abstention(answer) and any(token in normalized for token in ("maybe", "likely", "possibly", "guess"))


def _strip_markdown_fences(value: str) -> str:
    stripped = value.strip()
    fence_match = re.match(r"^```(?:json)?\s*\n?(.*?)\n?```$", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence_match is not None:
        return fence_match.group(1).strip()
    return stripped


def _judge_request(
    *,
    role: str,
    config: EvaluationModelConfig,
    prompt: str,
    context: dict[str, Any],
    run_id: str,
    exp_id: str,
    engine: Engine,
    event_logger: Any | None = None,
) -> tuple[dict[str, Any] | None, EvaluationJudgeInfo, EvaluationTrace]:
    if event_logger is not None:
        event_logger(
            "EVALUATE",
            "Starting judge request",
            {
                "runId": run_id,
                "experimentId": exp_id,
                "provider": config.provider,
                "model": config.model,
                "judgeRole": role,
            },
        )
    request = AIRequest(
        question=prompt,
        context=json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True),
        provider_name=config.provider,
        model_name=config.model,
        strategy_name="inline",
        context_format="json",
        system_instruction=EVALUATION_SYSTEM_INSTRUCTION,
        params={"temperature": config.temperature, **config.params},
        metadata={
            "run_id": run_id,
            "runId": run_id,
            "expId": exp_id,
            "experiment_id": exp_id,
            "phase": "evaluation",
            "judge_role": role,
        },
    )
    model_input = ModelInput(
        system_instruction=EVALUATION_SYSTEM_INSTRUCTION,
        prompt=(
            f"Context format: {request.context_format}\n\n"
            f"Question:\n{request.question}\n\n"
            f"Context:\n{request.context}\n"
        ),
    )
    result = engine.execute_model_input(request, model_input)
    trace = EvaluationTrace(
        aiTrace=result.trace,
        rawResponse=result.raw_response,
        error=result.error,
    )
    metrics = result.trace.get("metrics", {}) if isinstance(result.trace, dict) else {}
    info = EvaluationJudgeInfo(
        used=True,
        role=role,
        provider=config.provider,
        model=config.model,
        inputTokens=result.usage.get("inputTokens"),
        outputTokens=result.usage.get("outputTokens"),
        durationMs=metrics.get("total_duration_ms"),
    )
    if result.error:
        if event_logger is not None:
            event_logger(
                "EVALUATE",
                "Judge request failed",
                {
                    "runId": run_id,
                    "experimentId": exp_id,
                    "provider": config.provider,
                    "model": config.model,
                    "judgeRole": role,
                    "error": result.error,
                },
            )
        return None, info, trace
    try:
        payload = json.loads(_strip_markdown_fences(result.answer))
        if event_logger is not None:
            event_logger(
                "EVALUATE",
                "Judge request completed",
                {
                    "runId": run_id,
                    "experimentId": exp_id,
                    "provider": config.provider,
                    "model": config.model,
                    "judgeRole": role,
                    "inputTokens": info.inputTokens,
                    "outputTokens": info.outputTokens,
                    "durationMs": info.durationMs,
                },
            )
        return payload, info, trace
    except json.JSONDecodeError:
        if event_logger is not None:
            event_logger(
                "EVALUATE",
                "Judge returned invalid JSON",
                {
                    "runId": run_id,
                    "experimentId": exp_id,
                    "provider": config.provider,
                    "model": config.model,
                    "judgeRole": role,
                    "response": result.answer,
                },
            )
        return None, info, trace


def _request_run_metadata(result: Any) -> tuple[str, str]:
    run_id = getattr(result, "runId", None)
    exp_id = getattr(result, "experimentId", None)
    return (str(run_id) if run_id is not None else "", str(exp_id) if exp_id is not None else "")


def _evaluate_exact(
    result: RunResult,
    question: Question,
    expected: Any,
    accepted_answers: list[Any],
    engine: Engine,
    experiment: Experiment,
    normalization_hints: list[str] | None = None,
    event_logger: Any | None = None,
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    answer_type = question.evaluation.answerType if question.evaluation else None
    normalization = _normalization_rules(question, normalization_hints)
    details: dict[str, Any] = {
        "expected": expected,
        "acceptedAnswers": accepted_answers,
        "answerType": answer_type or "string",
        "normalization": normalization,
    }
    judge_info = EvaluationJudgeInfo()
    trace = EvaluationTrace()
    extracted: Any = None
    is_extractable = False
    evaluation_method = "no-extraction"
    comparator = "string-normalized-equality"
    if answer_type == "number":
        comparator = "numeric-equality"
    elif answer_type == "year":
        comparator = "year-equality"

    prompt = (
        "You are extracting the final answer to an exact benchmark question.\n\n"
        f"Question:\n{question.question}\n\n"
        f"Expected answer type:\n{answer_type}\n\n"
        f"Model answer:\n{result.answer}\n\n"
        "Rules:\n"
        "- Extract only the final answer supported by the model answer.\n"
        "- Do not use external knowledge.\n"
        "- Do not infer information that is not explicitly present.\n"
        "- If no reliable extraction is possible, return null.\n"
        "- Do not decide whether the answer is correct.\n"
        "- Do not assign a score or label.\n\n"
        "Output requirements:\n"
        "- Return valid JSON only.\n"
        "- Do not include markdown.\n"
        "- Do not include extra text.\n"
        "- Use exactly these fields:\n"
        "  - extractedAnswer\n"
        "  - isExtractable\n"
        "  - justification\n\n"
        "Return:\n"
        '{\n  "extractedAnswer": null,\n  "isExtractable": false,\n  "justification": ""\n}'
    )

    if experiment.evaluation.judge is not None:
        run_id, exp_id = _request_run_metadata(result)
        judge_payload, judge_info, trace = _judge_request(
            role="exact-extractor",
            config=experiment.evaluation.judge,
            prompt=prompt,
            context={
                "question": question.question,
                "answerType": answer_type,
                "modelAnswer": result.answer,
            },
            run_id=run_id,
            exp_id=exp_id,
            engine=engine,
            event_logger=event_logger,
        )
        if judge_payload is not None:
            extracted = judge_payload.get("extractedAnswer")
            is_extractable = bool(judge_payload.get("isExtractable"))
            evaluation_method = "judge-extraction"
        elif experiment.evaluation.fallback is not None:
            if event_logger is not None:
                event_logger(
                    "EVALUATE",
                    "Primary judge failed; trying fallback judge",
                    {
                        "runId": run_id,
                        "experimentId": exp_id,
                        "judgeRole": "exact-extractor",
                        "provider": experiment.evaluation.fallback.provider,
                        "model": experiment.evaluation.fallback.model,
                    },
                )
            judge_payload, judge_info, trace = _judge_request(
                role="exact-extractor",
                config=experiment.evaluation.fallback,
                prompt=prompt,
                context={
                    "question": question.question,
                    "answerType": answer_type,
                    "modelAnswer": result.answer,
                },
                run_id=run_id,
                exp_id=exp_id,
                engine=engine,
                event_logger=event_logger,
            )
            judge_info.fallbackUsed = True
            if judge_payload is not None:
                extracted = judge_payload.get("extractedAnswer")
                is_extractable = bool(judge_payload.get("isExtractable"))
                evaluation_method = "fallback-judge-extraction"

    if extracted is None:
        if answer_type == "number":
            extracted = _extract_number(result.answer)
        elif answer_type == "year":
            extracted = _extract_year(result.answer)
        else:
            extracted = result.answer.strip()
        if extracted is not None and not (isinstance(extracted, str) and not extracted):
            is_extractable = True
            evaluation_method = "rule-fallback-extraction"

    details["extractedAnswer"] = extracted
    details["isExtractable"] = is_extractable
    details["comparisonMethod"] = comparator
    details["evaluationMethod"] = evaluation_method

    expected_normalized = _apply_normalization(expected, normalization, answer_type)
    details["expectedNormalized"] = expected_normalized

    normalized_extracted = _apply_normalization(extracted, normalization, answer_type)
    details["extractedAnswerNormalized"] = normalized_extracted
    accepted_normalized = [
        _apply_normalization(item, normalization, answer_type)
        for item in accepted_answers
    ]
    candidates = [item for item in [expected_normalized, *accepted_normalized] if item is not None]
    score = 1.0 if normalized_extracted in candidates else 0.0
    details["dimensionResults"] = {
        "exact-match": {
            "label": "correct" if score == 1.0 else "incorrect",
            "score": score,
            "weight": 1.0,
            "justification": "Normalized extracted answer compared against accepted canonical answers.",
            "scale": ["incorrect", "correct"],
        }
    }
    return score, "correct" if score == 1.0 else "incorrect", details, judge_info, trace


def _criterion_keywords(criterion: EvaluationRubricCriterion) -> list[str]:
    if criterion.keywords:
        return [_normalize(item) for item in criterion.keywords if item]
    tokens = [token for token in _slug_tokens(criterion.description) if token not in {"mentions", "provides", "related"}]
    return list(dict.fromkeys(tokens))


def _legacy_dimensions_from_rubric(
    rubric: list[EvaluationRubricCriterion],
) -> list[EvaluationDimension]:
    return [
        EvaluationDimension(
            id=item.id,
            weight=item.weight,
            description=item.description,
            defaultScale=["absent", "present"],
        )
        for item in rubric
    ]


def _context_for_dimension(
    dimension_id: str,
    evaluation_context_by_dimension: dict[str, dict[str, Any]] | None,
    evaluation_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if evaluation_context_by_dimension and isinstance(evaluation_context_by_dimension.get(dimension_id), dict):
        return evaluation_context_by_dimension[dimension_id]
    if evaluation_context and isinstance(evaluation_context.get(dimension_id), dict):
        return evaluation_context[dimension_id]
    return evaluation_context if isinstance(evaluation_context, dict) else {}


def _dimension_keywords(
    dimension: EvaluationDimension,
    context: dict[str, Any],
    rubric_lookup: dict[str, EvaluationRubricCriterion] | None = None,
) -> list[str]:
    if rubric_lookup and dimension.id in rubric_lookup:
        keywords = _criterion_keywords(rubric_lookup[dimension.id])
        if keywords:
            return keywords
    keywords: list[str] = []
    for field_name in (
        "supportedThemes",
        "availableThemes",
        "coreThemesForHighScore",
        "priorityThemes",
        "majorThemes",
        "preferredThemes",
        "profileSpecificSignals",
        "expectedAbstractions",
        "preferredEvidence",
    ):
        value = context.get(field_name)
        if isinstance(value, list):
            keywords.extend(_normalize(item) for item in value if isinstance(item, str))
    if not keywords and dimension.description:
        keywords.extend(_slug_tokens(dimension.description))
    return list(dict.fromkeys(item for item in keywords if item))


def _evaluate_analytical_heuristic(
    answer: str,
    rubric: list[EvaluationRubricCriterion],
) -> tuple[float, dict[str, Any]]:
    normalized_answer = _normalize(answer)
    matched: list[str] = []
    missing: list[str] = []
    for criterion in rubric:
        keywords = _criterion_keywords(criterion)
        hit = any(keyword and keyword in normalized_answer for keyword in keywords)
        if hit:
            matched.append(criterion.id)
        else:
            missing.append(criterion.id)

    return 0.0, {
        "matchedCriteria": matched,
        "missingCriteria": missing,
        "justification": "Heuristic rubric matching used.",
        "evaluationMethod": "heuristic-rubric",
    }


def _dimension_assessment_payload(
    payload: dict[str, Any] | None,
    dimensions: list[EvaluationDimension],
    *,
    evaluation_method: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    assessments = payload.get("dimensionAssessments", [])
    if not isinstance(assessments, list):
        return None
    by_id: dict[str, dict[str, Any]] = {}
    dimensions_by_id = {dimension.id: dimension for dimension in dimensions}
    for item in assessments:
        if not isinstance(item, dict):
            return None
        dimension_id = str(item.get("id", ""))
        dimension = dimensions_by_id.get(dimension_id)
        if dimension is None or dimension_id in by_id:
            return None
        label = str(item.get("label", ""))
        if dimension.defaultScale and label not in dimension.defaultScale:
            return None
        by_id[dimension_id] = {
            "label": label,
            "score": _scale_label_score(dimension.defaultScale, label),
            "weight": max(dimension.weight, 0.0),
            "justification": str(item.get("justification", "")),
            "scale": list(dimension.defaultScale),
        }

    for dimension in dimensions:
        if dimension.id not in by_id:
            lowest = dimension.defaultScale[0] if dimension.defaultScale else None
            by_id[dimension.id] = {
                "label": lowest,
                "score": _scale_label_score(dimension.defaultScale, lowest),
                "weight": max(dimension.weight, 0.0),
                "justification": "",
                "scale": list(dimension.defaultScale),
            }

    return {
        "dimensionResults": by_id,
        "overallJustification": str(payload.get("overallJustification", "")),
        "evaluationMethod": evaluation_method,
    }


def _heuristic_dimension_results(
    answer: str,
    dimensions: list[EvaluationDimension],
    *,
    evaluation_context: dict[str, Any] | None = None,
    evaluation_context_by_dimension: dict[str, dict[str, Any]] | None = None,
    rubric_lookup: dict[str, EvaluationRubricCriterion] | None = None,
) -> dict[str, Any]:
    normalized_answer = _normalize(answer)
    dimension_results: dict[str, dict[str, Any]] = {}
    for dimension in dimensions:
        scale = list(dimension.defaultScale)
        context = _context_for_dimension(
            dimension.id,
            evaluation_context_by_dimension,
            evaluation_context,
        )
        label: str | None = None
        justification = "Heuristic dimension assessment used."
        if dimension.id == "conciseness":
            word_count = len([token for token in answer.split() if token])
            if word_count <= 80:
                label = scale[-1] if scale else None
            elif word_count <= 140 and len(scale) > 1:
                label = scale[1]
            else:
                label = scale[0] if scale else None
        elif dimension.id == "count":
            expected_count = context.get("expectedCount")
            item_count = len(
                [
                    line
                    for line in answer.splitlines()
                    if line.strip() and any(char.isdigit() for char in line[:4])
                ]
            )
            if not item_count:
                item_count = len(re.findall(r"\b\d{4}\b", answer))
            label = (
                scale[-1]
                if isinstance(expected_count, int) and item_count == expected_count and scale
                else scale[0] if scale else None
            )
            justification = "Heuristic count based on numbered lines or detected year-bearing items."
        elif dimension.id == "answerability":
            label = scale[-1] if _is_abstention(answer) and scale else scale[0] if scale else None
            justification = "Heuristic answerability based on abstention language."
        elif dimension.id == "task-success":
            keyword_hits = 1 if len(answer.split()) >= 4 else 0
            label = _heuristic_scale_label(keyword_hits, 1, scale)
        else:
            keywords = _dimension_keywords(dimension, context, rubric_lookup)
            hit_count = sum(1 for keyword in keywords if keyword and keyword in normalized_answer)
            total = len(keywords)
            if dimension.id == "synthesis":
                synthesis_hits = sum(
                    1 for token in ("overall", "suggests", "indicates", "shows", "combines", "synthes")
                    if token in normalized_answer
                )
                hit_count = max(hit_count, synthesis_hits)
                total = max(total, 2)
            elif dimension.id in {"grounded", "factual-correctness"} and keywords:
                total = max(total, 3)
            label = _heuristic_scale_label(hit_count, total, scale)
        dimension_results[dimension.id] = {
            "label": label,
            "score": _scale_label_score(scale, label),
            "weight": max(dimension.weight, 0.0),
            "justification": justification,
            "scale": scale,
        }
    return {
        "dimensionResults": dimension_results,
        "overallJustification": "Heuristic dimension assessment used.",
        "evaluationMethod": "heuristic-dimensions",
    }


def _score_analytical_criteria(
    matched_criteria: list[str],
    rubric: list[EvaluationRubricCriterion],
) -> tuple[float, str, float, float]:
    weights = {criterion.id: max(criterion.weight, 0.0) for criterion in rubric}
    total_weight = sum(weights.values())
    matched_weight = sum(weights.get(item, 0.0) for item in matched_criteria)
    score = round(matched_weight / total_weight, 4) if total_weight > 0 else 0.0
    label = "strong" if score >= 0.8 else "partial" if score > 0 else "weak"
    return score, label, matched_weight, total_weight


def _invalid_analytical_result(
    reason: str,
    rubric: list[EvaluationRubricCriterion],
) -> tuple[float | None, str | None, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    return None, None, "invalid-evaluation-config", {
        "reason": reason,
        "rubric": [item.model_dump(mode="json") for item in rubric],
        "matchedCriteria": [],
        "missingCriteria": [],
        "justification": "",
        "evaluationMethod": "invalid-evaluation-config",
    }, EvaluationJudgeInfo(), EvaluationTrace()


def _normalize_judge_criteria_payload(
    payload: dict[str, Any] | None,
    rubric: list[EvaluationRubricCriterion],
    *,
    evaluation_method: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    rubric_ids = {item.id for item in rubric}
    matched = payload.get("matchedCriteria", [])
    missing = payload.get("missingCriteria", [])
    if not isinstance(matched, list) or not isinstance(missing, list):
        return None
    matched_ids = [str(item) for item in matched]
    missing_ids = [str(item) for item in missing]
    if any(item not in rubric_ids for item in matched_ids + missing_ids):
        return None
    if set(matched_ids) & set(missing_ids):
        return None
    resolved_missing = [item.id for item in rubric if item.id not in set(matched_ids)]
    return {
        "matchedCriteria": [item.id for item in rubric if item.id in set(matched_ids)],
        "missingCriteria": resolved_missing if not missing_ids else [item.id for item in rubric if item.id in set(missing_ids)],
        "justification": str(payload.get("justification", "")),
        "evaluationMethod": evaluation_method,
    }


def _evaluate_analytical_dimensions(
    result: RunResult,
    question: Question,
    judge_reference: dict[str, Any] | None,
    evaluation_context: dict[str, Any] | None,
    evaluation_context_by_dimension: dict[str, dict[str, Any]] | None,
    engine: Engine,
    experiment: Experiment,
    event_logger: Any | None = None,
) -> tuple[float | None, str | None, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    dimensions = question.evaluation.dimensions if question.evaluation else []
    if not dimensions:
        return _invalid_analytical_result("Missing analytical dimensions.", [])
    if sum(max(item.weight, 0.0) for item in dimensions) <= 0:
        return _invalid_analytical_result("Analytical dimensions have no positive weight.", [])

    if experiment.evaluation.judge is not None:
        run_id, exp_id = _request_run_metadata(result)
        prompt = (
            "You are evaluating a benchmark answer dimension by dimension.\n\n"
            "Task:\n"
            "Assess each evaluation dimension using only the provided answer, dimension definitions, and context.\n\n"
            "Rules:\n"
            "- Evaluate each dimension independently.\n"
            "- Use only labels from the dimension's allowed scale.\n"
            "- Use the per-dimension context to understand valid evidence and constraints.\n"
            "- Do not use external knowledge.\n"
            "- Be conservative when evidence is weak.\n"
            "- Do not compute the final weighted score.\n\n"
            "Output requirements:\n"
            "- Return valid JSON only.\n"
            "- Do not include markdown or extra text.\n"
            "- Use exactly these fields:\n"
            "  - dimensionAssessments\n"
            "  - overallJustification\n\n"
            "Return this JSON structure:\n"
            '{\n'
            '  "dimensionAssessments": [\n'
            '    {"id": "", "label": "", "justification": ""}\n'
            "  ],\n"
            '  "overallJustification": ""\n'
            "}"
        )
        judge_payload, judge_info, trace = _judge_request(
            role="analytical-dimensions-judge",
            config=experiment.evaluation.judge,
            prompt=prompt,
            context={
                "question": question.question,
                "dimensions": [item.model_dump(mode="json") for item in dimensions],
                "modelAnswer": result.answer,
                "judgeReference": judge_reference,
                "evaluationContext": evaluation_context,
                "evaluationContextByDimension": evaluation_context_by_dimension,
            },
            run_id=run_id,
            exp_id=exp_id,
            engine=engine,
            event_logger=event_logger,
        )
        details = _dimension_assessment_payload(
            judge_payload,
            dimensions,
            evaluation_method="judge-dimensions",
        )
        if details is not None:
            score, matched_weight, total_weight = _score_dimension_results(
                details["dimensionResults"],
                dimensions,
            )
            details["dimensions"] = [item.model_dump(mode="json") for item in dimensions]
            details["matchedWeight"] = matched_weight
            details["totalWeight"] = total_weight
            label = "strong" if score is not None and score >= 0.8 else "partial" if score is not None and score > 0 else "weak"
            return score, label, "evaluated", details, judge_info, trace
        if experiment.evaluation.fallback is not None:
            if event_logger is not None:
                event_logger(
                    "EVALUATE",
                    "Primary judge failed; trying fallback judge",
                    {
                        "runId": run_id,
                        "experimentId": exp_id,
                        "judgeRole": "analytical-dimensions-judge",
                        "provider": experiment.evaluation.fallback.provider,
                        "model": experiment.evaluation.fallback.model,
                    },
                )
            judge_payload, fallback_info, fallback_trace = _judge_request(
                role="analytical-dimensions-judge",
                config=experiment.evaluation.fallback,
                prompt=prompt,
                context={
                    "question": question.question,
                    "dimensions": [item.model_dump(mode="json") for item in dimensions],
                    "modelAnswer": result.answer,
                    "judgeReference": judge_reference,
                    "evaluationContext": evaluation_context,
                    "evaluationContextByDimension": evaluation_context_by_dimension,
                },
                run_id=run_id,
                exp_id=exp_id,
                engine=engine,
                event_logger=event_logger,
            )
            fallback_info.fallbackUsed = True
            details = _dimension_assessment_payload(
                judge_payload,
                dimensions,
                evaluation_method="fallback-judge-dimensions",
            )
            if details is not None:
                score, matched_weight, total_weight = _score_dimension_results(
                    details["dimensionResults"],
                    dimensions,
                )
                details["dimensions"] = [item.model_dump(mode="json") for item in dimensions]
                details["matchedWeight"] = matched_weight
                details["totalWeight"] = total_weight
                label = "strong" if score is not None and score >= 0.8 else "partial" if score is not None and score > 0 else "weak"
                return score, label, "evaluated", details, fallback_info, fallback_trace

    details = _heuristic_dimension_results(
        result.answer,
        dimensions,
        evaluation_context=evaluation_context,
        evaluation_context_by_dimension=evaluation_context_by_dimension,
    )
    score, matched_weight, total_weight = _score_dimension_results(
        details["dimensionResults"],
        dimensions,
    )
    details["dimensions"] = [item.model_dump(mode="json") for item in dimensions]
    details["matchedWeight"] = matched_weight
    details["totalWeight"] = total_weight
    label = "strong" if score is not None and score >= 0.8 else "partial" if score is not None and score > 0 else "weak"
    return score, label, "evaluated", details, EvaluationJudgeInfo(), EvaluationTrace()


def _evaluate_analytical(
    result: RunResult,
    question: Question,
    judge_reference: dict[str, Any] | None,
    evaluation_context: dict[str, Any] | None,
    engine: Engine,
    experiment: Experiment,
    evaluation_context_by_dimension: dict[str, dict[str, Any]] | None = None,
    event_logger: Any | None = None,
) -> tuple[float | None, str | None, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    dimensions = question.evaluation.dimensions if question.evaluation else []
    if dimensions:
        return _evaluate_analytical_dimensions(
            result,
            question,
            judge_reference,
            evaluation_context,
            evaluation_context_by_dimension,
            engine,
            experiment,
            event_logger,
        )
    rubric = question.evaluation.rubric if question.evaluation else []
    if not rubric:
        return _invalid_analytical_result("Missing analytical rubric.", rubric)
    if sum(max(item.weight, 0.0) for item in rubric) <= 0:
        return _invalid_analytical_result("Analytical rubric has no positive weight.", rubric)
    if experiment.evaluation.judge is not None and rubric:
        run_id, exp_id = _request_run_metadata(result)
        prompt = (
            "You are evaluating an answer to a benchmark question using a rubric.\n\n"
            "Task:\n"
            "Determine which rubric criteria are clearly satisfied by the answer.\n\n"
            "Rules:\n"
            "- Evaluate the answer only against the provided rubric.\n"
            "- Use the provided evaluation context only to understand the valid candidate space and the available evidence.\n"
            "- Do not use external knowledge.\n"
            "- Do not infer that a criterion is satisfied unless the answer clearly supports it.\n"
            "- Be conservative: if unsure, do not match the criterion.\n"
            "- Only use criterion ids that exist in the rubric.\n"
            "- Do not compute the final score.\n"
            "- Do not assign the final label.\n\n"
            "Output requirements:\n"
            "- Return valid JSON only.\n"
            "- Do not include markdown.\n"
            "- Do not include extra text.\n"
            "- Use exactly these fields:\n"
            "  - matchedCriteria\n"
            "  - missingCriteria\n"
            "  - justification\n\n"
            "Return this JSON structure:\n"
            '{\n  "matchedCriteria": [],\n  "missingCriteria": [],\n  "justification": ""\n}'
        )
        judge_payload, judge_info, trace = _judge_request(
            role="analytical-judge",
            config=experiment.evaluation.judge,
            prompt=prompt,
            context={
                "question": question.question,
                "rubric": [item.model_dump(mode="json") for item in rubric],
                "modelAnswer": result.answer,
                "judgeReference": judge_reference,
                "evaluationContext": evaluation_context,
            },
            run_id=run_id,
            exp_id=exp_id,
            engine=engine,
            event_logger=event_logger,
        )
        details = _normalize_judge_criteria_payload(judge_payload, rubric, evaluation_method="judge-rubric")
        if details is not None:
            score, label, matched_weight, total_weight = _score_analytical_criteria(
                details["matchedCriteria"],
                rubric,
            )
            details["rubric"] = [item.model_dump(mode="json") for item in rubric]
            details["matchedWeight"] = matched_weight
            details["totalWeight"] = total_weight
            return score, label, "evaluated", details, judge_info, trace
        if experiment.evaluation.fallback is not None:
            if event_logger is not None:
                event_logger(
                    "EVALUATE",
                    "Primary judge failed; trying fallback judge",
                    {
                        "runId": run_id,
                        "experimentId": exp_id,
                        "judgeRole": "analytical-judge",
                        "provider": experiment.evaluation.fallback.provider,
                        "model": experiment.evaluation.fallback.model,
                    },
                )
            judge_payload, fallback_info, fallback_trace = _judge_request(
                role="analytical-judge",
                config=experiment.evaluation.fallback,
                prompt=prompt,
                context={
                    "question": question.question,
                    "rubric": [item.model_dump(mode="json") for item in rubric],
                    "modelAnswer": result.answer,
                    "judgeReference": judge_reference,
                    "evaluationContext": evaluation_context,
                },
                run_id=run_id,
                exp_id=exp_id,
                engine=engine,
                event_logger=event_logger,
            )
            fallback_info.fallbackUsed = True
            details = _normalize_judge_criteria_payload(judge_payload, rubric, evaluation_method="fallback-judge-rubric")
            if details is not None:
                score, label, matched_weight, total_weight = _score_analytical_criteria(
                    details["matchedCriteria"],
                    rubric,
                )
                details["rubric"] = [item.model_dump(mode="json") for item in rubric]
                details["matchedWeight"] = matched_weight
                details["totalWeight"] = total_weight
                return score, label, "evaluated", details, fallback_info, fallback_trace

    _, details = _evaluate_analytical_heuristic(result.answer, rubric)
    details["rubric"] = [item.model_dump(mode="json") for item in rubric]
    score, label, matched_weight, total_weight = _score_analytical_criteria(
        details["matchedCriteria"],
        rubric,
    )
    details["matchedWeight"] = matched_weight
    details["totalWeight"] = total_weight
    return score, label, "evaluated", details, EvaluationJudgeInfo(), EvaluationTrace()


def _evaluate_unanswerable(
    result: RunResult,
    question: Question | None = None,
    evaluation_context_by_dimension: dict[str, dict[str, Any]] | None = None,
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    if _is_abstention(result.answer):
        matched_pattern = next((pattern for pattern in ABSTENTION_PATTERNS if pattern in _normalize(result.answer)), None)
        if _partial_abstention(result.answer):
            label = "partial-abstention"
            score = 0.5
            reason = "Matched abstention language but included hedging."
        else:
            label = "correct-abstention"
            score = 1.0
            reason = "Matched abstention language."
    else:
        label = "fabrication"
        score = 0.0
        matched_pattern = None
        reason = "Answer did not abstain despite unsupported question."
    details = {
        "answer": result.answer,
        "classificationReason": reason,
        "evaluationMethod": "rule-unanswerable",
    }
    if matched_pattern is not None:
        details["matchedPattern"] = matched_pattern
    dimensions = question.evaluation.dimensions if question and question.evaluation else []
    if dimensions:
        dimension_results: dict[str, dict[str, Any]] = {}
        normalized_answer = _normalize(result.answer)
        forbidden_claims = []
        if evaluation_context_by_dimension and isinstance(evaluation_context_by_dimension.get("grounded"), dict):
            raw_forbidden = evaluation_context_by_dimension["grounded"].get("forbiddenClaims", [])
            if isinstance(raw_forbidden, list):
                forbidden_claims = [_normalize(item) for item in raw_forbidden if isinstance(item, str)]
        for dimension in dimensions:
            if dimension.id == "answerability":
                dim_label = "correct" if _is_abstention(result.answer) else "incorrect"
                dim_justification = reason
            elif dimension.id == "grounded":
                has_forbidden = any(token in normalized_answer for token in forbidden_claims)
                dim_label = "grounded" if _is_abstention(result.answer) and not has_forbidden else "ungrounded"
                dim_justification = "Groundedness based on abstention and absence of forbidden invented claims."
            elif dimension.id == "task-success":
                dim_label = "successful" if score == 1.0 else "partial" if score > 0 else "poor"
                dim_justification = "Task success based on whether the answer abstained appropriately."
            else:
                dim_label = _default_scale_label(dimension.defaultScale, score)
                dim_justification = "Derived from the unanswerable-task heuristic outcome."
            dimension_results[dimension.id] = {
                "label": dim_label,
                "score": _scale_label_score(dimension.defaultScale, dim_label),
                "weight": max(dimension.weight, 0.0),
                "justification": dim_justification,
                "scale": list(dimension.defaultScale),
            }
        details["dimensionResults"] = dimension_results
        details["dimensions"] = [item.model_dump(mode="json") for item in dimensions]
        aggregate_score, matched_weight, total_weight = _score_dimension_results(dimension_results, dimensions)
        if aggregate_score is not None:
            score = aggregate_score
        details["matchedWeight"] = matched_weight
        details["totalWeight"] = total_weight
    return score, label, details, EvaluationJudgeInfo(), EvaluationTrace()


def evaluate_run_result(
    result: RunResult,
    provider: DatasetProvider,
    experiment: Experiment,
    *,
    only: str | None = None,
    mode: str | None = None,
    fail_on_missing_gold: bool = False,
    engine: Engine | None = None,
    event_logger: Any | None = None,
) -> EvaluationRunResult | None:
    if result.status != "success":
        return None
    if only and result.questionId != only:
        return None

    question = provider.get_question(result.questionId)
    evaluation_mode = question.evaluation.mode if question.evaluation else "exact"
    if mode and evaluation_mode != mode:
        return None

    instance = provider.get_question_instance(result.questionId, result.contextId)
    expected = None if instance is None else instance.goldAnswer
    accepted_answers = [] if instance is None else list(instance.acceptedAnswers)
    normalization_hints = [] if instance is None else list(instance.normalizationHints)
    if fail_on_missing_gold and evaluation_mode == "exact" and expected is None:
        raise ValueError(f"Missing gold answer for question '{result.questionId}' and context '{result.contextId}'.")

    active_engine = engine or Engine()
    if event_logger is not None:
        event_logger(
            "EVALUATE",
            "Starting evaluation",
            {
                "runId": result.runId,
                "questionId": result.questionId,
                "mode": evaluation_mode,
                "provider": result.provider,
                "model": result.modelName,
                "strategy": result.strategy,
                "format": result.format,
            },
        )
    if evaluation_mode == "exact":
        score, label, details, judge_info, trace = _evaluate_exact(
            result,
            question,
            expected,
            accepted_answers,
            active_engine,
            experiment,
            normalization_hints,
            event_logger,
        )
        evaluation_status = "evaluated"
    elif evaluation_mode == "analytical":
        score, label, evaluation_status, details, judge_info, trace = _evaluate_analytical(
            result,
            question,
            instance.judgeReference if instance is not None else None,
            instance.evaluationContext if instance is not None else None,
            active_engine,
            experiment,
            evaluation_context_by_dimension=(
                instance.evaluationContextByDimension if instance is not None else None
            ),
            event_logger=event_logger,
        )
    elif evaluation_mode == "unanswerable":
        score, label, details, judge_info, trace = _evaluate_unanswerable(
            result,
            question,
            instance.evaluationContextByDimension if instance is not None else None,
        )
        evaluation_status = "evaluated"
    else:
        raise ValueError(f"Unsupported evaluation mode: {evaluation_mode}")

    details.setdefault("expected", expected)
    details.setdefault("acceptedAnswers", accepted_answers)
    evaluation_method = details.get("evaluationMethod")

    item = EvaluationItemResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        question=question.question,
        evaluationMode=evaluation_mode,
        status=evaluation_status,
        evaluationMethod=str(evaluation_method) if evaluation_method is not None else None,
        score=score,
        label=label,
        details=details,
        executionModel=result.modelName,
        executionStrategy=result.strategy,
        executionFormat=result.format,
        executionInputTokens=result.usage.get("inputTokens"),
        executionOutputTokens=result.usage.get("outputTokens"),
        executionDurationMs=result.timing.durationMs,
        executionToolCalls=len(result.trace.toolCalls),
        evaluationJudgeUsed=judge_info.used,
        evaluationJudgeRole=judge_info.role,
        evaluationJudgeProvider=judge_info.provider,
        evaluationJudgeModel=judge_info.model,
        evaluationInputTokens=judge_info.inputTokens,
        evaluationOutputTokens=judge_info.outputTokens,
        evaluationDurationMs=judge_info.durationMs,
        evaluationTrace=trace,
    )
    summary = EvaluationRunSummary(
        itemCount=1,
        meanScore=score,
        labels={label: 1} if label is not None else {},
    )
    if event_logger is not None:
        event_logger(
            "EVALUATE",
            "Evaluation completed",
            {
                "runId": result.runId,
                "questionId": result.questionId,
                "mode": evaluation_mode,
                "status": evaluation_status,
                "evaluationMethod": item.evaluationMethod,
                "score": item.score,
                "resultLabel": item.label,
                "judgeUsed": item.evaluationJudgeUsed,
                "judgeProvider": item.evaluationJudgeProvider,
                "judgeModel": item.evaluationJudgeModel,
            },
        )
    return EvaluationRunResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        items=[item],
        summary=summary,
        metadata=result.metadata,
    )


def evaluate_run_results(
    results: Iterable[RunResult],
    *,
    experiment: Experiment,
    only: str | None = None,
    mode: str | None = None,
    continue_on_error: bool = False,
    fail_on_missing_gold: bool = False,
    event_logger: Any | None = None,
    on_result: Any | None = None,
) -> list[EvaluationRunResult]:
    provider = DatasetProvider.from_experiment(experiment, _experiment_base_dir(experiment))
    engine = Engine(event_logger=event_logger)
    evaluation_results: list[EvaluationRunResult] = []
    try:
        for result in results:
            try:
                evaluated = evaluate_run_result(
                    result,
                    provider,
                    experiment,
                    only=only,
                    mode=mode,
                fail_on_missing_gold=fail_on_missing_gold,
                engine=engine,
                event_logger=event_logger,
            )
                if evaluated is not None:
                    evaluation_results.append(evaluated)
                if on_result is not None:
                    on_result(result, evaluated)
            except Exception:
                if on_result is not None:
                    on_result(result, None)
                if not continue_on_error:
                    raise
    finally:
        engine.close()
    return evaluation_results


def _experiment_base_dir(experiment: Experiment) -> Path:
    dataset_root = Path(experiment.dataset.root)
    return dataset_root.parent if dataset_root.is_absolute() else dataset_root.resolve().parent


def load_experiment_for_evaluation(path: str | Path) -> tuple[Experiment, Path]:
    experiment_path = Path(path).resolve()
    experiment = load_experiment(experiment_path)
    base_dir = experiment_path.parent
    if not Path(experiment.dataset.root).is_absolute():
        experiment.dataset.root = str((base_dir / experiment.dataset.root).resolve())
    return experiment, base_dir


def runspec_index_for_experiment(
    experiment: Experiment,
    base_dir: Path,
    *,
    experiment_path: str | Path | None = None,
) -> dict[str, Any]:
    return {
        runspec.runId: runspec
        for runspec in generate_runspecs(experiment, base_dir, experiment_path=experiment_path)
    }


def evaluation_output_paths(
    experiment: Experiment,
    base_dir: Path,
    *,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
) -> tuple[Path, Path | None]:
    resolved_output_dir = (
        Path(output_dir).resolve()
        if output_dir
        else resolve_eval_output_dir(experiment, base_dir)
    )
    resolved_jsonl = None
    if output_jsonl:
        resolved_jsonl = Path(output_jsonl).resolve()
    else:
        resolved_jsonl = resolve_eval_jsonl_path(experiment, base_dir)
    return resolved_output_dir, resolved_jsonl


def update_run_results_with_evaluation(
    results: Iterable[RunResult],
    evaluations: Iterable[EvaluationRunResult],
) -> list[RunResult]:
    evaluation_by_run_id = {item.runId: item for item in evaluations}
    updated: list[RunResult] = []
    for result in results:
        evaluated = evaluation_by_run_id.get(result.runId)
        if evaluated is None:
            updated.append(result)
            continue
        item = evaluated.items[0] if evaluated.items else None
        details = item.details if item is not None else {}
        expected = details.get("expected")
        accepted_answers = details.get("acceptedAnswers", [])
        passed = None
        if item is not None:
            passed = item.score is not None and item.score >= 1.0
        result.evaluation = EvaluationResult(
            status=item.status if item is not None else "not_evaluated",
            passed=passed,
            expected=expected,
            acceptedAnswers=list(accepted_answers) if isinstance(accepted_answers, list) else [],
            reason=item.label if item is not None else None,
            evaluator=item.evaluationJudgeModel if item is not None else None,
        )
        updated.append(result)
    return updated


def flatten_evaluation_rows(evaluations: Iterable[EvaluationRunResult]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run_result in evaluations:
        for item in run_result.items:
            rows.append(item.to_persisted_artifact())
    return rows


def build_evaluation_summary(evaluations: Iterable[EvaluationRunResult]) -> EvaluationBatchSummary:
    evaluation_list = list(evaluations)
    labels: dict[str, int] = {}
    score_total = 0.0
    item_count = 0
    scored_item_count = 0
    experiment_id = evaluation_list[0].experimentId if evaluation_list else ""
    for run_result in evaluation_list:
        for item in run_result.items:
            if item.label is not None:
                labels[item.label] = labels.get(item.label, 0) + 1
            if item.score is not None:
                score_total += item.score
                scored_item_count += 1
            item_count += 1
    return EvaluationBatchSummary(
        experimentId=experiment_id,
        runCount=len(evaluation_list),
        itemCount=item_count,
        meanScore=round(score_total / scored_item_count, 4) if scored_item_count else None,
        labels=labels,
    )
