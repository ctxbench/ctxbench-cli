from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter, ModelInput
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.trace import TraceCollector

DEFAULT_SYSTEM_INSTRUCTION = (
    "You are given a researcher's Lattes CV as context.\n"
    "Answer the question using only the information available in the provided context.\n"
    "Guidelines:\n"
    "- Base your answer strictly on the provided data.\n"
    "- If the answer is not explicitly or implicitly supported by the context, respond with: 'Not enough information.'\n"
    "- Be concise and precise.\n"
    "- Do not make assumptions or use external knowledge.\n"
)


class InlineStrategy(StrategyAdapter):
    def execute(self, model: ModelAdapter, request: AIRequest, trace: TraceCollector) -> AIResult:
        with trace.span("strategy.inline.execute", "strategy.inline.execute"):
            trace.record_steps(1)
            prompt = (
                f"Context format: {request.context_format}\n\n"
                f"Question:\n{request.question}\n\n"
                f"Context:\n{request.context}\n"
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
