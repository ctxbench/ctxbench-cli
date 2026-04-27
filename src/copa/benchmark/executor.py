from __future__ import annotations

from datetime import datetime

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest
from copa.ai.runtime import LocalFunctionRuntime, MCPRuntime
from copa.benchmark.models import EvaluationResult, RunResult, RunTiming, RunTrace, RunSpec
from copa.datasets.lattes.mcp_server import LattesMCPServer
from copa.datasets.lattes.tools import LattesToolService
from copa.util.clock import utc_now_iso


def execute_runspec(runspec: RunSpec, engine: Engine) -> RunResult:
    from copa.dataset.provider import DatasetProvider

    provider = DatasetProvider.from_dataset(runspec.dataset)
    question = provider.get_question(runspec.questionId)
    question_instance = provider.get_question_instance(runspec.questionId, runspec.instanceId)
    context = provider.get_context(runspec.instanceId, runspec.format)
    context_path = provider.get_context_artifact_path(runspec.instanceId, runspec.format)
    instance_dir = provider.get_instance_dir(runspec.instanceId)
    lattes_id = runspec.instanceId
    request_params = dict(runspec.params)
    if question.validation.type == "heuristic" and question.validation.schema:
        request_params["structured_output"] = {
            "name": f"{runspec.questionId}_response",
            "strict": True,
            "schema": question.validation.schema,
        }

    request = AIRequest(
        question=runspec.question or question.question,
        context=context,
        provider_name=runspec.provider,
        model_name=str(runspec.params.get("model_name", "")),
        strategy_name=runspec.strategy,
        context_format=runspec.format,
        params=request_params,
        metadata={
            "run_id": runspec.runId,
            "runId": runspec.runId,
            "expId": runspec.experimentId,
            "question_id": runspec.questionId,
            "instance_id": runspec.instanceId,
            "experiment_id": runspec.experimentId,
            "phase": "execution",
            "format": runspec.format,
            "provider": runspec.provider,
            "lattes_id": lattes_id,
            "instance_dir": str(instance_dir.resolve()),
            "question_tags": list(question.tags),
            "validation_type": question.validation.type,
            "context_path": str(context_path.resolve()),
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
    metrics_summary = _build_metrics_summary(
        ai_trace=trace.aiTrace,
        strategy=runspec.strategy,
    )
    result = RunResult(
        runId=runspec.runId,
        experimentId=runspec.experimentId,
        dataset=runspec.dataset,
        questionId=runspec.questionId,
        question=runspec.question or question.question,
        questionTemplate=runspec.questionTemplate or question.question,
        instanceId=runspec.instanceId,
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
        metricsSummary=metrics_summary,
        trace=trace,
        evaluation=EvaluationResult(),
        metadata=runspec.metadata,
    )
    return result


def _build_metrics_summary(*, ai_trace: dict[str, object], strategy: str) -> dict[str, int | None]:
    metrics = ai_trace.get("metrics", {}) if isinstance(ai_trace, dict) else {}
    if not isinstance(metrics, dict):
        metrics = {}
    summary: dict[str, int | None] = {
        "experiment_duration": _as_int(metrics.get("experiment_duration") or metrics.get("total_duration_ms")),
        "strategy_duration": _as_int(metrics.get("strategy_duration") or metrics.get("strategy_duration_ms")),
        "function_exec_duration": None,
        "tool_exec_duration": None,
        "llm_exec_duration": _as_int(metrics.get("llm_exec_duration") or metrics.get("model_duration_ms")),
        "function_call_count": None,
        "tool_call_count": None,
        "llm_call_count": _as_int(metrics.get("llm_call_count") or metrics.get("model_calls")),
        "prompt_tokens": _as_int(metrics.get("prompt_tokens") or metrics.get("input_tokens")),
        "question_tokens": _as_int(metrics.get("question_tokens")),
        "function_tokens": None,
        "tool_tokens": None,
        "total_llm_tokens": _as_int(metrics.get("total_llm_tokens") or metrics.get("total_tokens")),
    }
    if strategy in {"local_function", "local_mcp"}:
        summary["function_exec_duration"] = _as_int(metrics.get("function_exec_duration") or metrics.get("function_execution_duration_ms"))
        summary["tool_exec_duration"] = summary["function_exec_duration"]
        summary["function_call_count"] = _as_int(metrics.get("function_call_count") or metrics.get("tool_call_count"))
        summary["tool_call_count"] = _as_int(metrics.get("tool_call_count_semantic") or metrics.get("mcp_tool_calls") or metrics.get("tool_call_count"))
    elif strategy == "inline":
        summary["function_exec_duration"] = 0
        summary["tool_exec_duration"] = 0
        summary["function_call_count"] = 0
        summary["tool_call_count"] = 0
    elif strategy == "mcp":
        summary["function_exec_duration"] = None
        summary["tool_exec_duration"] = None
        summary["function_call_count"] = None
        summary["tool_call_count"] = None
        summary["prompt_tokens"] = None
        summary["total_llm_tokens"] = None
    return summary


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None
