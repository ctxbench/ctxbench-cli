from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.models.claude import ClaudeModel
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.mock import MockModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.strategies.inline import InlineStrategy
from copa.ai.strategies.mcp import MCPStrategy
from copa.ai.trace import TraceCollector


class Engine:
    def __init__(self) -> None:
        self._models: dict[str, ModelAdapter] = {
            "mock": MockModel(),
            "echo": MockModel(),
        }
        self._strategies: dict[str, StrategyAdapter] = {
            "inline": InlineStrategy(),
            "mcp": MCPStrategy(),
        }

    def execute(self, request: AIRequest) -> AIResult:
        trace = TraceCollector()
        trace.metrics.context_size_chars = len(request.context)
        trace.metrics.context_size_bytes = len(request.context.encode("utf-8"))
        trace.metrics.question_size_chars = len(request.question)
        try:
            with trace.span("engine", "engine.execute"):
                model = self._resolve_model(request.provider_name, request.params)
                strategy = self._resolve_strategy(request.strategy_name)
                result = strategy.execute(model, request, trace)
        except Exception as exc:
            trace.record_error(
                str(exc),
                metadata={
                    "provider_name": request.provider_name,
                    "model_name": request.model_name,
                    "strategy_name": request.strategy_name,
                },
            )
            result = AIResult(answer="", error=str(exc))
        result.trace = trace.to_trace().model_dump(mode="json")
        return result

    def _resolve_model(self, name: str, params: dict[str, object] | None = None) -> ModelAdapter:
        if name in self._models:
            return self._models[name]
        lowered = name.lower()
        if lowered.startswith("gpt") or lowered.startswith("openai"):
            return OpenAIModel(params=params)
        if lowered.startswith("gemini") or lowered.startswith("google"):
            return GeminiModel(params=params)
        if lowered.startswith("claude") or lowered.startswith("anthropic"):
            return ClaudeModel(params=params)
        return MockModel(params=params)

    def _resolve_strategy(self, name: str) -> StrategyAdapter:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unknown strategy: {name}")
        return strategy
