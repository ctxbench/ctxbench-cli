from __future__ import annotations

from datetime import datetime

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest
from copa.ai.runtime import LocalFunctionRuntime, MCPRuntime
from copa.benchmark.models import EvaluationResult, RunResult, RunTiming, RunTrace, RunSpec
from copa.datasets.lattes.mcp_server import LattesMCPServer
from copa.datasets.lattes.tools import LattesToolService
from copa.dataset.contexts import context_path
from copa.util.clock import utc_now_iso


def execute_runspec(runspec: RunSpec, engine: Engine) -> RunResult:
    from copa.dataset.provider import DatasetProvider

    provider = DatasetProvider.from_dataset(runspec.dataset)
    question = provider.get_question(runspec.questionId)
    question_instance = provider.get_question_instance(runspec.questionId, runspec.contextId)
    context = provider.get_context(runspec.contextId, runspec.format)
    lattes_id = (
        question_instance.lattesId
        if question_instance is not None and isinstance(question_instance.lattesId, str) and question_instance.lattesId
        else runspec.contextId
    )

    request = AIRequest(
        question=question.question,
        context=context,
        provider_name=runspec.provider,
        model_name=str(runspec.params.get("model_name", "")),
        strategy_name=runspec.strategy,
        context_format=runspec.format,
        params=runspec.params,
        metadata={
            "run_id": runspec.runId,
            "runId": runspec.runId,
            "expId": runspec.experimentId,
            "question_id": runspec.questionId,
            "context_id": runspec.contextId,
            "experiment_id": runspec.experimentId,
            "phase": "execution",
            "format": runspec.format,
            "provider": runspec.provider,
            "lattes_id": lattes_id,
            "context_path": str(context_path(runspec.dataset.contexts, runspec.contextId, runspec.format).resolve()),
        },
    )

    started_at = utc_now_iso()
    start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    active_engine = engine
    owned_engine: Engine | None = None
    if runspec.strategy in {"local_function", "local_mcp"}:
        tool_runtime_factories = {}
        if runspec.strategy == "local_function":
            tool_runtime_factories["local_function"] = lambda: LocalFunctionRuntime(
                LattesToolService(contexts_dir=runspec.dataset.contexts)
            )
        if runspec.strategy == "local_mcp":
            tool_runtime_factories["local_mcp"] = lambda: MCPRuntime.for_local_server(
                LattesMCPServer(
                    contexts_dir=runspec.dataset.contexts,
                )
            )
        owned_engine = engine.copy_with_tool_runtime_factories(tool_runtime_factories)
        active_engine = owned_engine
    try:
        ai_result = active_engine.execute(request)
    finally:
        if owned_engine is not None:
            owned_engine.close()
    finished_at = utc_now_iso()
    finish = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))

    trace = RunTrace()
    if runspec.trace.enabled:
        trace.aiTrace = ai_result.trace
        if runspec.trace.save_tool_calls:
            trace.toolCalls = ai_result.tool_calls
        native_mcp = ai_result.metadata.get("native_mcp")
        if isinstance(native_mcp, dict):
            trace.nativeMcp = native_mcp
        server_mcp = ai_result.metadata.get("server_mcp")
        if isinstance(server_mcp, list):
            trace.serverMcp = [item for item in server_mcp if isinstance(item, dict)]
        if runspec.trace.save_raw_response:
            trace.rawResponse = ai_result.raw_response
        if runspec.trace.save_errors:
            trace.error = ai_result.error

    usage = ai_result.usage if runspec.trace.save_usage or ai_result.error else {}
    result = RunResult(
        runId=runspec.runId,
        experimentId=runspec.experimentId,
        dataset=runspec.dataset,
        questionId=runspec.questionId,
        contextId=runspec.contextId,
        provider=runspec.provider,
        modelName=runspec.modelName,
        strategy=runspec.strategy,
        format=runspec.format,
        repeatIndex=runspec.repeatIndex,
        outputRoot=runspec.outputRoot,
        answer=ai_result.answer,
        status="success" if ai_result.error is None else "error",
        errorMessage=ai_result.error,
        timing=RunTiming(
            startedAt=started_at,
            finishedAt=finished_at,
            durationMs=max(0, int((finish - start).total_seconds() * 1000)),
        ),
        usage=usage,
        trace=trace,
        evaluation=EvaluationResult(),
        metadata=runspec.metadata,
    )
    return result
