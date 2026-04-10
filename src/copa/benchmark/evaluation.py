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
        metadata={"phase": "evaluation", "judge_role": role},
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


def _evaluate_exact(
    result: RunResult,
    question: Question,
    expected: Any,
    engine: Engine,
    experiment: Experiment,
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    answer_type = question.evaluation.answerType if question.evaluation else None
    details: dict[str, Any] = {
        "expected": expected,
        "answerType": answer_type or "string",
    }
    judge_info = EvaluationJudgeInfo()
    trace = EvaluationTrace()

    extracted: Any
    comparator = "string-normalized-equality"
    if answer_type == "number":
        extracted = _extract_number(result.answer)
        comparator = "numeric-equality"
    elif answer_type == "year":
        extracted = _extract_year(result.answer)
        comparator = "year-equality"
    else:
        extracted = result.answer.strip()

    if extracted is None and experiment.evaluation.judge is not None:
        prompt = (
            "Extract the canonical answer from the model answer.\n"
            "Return JSON with one field named extractedAnswer.\n"
            "If extraction is not possible, use null."
        )
        judge_payload, judge_info, trace = _judge_request(
            role="exact-extractor",
            config=experiment.evaluation.judge,
            prompt=prompt,
            context={
                "question": question.question,
                "answerType": answer_type,
                "modelAnswer": result.answer,
            },
            engine=engine,
        )
        if judge_payload is not None:
            extracted = judge_payload.get("extractedAnswer")

    details["extractedAnswer"] = extracted
    details["comparator"] = comparator

    if answer_type in {"number", "year"}:
        score = 1.0 if extracted == expected else 0.0
    else:
        score = 1.0 if _normalize(extracted) == _normalize(expected) else 0.0
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
    total_weight = sum(max(criterion.weight, 0.0) for criterion in rubric) or 1.0
    matched_weight = 0.0

    for criterion in rubric:
        keywords = _criterion_keywords(criterion)
        hit = any(keyword and keyword in normalized_answer for keyword in keywords)
        if hit:
            matched.append(criterion.id)
            matched_weight += max(criterion.weight, 0.0)
        else:
            missing.append(criterion.id)

    score = round(matched_weight / total_weight, 4)
    return score, {
        "matchedCriteria": matched,
        "missingCriteria": missing,
        "justification": "Heuristic rubric matching used.",
    }


def _evaluate_analytical(
    result: RunResult,
    question: Question,
    engine: Engine,
    experiment: Experiment,
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    rubric = question.evaluation.rubric if question.evaluation else []
    if experiment.evaluation.judge is not None and rubric:
        prompt = (
            "Evaluate the answer against the rubric.\n"
            "Return JSON with: score (0..1), label, matchedCriteria, missingCriteria, justification."
        )
        judge_payload, judge_info, trace = _judge_request(
            role="analytical-judge",
            config=experiment.evaluation.judge,
            prompt=prompt,
            context={
                "question": question.question,
                "rubric": [item.model_dump(mode="json") for item in rubric],
                "modelAnswer": result.answer,
            },
            engine=engine,
        )
        if judge_payload is not None:
            score = float(judge_payload.get("score", 0.0))
            details = {
                "matchedCriteria": list(judge_payload.get("matchedCriteria", [])),
                "missingCriteria": list(judge_payload.get("missingCriteria", [])),
                "justification": judge_payload.get("justification", ""),
                "rubric": [item.model_dump(mode="json") for item in rubric],
            }
            label = str(judge_payload.get("label", "analytical"))
            return score, label, details, judge_info, trace
        if experiment.evaluation.fallback is not None:
            judge_payload, fallback_info, fallback_trace = _judge_request(
                role="analytical-judge",
                config=experiment.evaluation.fallback,
                prompt=prompt,
                context={
                    "question": question.question,
                    "rubric": [item.model_dump(mode="json") for item in rubric],
                    "modelAnswer": result.answer,
                },
                engine=engine,
            )
            fallback_info.fallbackUsed = True
            if judge_payload is not None:
                score = float(judge_payload.get("score", 0.0))
                details = {
                    "matchedCriteria": list(judge_payload.get("matchedCriteria", [])),
                    "missingCriteria": list(judge_payload.get("missingCriteria", [])),
                    "justification": judge_payload.get("justification", ""),
                    "rubric": [item.model_dump(mode="json") for item in rubric],
                }
                label = str(judge_payload.get("label", "analytical"))
                return score, label, details, fallback_info, fallback_trace

    score, details = _evaluate_analytical_heuristic(result.answer, rubric)
    details["rubric"] = [item.model_dump(mode="json") for item in rubric]
    label = "strong" if score >= 0.8 else "partial" if score > 0 else "weak"
    return score, label, details, EvaluationJudgeInfo(), EvaluationTrace()


def _evaluate_unanswerable(
    result: RunResult,
) -> tuple[float, str, dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    if _is_abstention(result.answer):
        if _partial_abstention(result.answer):
            label = "partial-abstention"
            score = 0.5
        else:
            label = "correct-abstention"
            score = 1.0
    else:
        label = "fabrication"
        score = 0.0
    return score, label, {"answer": result.answer}, EvaluationJudgeInfo(), EvaluationTrace()


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
            active_engine,
            experiment,
        )
    elif evaluation_mode == "analytical":
        score, label, details, judge_info, trace = _evaluate_analytical(
            result,
            question,
            active_engine,
            experiment,
        )
    elif evaluation_mode == "unanswerable":
        score, label, details, judge_info, trace = _evaluate_unanswerable(result)
    else:
        raise ValueError(f"Unsupported evaluation mode: {evaluation_mode}")

    details.setdefault("expected", expected)
    details.setdefault("acceptedAnswers", accepted_answers)

    item = EvaluationItemResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        question=question.question,
        evaluationMode=evaluation_mode,
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
        labels={label: 1},
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
) -> list[EvaluationRunResult]:
    provider = DatasetProvider.from_experiment(experiment, _experiment_base_dir(experiment))
    engine = Engine()
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
            passed = item.score >= 1.0
        result.evaluation = EvaluationResult(
            status="evaluated",
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
    experiment_id = evaluation_list[0].experimentId if evaluation_list else ""
    for run_result in evaluation_list:
        for item in run_result.items:
            labels[item.label] = labels.get(item.label, 0) + 1
            score_total += item.score
            item_count += 1
    return EvaluationBatchSummary(
        experimentId=experiment_id,
        runCount=len(evaluation_list),
        itemCount=item_count,
        meanScore=round(score_total / item_count, 4) if item_count else 0.0,
        labels=labels,
    )
