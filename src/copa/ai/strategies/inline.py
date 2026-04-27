from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter, ModelInput
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.trace import TraceCollector

DEFAULT_SYSTEM_INSTRUCTION = (
    "You are an assistant that answers questions about a researcher using his / her Lattes curriculum as context.\n"
    "Your goal is to produce  accurate, concise and context-grounded answers.\n"
    "Guidelines:\n"
    "- Base your answer strictly on the provided data.\n"
    "- Inform if the provided context isn't enough to answer the question\n"
    "- Be concise and precise.\n"
    "- Do not make assumptions or use external knowledge.\n"
)


class InlineStrategy(StrategyAdapter):
    def execute(self, model: ModelAdapter, request: AIRequest, trace: TraceCollector) -> AIResult:
        with trace.span("strategy.inline.execute", "strategy.inline.execute"):
            trace.record_steps(1)
            prompt = (
                f"# Context:\n{request.context}\n\n"
                f"# Question:\n{request.question}\n"
            )
            trace.metrics.prompt_size_chars = len(prompt)
            model_input = ModelInput(
                system_instruction=request.system_instruction or DEFAULT_SYSTEM_INSTRUCTION,
                prompt=prompt,
            )
            model_response = model.generate(model_input, request, trace=trace)
            trace.record_model_call(
                duration_ms=model_response.duration_ms,
                input_tokens=model_response.input_tokens,
                output_tokens=model_response.output_tokens,
                total_tokens=model_response.total_tokens,
                metadata=model_response.metadata,
            )
            usage = {
                "inputTokens": model_response.input_tokens,
                "outputTokens": model_response.output_tokens,
                "totalTokens": model_response.total_tokens,
            }
            usage = {key: value for key, value in usage.items() if value is not None}
            return AIResult(
                answer=model_response.text,
                raw_response=model_response.raw_response,
                metadata=dict(model_response.metadata),
                usage=usage,
            )
