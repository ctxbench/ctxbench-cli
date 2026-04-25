from __future__ import annotations

import csv
import json
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
    "Use only the provided question, answer, context and themes.\n"
    "Do not use external knowledge.\n"
    "Return only the requested JSON."
)

JUDGE_PROMPT = """You are an evaluation assistant for a benchmark. Your task is to evaluate an answer given by a model based strictly on the provided context and criteria.
You must be objective, consistent, and conservative in your evaluation.
Do NOT use external knowledge. Only use the provided context and themes.
Your output must strictly follow the requested JSON format.
Evaluate the answer to the question based on the provided context.

# Question
{question}

# Answer
{answer}

# Context
{context_blocks}

# Themes
{themes}

# Evaluation Scale

Use the following scale for ALL criteria:

- "meets": fully satisfies the criterion
- "partially meets": partially satisfies the criterion, with minor issues or omissions
- "does not meet": does not satisfy the criterion or has major issues

# Evaluation Criteria

## Groundedness
The answer must be fully supported by the provided context.
- Check whether all claims are grounded in the context.
- Penalize any hallucinations or unsupported assumptions.
- Themes MUST NOT be used to justify groundedness.

## Correctness
The answer must be factually correct according to the context.
- Check whether the information provided is accurate.
- Use the context as the primary source of truth.
- Themes can help identify expected subject areas, but MUST NOT override the context.

## Completeness
The answer must fully address the question.
- Check whether all parts of the question are answered.
- Use the themes to verify whether important aspects or topics are covered.
- Penalize missing relevant topics suggested by the themes.

# Important Rules
- Base your evaluation ONLY on the provided context and themes.
- Context is the source of truth.
- Themes are supportive hints, not factual evidence.
- Do NOT assume missing information.
- Be strict: if unsure, prefer "partially meets" or "does not meet".
- Each criterion MUST include a short justification grounded in the provided context and/or themes.
- Do NOT include chain-of-thought or hidden reasoning. Provide only concise criterion justifications.

# Output Format (STRICT JSON)
Return ONLY a JSON object in the following format:

{{
  "groundedness": {{
    "rating": "meets | partially meets | does not meet",
    "justification": "short justification"
  }},
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


def _normalize_text(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


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
    matched = normalized_answer in normalized_candidates
    return {
        "acceptedAnswers": accepted_answers,
        "schema": schema,
        "evaluationMethod": "heuristic",
        "matched": matched,
        "outcome": "accepted" if matched else "rejected",
        "parsedAnswer": parsed_answer,
        "normalizedAnswer": normalized_answer,
    }


def _filter_context_blocks(blocks: dict[str, object], refs: list[str]) -> dict[str, object]:
    if not refs:
        return blocks
    return {key: value for key, value in blocks.items() if key in refs}


def _judge_request(
    *,
    config: EvaluationModelConfig,
    prompt: str,
    run_id: str,
    exp_id: str,
    engine: Engine,
) -> tuple[dict[str, Any] | None, EvaluationJudgeInfo, EvaluationTrace]:
    request = AIRequest(
        question=prompt,
        context="{}",
        provider_name=config.provider,
        model_name=config.model,
        strategy_name="inline",
        context_format="text",
        system_instruction=EVALUATION_SYSTEM_INSTRUCTION,
        params={
            "temperature": config.temperature,
            **config.params,
        },
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
    blocks: dict[str, object],
    refs: list[str],
    themes: list[str],
    experiment: Experiment,
    engine: Engine,
) -> tuple[dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    if experiment.evaluation.judge is None:
        return {
            "evaluationMethod": "judge",
            "error": "Experiment evaluation.judge is required for judge validation.",
        }, EvaluationJudgeInfo(), EvaluationTrace()
    filtered_blocks = _filter_context_blocks(blocks, refs)
    prompt = JUDGE_PROMPT.format(
        question=question_text,
        answer=result.answer,
        context_blocks=json.dumps(filtered_blocks, ensure_ascii=False, indent=2),
        themes=json.dumps(themes, ensure_ascii=False, indent=2),
    )
    payload, judge_info, trace = _judge_request(
        config=experiment.evaluation.judge,
        prompt=prompt,
        run_id=result.runId,
        exp_id=result.experimentId,
        engine=engine,
    )
    if payload is None:
        return {
            "evaluationMethod": "judge",
            "contextRefs": refs,
            "themes": themes,
            "error": "Judge did not return valid JSON.",
        }, judge_info, trace
    groundedness = _criterion_payload(payload.get("groundedness"))
    correctness = _criterion_payload(payload.get("correctness"))
    completeness = _criterion_payload(payload.get("completeness"))
    summary = "meets"
    ratings = (
        groundedness["rating"],
        correctness["rating"],
        completeness["rating"],
    )
    if any(item == "does not meet" for item in ratings):
        summary = "does_not_meet"
    elif any(item == "partially meets" for item in ratings):
        summary = "partially_meets"
    return {
        "evaluationMethod": "judge",
        "contextRefs": refs,
        "themes": themes,
        "groundedness": groundedness,
        "correctness": correctness,
        "completeness": completeness,
        "outcome": summary,
        "qualitativeSummary": {
            "meetsCount": sum(1 for item in ratings if item == "meets"),
            "partialCount": sum(1 for item in ratings if item == "partially meets"),
            "doesNotMeetCount": sum(1 for item in ratings if item == "does not meet"),
        },
    }, judge_info, trace


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
        blocks = provider.get_context_blocks(result.instanceId)
        details, judge_info, trace = _evaluate_judge(
            result,
            question.question,
            blocks,
            list(instance_question.contextRefs),
            list(instance_question.themes),
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
        question=question.question,
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
    )


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
