from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelInput
from copa.benchmark.experiment_loader import load_experiment
from copa.benchmark.models import (
    EvaluationBatchSummary,
    EvaluationItemResult,
    EvaluationJudgeInfo,
    EvaluationModelConfig,
    EvaluationRunResult,
    EvaluationRunSummary,
    EvaluationTrace,
    ExperimentDataset,
    Experiment,
    RunResult,
)
from copa.benchmark.paths import resolve_eval_jsonl_path, resolve_eval_output_dir
from copa.benchmark.runspec_generator import generate_runspecs
from copa.dataset.provider import DatasetProvider

EVALUATION_SYSTEM_INSTRUCTION = (
    "You are evaluating benchmark answers.\n"
    "Use only the provided question, answer and ground truth.\n"
    "Do not use external knowledge.\n"
    "Return only the requested JSON."
)

JUDGE_PROMPT = """You are an evaluation assistant for a benchmark. Your task is to evaluate an answer given by a model based strictly on the provided context and criteria.
You must be objective, consistent, and conservative in your evaluation.
Do NOT use external knowledge. Only use the provided ground truth.
Your output must strictly follow the requested JSON format.
Evaluate the answer to the question based on the provided ground truth.

# Question
{question}

# Answer
{answer}

# Ground Truth
{ground_truth}

# Evaluation Scale

Use the following scale for ALL criteria:

- "meets": fully satisfies the criterion
- "partially meets": partially satisfies the criterion, with minor issues or omissions
- "does not meet": does not satisfy the criterion or has major issues

# Evaluation Criteria

## Correctness
The answer must be factually correct according to the ground truth.
- Check whether the information provided is accurate.
- Use the ground truth as the source of truth.

## Completeness
The answer must fully address the question.
- Check whether all parts of the question are answered.
- Penalize important omissions relative to the ground truth.

# Important Rules
- Base your evaluation ONLY on the provided ground truth.
- Ground truth is the source of truth.
- Do NOT assume missing information.
- Be strict: if unsure, prefer "partially meets" or "does not meet".
- Each criterion MUST include a short justification grounded in the provided ground truth.
- Do NOT include chain-of-thought or hidden reasoning. Provide only concise criterion justifications.

# Output Format (STRICT JSON)
Return ONLY a JSON object in the following format:

{{
  "correctness": {{
    "rating": "meets | partially meets | does not meet",
    "justification": "short justification"
  }},
  "completeness": {{
    "rating": "meets | partially meets | does not meet",
    "justification": "short justification"
  }}
}}
"""

RATING_SEVERITY = {
    "meets": 0,
    "partially meets": 1,
    "does not meet": 2,
}

JUDGE_STRUCTURED_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "correctness": {
            "type": "object",
            "properties": {
                "rating": {
                    "type": "string",
                    "enum": ["meets", "partially meets", "does not meet"],
                },
                "justification": {"type": "string"},
            },
            "required": ["rating", "justification"],
            "additionalProperties": False,
        },
        "completeness": {
            "type": "object",
            "properties": {
                "rating": {
                    "type": "string",
                    "enum": ["meets", "partially meets", "does not meet"],
                },
                "justification": {"type": "string"},
            },
            "required": ["rating", "justification"],
            "additionalProperties": False,
        },
    },
    "required": ["correctness", "completeness"],
    "additionalProperties": False,
}


def _normalize_text(value: Any) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    raw = str(value).strip().replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _normalize_structured(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_structured(item) for key, item in sorted(value.items())}
    if isinstance(value, list):
        return [_normalize_structured(item) for item in value]
    number = _coerce_number(value)
    if number is not None:
        return int(number) if number.is_integer() else number
    return _normalize_text(value)


def _parse_candidate_answer(answer: str, schema: dict[str, Any] | None) -> Any:
    stripped = answer.strip()
    if schema is None:
        return stripped
    schema_type = schema.get("type")
    if schema_type == "object":
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            return stripped
    if schema_type == "number":
        return _coerce_number(stripped)
    if schema_type == "string":
        return stripped
    return stripped


def _heuristic_compare(answer: str, accepted_answers: list[Any], schema: dict[str, Any] | None) -> dict[str, Any]:
    parsed_answer = _parse_candidate_answer(answer, schema)
    normalized_answer = _normalize_structured(parsed_answer)
    normalized_candidates = [_normalize_structured(item) for item in accepted_answers]
    matched = any(_matches_expected(parsed_answer, candidate) for candidate in accepted_answers)
    return {
        "acceptedAnswers": accepted_answers,
        "schema": schema,
        "evaluationMethod": "heuristic",
        "matched": matched,
        "outcome": "accepted" if matched else "rejected",
        "parsedAnswer": parsed_answer,
        "normalizedAnswer": normalized_answer,
    }


