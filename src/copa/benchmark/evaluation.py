from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest
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
from copa.dataset.questions import EvaluationRubricCriterion, Question

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


def _normalize(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


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


def _is_abstention(answer: str) -> bool:
    normalized = _normalize(answer)
    return any(pattern in normalized for pattern in ABSTENTION_PATTERNS)


def _partial_abstention(answer: str) -> bool:
    normalized = _normalize(answer)
    return _is_abstention(answer) and any(token in normalized for token in ("maybe", "likely", "possibly", "guess"))


def _judge_request(
    *,
    role: str,
    config: EvaluationModelConfig,
    prompt: str,
    context: dict[str, Any],
    run_id: str,
    exp_id: str,
    engine: Engine,
) -> tuple[dict[str, Any] | None, EvaluationJudgeInfo, EvaluationTrace]:
    request = AIRequest(
        question=prompt,
        context=json.dumps(context, ensure_ascii=True, indent=2, sort_keys=True),
        provider_name=config.provider,
        model_name=config.model,
        strategy_name="inline",
        context_format="json",
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
    result = engine.execute(request)
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
        return None, info, trace
    try:
        return json.loads(result.answer), info, trace
    except json.JSONDecodeError:
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
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    answer_type = question.evaluation.answerType if question.evaluation else None
    details: dict[str, Any] = {
        "expected": expected,
        "acceptedAnswers": accepted_answers,
        "answerType": answer_type or "string",
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
        )
        if judge_payload is not None:
            extracted = judge_payload.get("extractedAnswer")
            is_extractable = bool(judge_payload.get("isExtractable"))
            evaluation_method = "judge-extraction"
        elif experiment.evaluation.fallback is not None:
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

    expected_normalized = _normalize_expected_exact(expected, answer_type)
    details["expectedNormalized"] = expected_normalized

    if answer_type in {"number", "year"}:
        accepted_normalized = [
            _normalize_expected_exact(item, answer_type)
            for item in accepted_answers
        ]
        candidates = [item for item in [expected_normalized, *accepted_normalized] if item is not None]
        score = 1.0 if extracted in candidates else 0.0
    else:
        normalized_extracted = _normalize(extracted)
        normalized_candidates = [
            _normalize(item)
            for item in [expected, *accepted_answers]
            if item is not None
        ]
        score = 1.0 if normalized_extracted in normalized_candidates else 0.0
    return score, "correct" if score == 1.0 else "incorrect", details, judge_info, trace


def _criterion_keywords(criterion: EvaluationRubricCriterion) -> list[str]:
    if criterion.keywords:
        return [_normalize(item) for item in criterion.keywords if item]
    tokens = [token for token in _slug_tokens(criterion.description) if token not in {"mentions", "provides", "related"}]
    return list(dict.fromkeys(tokens))


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


def _evaluate_analytical(
    result: RunResult,
    question: Question,
    judge_reference: dict[str, Any] | None,
    evaluation_context: dict[str, Any] | None,
    engine: Engine,
    experiment: Experiment,
) -> tuple[float | None, str | None, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
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
    if fail_on_missing_gold and evaluation_mode == "exact" and expected is None:
        raise ValueError(f"Missing gold answer for question '{result.questionId}' and context '{result.contextId}'.")

    active_engine = engine or Engine()
    if evaluation_mode == "exact":
        score, label, details, judge_info, trace = _evaluate_exact(
            result,
            question,
            expected,
            accepted_answers,
            active_engine,
            experiment,
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
        )
    elif evaluation_mode == "unanswerable":
        score, label, details, judge_info, trace = _evaluate_unanswerable(result)
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
                )
                if evaluated is not None:
                    evaluation_results.append(evaluated)
            except Exception:
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
