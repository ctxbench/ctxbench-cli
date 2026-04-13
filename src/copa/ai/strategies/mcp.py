from __future__ import annotations

from copa.ai.mcp.runtime import MCPRuntime
from copa.ai.models.base import AIRequest, AIResult, ModelAdapter, ModelInput, ToolResult
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.trace import TraceCollector

DEFAULT_MCP_SYSTEM_INSTRUCTION = (
"You are answering questions about a researcher.\n"
"You have access to relevant information about the researcher.\n"
"Guidelines:\n"
"- Use only the available information to answer the question.\n"
"- If the information is insufficient, respond with: 'Not enough information.'\n"
"- Be concise and precise.\n"
"- Do not make assumptions or use external knowledge.\n"
)


class MCPStrategy(StrategyAdapter):
    def __init__(self, runtime: MCPRuntime) -> None:
        self.runtime = runtime

    def execute(self, model: ModelAdapter, request: AIRequest, trace: TraceCollector) -> AIResult:
        max_steps = int(request.params.get("max_steps", 8))
        tool_results: list[ToolResult] = []
        previous_tool_calls = []
        continuation_state: dict[str, object] = {}
        tool_call_log: list[dict[str, object]] = []
        raw_responses: list[object] = []

        with trace.span("strategy.mcp.execute", "strategy.mcp.execute"):
            self.runtime.bind(request)
            tools = self.runtime.list_tools()
            prompt = (
                f"Question:\n{request.question}\n"
            )
            trace.metrics.prompt_size_chars = len(prompt)

            for step in range(max_steps):
                model_input = ModelInput(
                    system_instruction=DEFAULT_MCP_SYSTEM_INSTRUCTION,
                    prompt=prompt,
                    tools=tools,
                    previous_tool_calls=previous_tool_calls,
                    tool_results=tool_results,
                    continuation_state=continuation_state,
                )
                model_response = model.generate(model_input, request, trace=trace)
                raw_responses.append(model_response.raw_response)
                continuation_state = dict(model_response.continuation_state)
                trace.record_model_call(
                    duration_ms=model_response.duration_ms,
                    input_tokens=model_response.input_tokens,
                    output_tokens=model_response.output_tokens,
                    total_tokens=model_response.total_tokens,
                    metadata=model_response.metadata,
                )
                if not model_response.requested_tool_calls:
                    usage = {
                        "inputTokens": trace.metrics.input_tokens,
                        "outputTokens": trace.metrics.output_tokens,
                        "totalTokens": trace.metrics.total_tokens,
                    }
                    usage = {key: value for key, value in usage.items() if value is not None}
                    return AIResult(
                        answer=model_response.text,
                        raw_response=raw_responses[-1] if len(raw_responses) == 1 else raw_responses,
                        metadata={"steps": step + 1, **dict(model_response.metadata)},
                        usage=usage,
                        tool_calls=tool_call_log,
                    )

                current_results: list[ToolResult] = []
                for call_index, tool_call in enumerate(model_response.requested_tool_calls, start=1):
                    tool_call_id = tool_call.id or f"step-{step + 1}-tool-{call_index}"
                    trace.record_tool_call(name=tool_call.name, arguments=tool_call.arguments)
                    tool_result = self.runtime.call_tool(tool_call.name, tool_call.arguments)
                    normalized_result = tool_result.model_copy(update={"tool_call_id": tool_call_id})
                    current_results.append(normalized_result)
                    tool_call_log.append(
                        {
                            "id": tool_call_id,
                            "name": tool_call.name,
                            "arguments": dict(tool_call.arguments),
                            "result": normalized_result.content,
                            "isError": normalized_result.is_error,
                        }
                    )
                    trace.record_tool_result(
                        name=normalized_result.name,
                        result=normalized_result.content,
                        is_error=normalized_result.is_error,
                        metadata=normalized_result.metadata,
                    )
                previous_tool_calls = list(model_response.requested_tool_calls)
                tool_results = current_results

        error = f"MCP strategy exceeded max_steps={max_steps}."
        trace.record_error(error, metadata={"strategy_name": request.strategy_name, "max_steps": max_steps})
        return AIResult(
            answer="",
            error=error,
            metadata={"max_steps": max_steps},
            tool_calls=tool_call_log,
        )