def _matches_expected(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        if "aliases" in expected and isinstance(expected["aliases"], list):
            normalized_actual = _normalize_structured(actual)
            return any(
                normalized_actual == _normalize_structured(alias)
                for alias in expected["aliases"]
            )
        if not isinstance(actual, dict):
            return False
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            if not _matches_expected(actual[key], expected_value):
                return False
        return True
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return False
        return all(_matches_expected(actual_item, expected_item) for actual_item, expected_item in zip(actual, expected))
    return _normalize_structured(actual) == _normalize_structured(expected)


def _judge_request(
    *,
    config: EvaluationModelConfig,
    prompt: str,
    run_id: str,
    exp_id: str,
    engine: Engine,
) -> tuple[dict[str, Any] | None, EvaluationJudgeInfo, EvaluationTrace]:
    request_params = {
        "temperature": config.temperature,
        **config.params,
    }
    request_params.setdefault(
        "structured_output",
        {
            "name": "judge_response",
            "strict": True,
            "schema": JUDGE_STRUCTURED_OUTPUT_SCHEMA,
        },
    )
    request = AIRequest(
        question=prompt,
        context="{}",
        provider_name=config.provider,
        model_name=config.model,
        strategy_name="inline",
        context_format="text",
        system_instruction=EVALUATION_SYSTEM_INSTRUCTION,
        params=request_params,
        metadata={
            "run_id": run_id,
            "expId": exp_id,
            "phase": "evaluation",
            "judge_role": "judge",
        },
    )
    model_input = ModelInput(
        system_instruction=EVALUATION_SYSTEM_INSTRUCTION,
        prompt=prompt,
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
        role="judge",
        provider=config.provider,
        model=config.model,
        inputTokens=result.usage.get("inputTokens"),
        outputTokens=result.usage.get("outputTokens"),
        durationMs=metrics.get("total_duration_ms"),
    )
    if result.error:
        return None, info, trace
    try:
        return json.loads(result.answer.strip()), info, trace
    except json.JSONDecodeError:
        return None, info, trace


def _evaluate_judge(
    result: RunResult,
    question_text: str,
    ground_truth: str,
    experiment: Experiment,
    engine: Engine,
) -> tuple[dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    if not experiment.evaluation.judges:
        return {
            "evaluationMethod": "judge",
            "error": "Experiment evaluation.judges is required for judge validation.",
        }, EvaluationJudgeInfo(), EvaluationTrace()
    prompt = JUDGE_PROMPT.format(
        question=question_text,
        answer=result.answer,
        ground_truth=ground_truth,
    )
    judge_votes: list[dict[str, Any]] = []
    judge_infos: list[EvaluationJudgeInfo] = []
    traces: list[EvaluationTrace] = []
    valid_votes: list[dict[str, Any]] = []
    for config in experiment.evaluation.judges:
        payload, judge_info, trace = _judge_request(
            config=config,
            prompt=prompt,
            run_id=result.runId,
            exp_id=result.experimentId,
            engine=engine,
        )
        judge_infos.append(judge_info)
        traces.append(trace)
        if payload is None:
            judge_votes.append(
                {
                    "provider": config.provider,
                    "model": config.model,
                    "error": "Judge did not return valid JSON.",
                }
            )
            continue
        correctness = _criterion_payload(payload.get("correctness"))
        completeness = _criterion_payload(payload.get("completeness"))
        vote = {
            "provider": config.provider,
            "model": config.model,
            "correctness": correctness,
            "completeness": completeness,
        }
        judge_votes.append(vote)
        valid_votes.append(vote)

    merged_info = _merge_judge_infos(judge_infos)
    merged_trace = _merge_evaluation_traces(traces)
    if not valid_votes:
        return {
            "evaluationMethod": "judge",
            "groundTruth": ground_truth,
            "judges": judge_votes,
            "error": "Judge did not return valid JSON.",
        }, merged_info, merged_trace
    correctness = _aggregate_votes(valid_votes, "correctness")
    completeness = _aggregate_votes(valid_votes, "completeness")
    summary = _outcome_from_ratings(
        correctness["rating"],
        completeness["rating"],
    )
    return {
        "evaluationMethod": "judge",
        "groundTruth": ground_truth,
        "judges": judge_votes,
        "correctness": correctness,
        "completeness": completeness,
        "outcome": summary,
    }, merged_info, merged_trace


def _criterion_payload(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        rating = str(value.get("rating", "")).strip()
        justification = str(value.get("justification", "")).strip()
        return {
            "rating": rating,
            "justification": justification,
        }
    return {
        "rating": str(value or "").strip(),
        "justification": "",
    }


def _aggregate_votes(votes: list[dict[str, Any]], criterion: str) -> dict[str, Any]:
    counts = {"meets": 0, "partially meets": 0, "does not meet": 0}
    for vote in votes:
        payload = vote.get(criterion)
        if isinstance(payload, dict):
            rating = str(payload.get("rating", "")).strip()
            if rating in counts:
                counts[rating] += 1
    winner = max(
        counts,
        key=lambda item: (counts[item], RATING_SEVERITY[item]),
    )
    return {
        "rating": winner,
        "votes": counts,
    }


def _outcome_from_ratings(*ratings: str) -> str:
    if any(item == "does not meet" for item in ratings):
        return "does_not_meet"
    if any(item == "partially meets" for item in ratings):
        return "partially_meets"
    return "meets"


def _merge_judge_infos(judge_infos: list[EvaluationJudgeInfo]) -> EvaluationJudgeInfo:
    used_infos = [item for item in judge_infos if item.used]
    if not used_infos:
        return EvaluationJudgeInfo()
    providers = {item.provider for item in used_infos if item.provider}
    models = {item.model for item in used_infos if item.model}
    input_tokens = [item.inputTokens for item in used_infos if item.inputTokens is not None]
    output_tokens = [item.outputTokens for item in used_infos if item.outputTokens is not None]
    durations = [item.durationMs for item in used_infos if item.durationMs is not None]
    return EvaluationJudgeInfo(
        used=True,
        role="judges",
        provider=next(iter(providers)) if len(providers) == 1 else None,
        model=next(iter(models)) if len(models) == 1 else None,
        inputTokens=sum(input_tokens) if input_tokens else None,
        outputTokens=sum(output_tokens) if output_tokens else None,
        durationMs=sum(durations) if durations else None,
    )


def _merge_evaluation_traces(traces: list[EvaluationTrace]) -> EvaluationTrace:
    return EvaluationTrace(
        aiTrace={
            "judges": [trace.aiTrace for trace in traces if trace.aiTrace]
        },
        rawResponse=[trace.rawResponse for trace in traces if trace.rawResponse is not None],
        error="; ".join(trace.error for trace in traces if trace.error) or None,
    )


def evaluate_run_result(
    result: RunResult,
    provider: DatasetProvider,
    experiment: Experiment,
    *,
    only: str | None = None,
    mode: str | None = None,
    fail_on_missing_gold: bool = False,
    engine: Engine | None = None,
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
) -> EvaluationRunResult | None:
    del fail_on_missing_gold
    if result.status != "success":
        return None
    if only and result.questionId != only:
        return None

    question = provider.get_question(result.questionId)
    rendered_question = result.question or question.question
    validation_type = question.validation.type
    if mode and validation_type != mode:
        return None
    instance_question = provider.get_question_instance(result.questionId, result.instanceId)
    if instance_question is None:
        raise ValueError(f"Missing question instance mapping for question '{result.questionId}' and instance '{result.instanceId}'.")
    active_engine = engine or Engine()
    if event_logger is not None:
        event_logger(
            "EVALUATE",
            "Starting evaluation",
            {
                "runId": result.runId,
                "questionId": result.questionId,
                "validationType": validation_type,
            },
        )
    if validation_type == "heuristic":
        details = _heuristic_compare(
            result.answer,
            list(instance_question.acceptedAnswers),
            question.validation.schema,
        )
        judge_info = EvaluationJudgeInfo()
        trace = EvaluationTrace()
    elif validation_type == "judge":
        ground_truth = instance_question.groundTruth or ""
        if not ground_truth:
            raise ValueError(
                f"Missing ground truth for judge evaluation on question '{result.questionId}' and instance '{result.instanceId}'."
            )
        details, judge_info, trace = _evaluate_judge(
            result,
            rendered_question,
            ground_truth,
            experiment,
            active_engine,
        )
    else:
        raise ValueError(f"Unsupported validation type: {validation_type}")

    metrics = result.trace.aiTrace.get("metrics", {}) if result.trace.aiTrace else {}
    summary = result.metricsSummary
    item = EvaluationItemResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        instanceId=result.instanceId,
        question=rendered_question,
        evaluationMode=validation_type,
        status="evaluated",
        evaluationMethod=details.get("evaluationMethod"),
        details=details,
        executionModel=result.modelName,
        executionStrategy=result.strategy,
        executionFormat=result.format,
        executionInputTokens=result.usage.get("inputTokens"),
        executionOutputTokens=result.usage.get("outputTokens"),
        executionDurationMs=result.timing.durationMs,
        executionToolCalls=summary.get("tool_call_count", metrics.get("tool_call_count_semantic", metrics.get("tool_call_count"))),
        executionFunctionCalls=summary.get("function_call_count", metrics.get("function_call_count")),
        executionLlmCalls=summary.get("llm_call_count", metrics.get("llm_call_count", metrics.get("model_calls"))),
        questionTags=list(question.tags),
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
    )
    if event_logger is not None:
        event_logger(
            "EVALUATE",
            "Evaluation completed",
            {
                "runId": result.runId,
                "questionId": result.questionId,
                "validationType": validation_type,
                "outcome": details.get("outcome"),
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
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
    on_result: Callable[[RunResult, EvaluationRunResult | None], None] | None = None,
) -> list[EvaluationRunResult]:
    provider = DatasetProvider.from_dataset(experiment.dataset)
    engine = Engine(event_logger=event_logger)
    evaluations: list[EvaluationRunResult] = []
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
                    evaluations.append(evaluated)
                if on_result is not None:
                    on_result(result, evaluated)
            except Exception:
                if not continue_on_error:
                    raise
    finally:
        engine.close()
    return evaluations


def load_experiment_for_evaluation(path: str | Path) -> tuple[Experiment, Path]:
    resolved = Path(path).resolve()
    experiment = load_experiment(resolved)
    experiment.dataset = ExperimentDataset(root=str((resolved.parent / experiment.dataset.root).resolve()))
    return experiment, resolved.parent


def runspec_index_for_experiment(
    experiment: Experiment,
    base_dir: Path,
    *,
    experiment_path: str | Path | None = None,
) -> dict[str, Any]:
    return {
        item.runId: item
        for item in generate_runspecs(experiment, base_dir, experiment_path=experiment_path)
    }


def evaluation_output_paths(
    experiment: Experiment,
    base_dir: Path,
    *,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
) -> tuple[Path, Path | None]:
    target_dir = Path(output_dir).resolve() if output_dir else resolve_eval_output_dir(experiment, base_dir)
    target_jsonl = Path(output_jsonl).resolve() if output_jsonl else resolve_eval_jsonl_path(experiment, base_dir)
    return target_dir, target_jsonl


def build_evaluation_summary_rows(rows: Iterable[dict[str, Any]]) -> EvaluationBatchSummary:
    row_list = list(rows)
    experiment_id = str(row_list[0].get("experimentId", "")) if row_list else ""
    return EvaluationBatchSummary(
        experimentId=experiment_id,
        runCount=len(row_list),
        itemCount=len(row_list),
        questions=[_build_evaluation_question_summary(row) for row in row_list],
    )


def _build_evaluation_question_summary(row: dict[str, Any]) -> dict[str, Any]:
    details = row.get("details", {})
    if not isinstance(details, dict):
        details = {}
    summary: dict[str, Any] = {
        "runId": row.get("runId"),
        "questionId": row.get("questionId"),
        "instanceId": row.get("instanceId"),
        "status": row.get("status"),
        "evaluationMethod": row.get("evaluationMethod"),
    }
    if "outcome" in details:
        summary["outcome"] = details.get("outcome")
    if summary["evaluationMethod"] == "heuristic":
        if "matched" in details:
            summary["matched"] = details.get("matched")
        return summary

    judges = details.get("judges")
    if isinstance(judges, list):
        summary["judgeRatings"] = [
            {
                "provider": item.get("provider"),
                "model": item.get("model"),
                "correctness": item.get("correctness", {}).get("rating")
                if isinstance(item.get("correctness"), dict)
                else None,
                "completeness": item.get("completeness", {}).get("rating")
                if isinstance(item.get("completeness"), dict)
                else None,
                "error": item.get("error"),
            }
            for item in judges
            if isinstance(item, dict)
        ]
    summary["aggregate"] = {
        "correctness": details.get("correctness", {}).get("rating")
        if isinstance(details.get("correctness"), dict)
        else None,
        "completeness": details.get("completeness", {}).get("rating")
        if isinstance(details.get("completeness"), dict)
        else None,
    }
    return summary


def export_evaluation_rows_csv(rows: Iterable[dict[str, Any]], path: str | Path) -> Path:
    row_list = list(rows)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "experimentId",
        "runId",
        "questionId",
        "instanceId",
        "status",
        "evaluationMethod",
        "details",
        "traceRef",
    ]
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in row_list:
            payload = dict(row)
            payload["details"] = json.dumps(payload.get("details", {}), ensure_ascii=False)
            writer.writerow({name: payload.get(name) for name in fieldnames})
    return target
