from __future__ import annotations

from datetime import datetime

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest
from copa.benchmark.evaluation import evaluate_result
from copa.benchmark.models import EvaluationResult, RunResult, RunTiming, RunTrace, RunSpec
from copa.dataset.provider import DatasetProvider
from copa.util.clock import utc_now_iso


def execute_runspec(runspec: RunSpec, engine: Engine) -> RunResult:
    provider = DatasetProvider.from_dataset(runspec.dataset)
    question = provider.get_question(runspec.questionId)
    context = provider.get_context(runspec.contextId, runspec.format)

    request = AIRequest(
        question=question.question,
        context=context,
        provider_name=runspec.provider,
        model_name=str(runspec.params.get("model_name", "")),
        strategy_name=runspec.strategy,
        context_format=runspec.format,
        params=runspec.params,
        metadata={
            "question_id": runspec.questionId,
            "context_id": runspec.contextId,
            "experiment_id": runspec.experimentId,
            "format": runspec.format,
            "provider": runspec.provider,
        },
    )

    started_at = utc_now_iso()
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    ai_result = engine.execute(request)
    finished_at = utc_now_iso()
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))

    trace = RunTrace()
    if runspec.trace.enabled:
        trace.aiTrace = ai_result.trace
        if runspec.trace.save_tool_calls:
            trace.toolCalls = ai_result.tool_calls
        if runspec.trace.save_raw_response:
            trace.rawResponse = ai_result.raw_response
        if runspec.trace.save_errors:
            trace.error = ai_result.error

    usage = ai_result.usage if runspec.trace.save_usage or ai_result.error else {}
    result = RunResult(
        runId=runspec.id,
        experimentId=runspec.experimentId,
        dataset=runspec.dataset,
        questionId=runspec.questionId,
        contextId=runspec.contextId,
        provider=runspec.provider,
        strategy=runspec.strategy,
        format=runspec.format,
        repeatIndex=runspec.repeatIndex,
        outputRoot=runspec.outputRoot,
        answer=ai_result.answer,
        status="success" if ai_result.error is None else "error",
        timing=RunTiming(
            startedAt=started_at,
            finishedAt=finished_at,
            durationMs=max(0, int((finish - start).total_seconds() * 1000)),
        ),
        usage=usage,
        trace=trace,
        evaluation=EvaluationResult(),
    )
    if runspec.evaluationEnabled:
        result.evaluation = evaluate_result(result, provider)
    return result
