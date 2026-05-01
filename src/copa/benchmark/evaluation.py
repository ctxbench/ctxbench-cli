from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from copa.ai.cache import build_judge_prompt_cache_key
from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelInput
from copa.benchmark.models import (
    EvaluationBatchSummary,
    EvaluationItemResult,
    EvaluationJudgeInfo,
    EvaluationModelConfig,
    EvaluationRunResult,
    EvaluationRunSummary,
    EvaluationTrace,
    RunResult,
)
from copa.dataset.provider import DatasetProvider

EVALUATION_SYSTEM_INSTRUCTION = (
    "You are evaluating benchmark answers.\n"
    "Use only the provided question, answer and curriculum context.\n"
    "Do not use external knowledge.\n"
    "Return only the requested JSON."
)

JUDGE_PROMPT = """You are an evaluation assistant for a benchmark. Your task is to evaluate an answer given by a model based strictly on the provided curriculum context and criteria.
You must be objective, consistent, and conservative in your evaluation.
Do NOT use external knowledge. Only use the provided curriculum context.
Your output must strictly follow the requested JSON format.
Evaluate the answer to the question based on the provided curriculum context.

# Evaluation Instructions
- Use only the provided curriculum context.
- If the curriculum context is silent about something, treat that as missing support.
- Be strict: if unsure, prefer "partially meets" or "does not meet".
- Each criterion MUST include a short justification grounded in the provided curriculum context.
- Do NOT include chain-of-thought or hidden reasoning. Provide only concise criterion justifications.

# Evaluation Scale

Use the following scale for ALL criteria:

- "meets": fully satisfies the criterion
- "partially meets": partially satisfies the criterion, with minor issues or omissions
- "does not meet": does not satisfy the criterion or has major issues

# Evaluation Criteria

## Correctness
The answer must be factually correct according to the curriculum context.
- Check whether the information provided is accurate.
- Use the curriculum context as the source of truth.

## Completeness
The answer must fully address the question.
- Check whether all parts of the question are answered.
- Penalize important omissions relative to the curriculum context.

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

# Curriculum Context
{curriculum_context}

# Question
{question}

# Candidate Answer
{answer}

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


@dataclass(frozen=True)
class EvaluationJob:
    custom_id: str
    result: RunResult
    judge: EvaluationModelConfig
    prompt: str
    question_text: str
    context_payload: dict[str, Any]
    curriculum_context: str


def judge_identifier(config: EvaluationModelConfig) -> str:
    for key in ("id", "judgeId", "judge_id", "name"):
        value = config.params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return f"{config.provider}:{config.model}"


def batch_custom_id(result: RunResult, judge: EvaluationModelConfig) -> str:
    judge_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", judge_identifier(judge)).strip("-_")
    if not judge_slug:
        judge_slug = "judge"
    return f"{result.runId}-{judge_slug}"[:64]


def build_evaluation_job(
    result: RunResult,
    provider: DatasetProvider,
    *,
    judge: EvaluationModelConfig,
    only: str | None = None,
    mode: str | None = None,
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
) -> EvaluationJob | None:
    if result.status != "success":
        return None
    if only and result.questionId != only:
        return None

    rendered_question = result.question
    validation_type = result.validationType or result.metadata.validationType
    if mode and validation_type != mode:
        return None
    if validation_type != "judge":
        raise ValueError(f"Unsupported validation type: {validation_type}")

    blocks = provider.get_context_blocks(result.instanceId)
    context_payload, found = _get_question_block(blocks, result.questionId)
    if not found and event_logger is not None:
        event_logger(
            "WARN",
            "Context block not found for question; evaluation may be inaccurate",
            {
                "runId": result.runId,
                "questionId": result.questionId,
                "instanceId": result.instanceId,
            },
        )
    curriculum_context = _format_curriculum_context(context_payload)
    prompt = JUDGE_PROMPT.format(
        question=rendered_question,
        answer=result.answer,
        curriculum_context=curriculum_context,
    )
    return EvaluationJob(
        custom_id=batch_custom_id(result, judge),
        result=result,
        judge=judge,
        prompt=prompt,
        question_text=rendered_question,
        context_payload=context_payload,
        curriculum_context=curriculum_context,
    )


def build_evaluation_jobs(
    results: Iterable[RunResult],
    *,
    judges: list[EvaluationModelConfig],
    only: str | None = None,
    mode: str | None = None,
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
) -> list[EvaluationJob]:
    provider_cache: dict[str, DatasetProvider] = {}
    jobs: list[EvaluationJob] = []
    ordered_results = sorted(
        list(results),
        key=lambda item: (
            str(item.provider),
            str(item.modelName or ""),
            str(item.instanceId),
            str(item.questionId),
            str(item.runId),
        ),
    )
    for result in ordered_results:
        provider = provider_cache.setdefault(
            result.dataset.root,
            DatasetProvider.from_dataset(result.dataset),
        )
        for judge in judges:
            job = build_evaluation_job(
                result,
                provider,
                judge=judge,
                only=only,
                mode=mode,
                event_logger=event_logger,
            )
            if job is not None:
                jobs.append(job)
    return jobs


def _judge_request(
    *,
    config: EvaluationModelConfig,
    prompt: str,
    run_id: str,
    exp_id: str,
    instance_id: str,
    question_id: str,
    question_text: str,
    curriculum_context: str,
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
    if config.provider.lower().startswith("openai"):
        request_params.setdefault(
            "prompt_cache_key",
            build_judge_prompt_cache_key(
                model_name=config.model,
                instance_id=instance_id,
                question_id=question_id,
                context=curriculum_context,
                question=question_text,
            ),
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
        durationMs=metrics.get("totalDurationMs"),
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
    context_payload: dict[str, Any],
    judges: list[EvaluationModelConfig],
    engine: Engine,
) -> tuple[dict[str, Any], EvaluationJudgeInfo, EvaluationTrace]:
    if not judges:
        return {
            "evaluationMethod": "judge",
            "error": "Experiment evaluation.judges is required for judge validation.",
        }, EvaluationJudgeInfo(), EvaluationTrace()
    curriculum_context = _format_curriculum_context(context_payload)
    prompt = JUDGE_PROMPT.format(
        question=question_text,
        answer=result.answer,
        curriculum_context=curriculum_context,
    )
    judge_votes: list[dict[str, Any]] = []
    judge_infos: list[EvaluationJudgeInfo] = []
    traces: list[EvaluationTrace] = []
    valid_votes: list[dict[str, Any]] = []
    for config in judges:
        payload, judge_info, trace = _judge_request(
            config=config,
            prompt=prompt,
            run_id=result.runId,
            exp_id=result.experimentId,
            instance_id=result.instanceId,
            question_id=result.questionId,
            question_text=question_text,
            curriculum_context=curriculum_context,
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
            "contextBlock": list(context_payload.keys()),
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
        "contextBlock": list(context_payload.keys()),
        "judges": judge_votes,
        "correctness": correctness,
        "completeness": completeness,
        "outcome": summary,
    }, merged_info, merged_trace


def evaluation_from_judge_payload(
    job: EvaluationJob,
    *,
    payload: dict[str, Any] | None,
    judge_info: EvaluationJudgeInfo,
    trace: EvaluationTrace,
) -> EvaluationRunResult:
    if payload is None:
        details = {
            "evaluationMethod": "judge",
            "contextBlock": list(job.context_payload.keys()),
            "judges": [
                {
                    "provider": job.judge.provider,
                    "model": job.judge.model,
                    "error": "Judge did not return valid JSON.",
                }
            ],
            "error": "Judge did not return valid JSON.",
        }
    else:
        correctness = _criterion_payload(payload.get("correctness"))
        completeness = _criterion_payload(payload.get("completeness"))
        vote = {
            "provider": job.judge.provider,
            "model": job.judge.model,
            "correctness": correctness,
            "completeness": completeness,
        }
        aggregate_correctness = _aggregate_votes([vote], "correctness")
        aggregate_completeness = _aggregate_votes([vote], "completeness")
        details = {
            "evaluationMethod": "judge",
            "contextBlock": list(job.context_payload.keys()),
            "judges": [vote],
            "correctness": aggregate_correctness,
            "completeness": aggregate_completeness,
            "outcome": _outcome_from_ratings(
                aggregate_correctness["rating"],
                aggregate_completeness["rating"],
            ),
        }
    return _build_evaluation_result(
        job.result,
        question_text=job.question_text,
        validation_type="judge",
        details=details,
        judge_info=judge_info,
        trace=trace,
    )


def _build_evaluation_result(
    result: RunResult,
    *,
    question_text: str,
    validation_type: str,
    details: dict[str, Any],
    judge_info: EvaluationJudgeInfo,
    trace: EvaluationTrace,
) -> EvaluationRunResult:
    metrics = result.trace.aiTrace.get("metrics", {}) if result.trace.aiTrace else {}
    summary = result.metricsSummary
    context_block = details.get("contextBlock") if isinstance(details, dict) else None
    item = EvaluationItemResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        instanceId=result.instanceId,
        question=question_text,
        evaluationMode=validation_type,
        status="evaluated",
        evaluationMethod=details.get("evaluationMethod"),
        details=details,
        contextBlock=context_block if isinstance(context_block, list) and context_block else None,
        executionModel=result.modelName,
        executionStrategy=result.strategy,
        executionFormat=result.format,
        executionInputTokens=result.usage.get("inputTokens"),
        executionOutputTokens=result.usage.get("outputTokens"),
        executionDurationMs=result.timing.durationMs,
        executionToolCalls=summary.get("toolCalls", metrics.get("toolCalls")),
        executionFunctionCalls=summary.get("functionCalls", metrics.get("functionCalls")),
        executionLlmCalls=summary.get("modelCalls", metrics.get("modelCalls")),
        questionTags=list(result.questionTags),
        evaluationJudgeUsed=judge_info.used,
        evaluationJudgeRole=judge_info.role,
        evaluationJudgeProvider=judge_info.provider,
        evaluationJudgeModel=judge_info.model,
        evaluationInputTokens=judge_info.inputTokens,
        evaluationOutputTokens=judge_info.outputTokens,
        evaluationDurationMs=judge_info.durationMs,
        evaluationTrace=trace,
    )
    return EvaluationRunResult(
        experimentId=result.experimentId,
        runId=result.runId,
        questionId=result.questionId,
        items=[item],
        summary=EvaluationRunSummary(itemCount=1),
        metadata=result.metadata,
    )


def _get_question_block(blocks: dict[str, Any], question_id: str) -> tuple[dict[str, Any], bool]:
    inner = blocks.get("blocks", {})
    if not isinstance(inner, dict):
        return {}, False
    block = inner.get(question_id)
    if block is None:
        return {}, False
    return {question_id: block}, True


def _format_curriculum_context(context_payload: dict[str, Any]) -> str:
    if not context_payload:
        return ""
    parts: list[str] = []
    for block_id, block in context_payload.items():
        if isinstance(block, dict):
            title = block.get("title", block_id)
            summary = block.get("summary", "")
            parts.append(f"## {title}\n{summary}")
        else:
            parts.append(str(block))
    return "\n\n".join(parts)


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
    *,
    judges: list[EvaluationModelConfig],
    only: str | None = None,
    mode: str | None = None,
    engine: Engine | None = None,
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
) -> EvaluationRunResult | None:
    if result.status != "success":
        return None
    if only and result.questionId != only:
        return None

    rendered_question = result.question
    validation_type = result.validationType or result.metadata.validationType
    if mode and validation_type != mode:
        return None
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
    if validation_type == "judge":
        blocks = provider.get_context_blocks(result.instanceId)
        context_payload, found = _get_question_block(blocks, result.questionId)
        if not found and event_logger is not None:
            event_logger(
                "WARN",
                "Context block not found for question; evaluation may be inaccurate",
                {
                    "runId": result.runId,
                    "questionId": result.questionId,
                    "instanceId": result.instanceId,
                },
            )
        details, judge_info, trace = _evaluate_judge(
            result,
            rendered_question,
            context_payload,
            judges,
            active_engine,
        )
    else:
        raise ValueError(f"Unsupported validation type: {validation_type}")

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
    return _build_evaluation_result(
        result,
        question_text=rendered_question,
        validation_type=validation_type,
        details=details,
        judge_info=judge_info,
        trace=trace,
    )


def evaluate_run_results(
    results: Iterable[RunResult],
    *,
    judges: list[EvaluationModelConfig],
    only: str | None = None,
    mode: str | None = None,
    continue_on_error: bool = False,
    event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
    on_result: Callable[[RunResult, EvaluationRunResult | None], None] | None = None,
) -> list[EvaluationRunResult]:
    provider_cache: dict[str, DatasetProvider] = {}
    engine = Engine(event_logger=event_logger)
    evaluations: list[EvaluationRunResult] = []
    ordered_results = sorted(
        list(results),
        key=lambda item: (
            str(item.provider),
            str(item.modelName or ""),
            str(item.instanceId),
            str(item.questionId),
            str(item.runId),
        ),
    )
    try:
        for result in ordered_results:
            try:
                evaluated = evaluate_run_result(
                    result,
                    provider_cache.setdefault(
                        result.dataset.root,
                        DatasetProvider.from_dataset(result.dataset),
                    ),
                    judges=judges,
                    only=only,
                    mode=mode,
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
    if row.get("outcome") is not None:
        summary["outcome"] = row.get("outcome")
    elif "outcome" in details:
        summary["outcome"] = details.get("outcome")
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
        "correctness": row.get("correctness")
        or (
            details.get("correctness", {}).get("rating")
            if isinstance(details.get("correctness"), dict)
            else None
        ),
        "completeness": row.get("completeness")
        or (
            details.get("completeness", {}).get("rating")
            if isinstance(details.get("completeness"), dict)
            else None
        ),
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
        "outcome",
        "correctness",
        "completeness",
        "judgeProvider",
        "judgeModel",
        "evaluationInputTokens",
        "evaluationOutputTokens",
        "evaluationDurationMs",
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
