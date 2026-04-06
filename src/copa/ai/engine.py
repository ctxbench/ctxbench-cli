from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.mock import MockModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.strategies.inline import InlineStrategy
from copa.ai.strategies.mcp import MCPStrategy


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
        model = self._resolve_model(request.model_name)
        strategy = self._resolve_strategy(request.strategy_name)
        return strategy.execute(model, request)

    def _resolve_model(self, name: str) -> ModelAdapter:
        if name in self._models:
            return self._models[name]
        lowered = name.lower()
        if lowered.startswith("gpt") or lowered.startswith("openai"):
            return OpenAIModel()
        if lowered.startswith("gemini"):
            return GeminiModel()
        return MockModel()

    def _resolve_strategy(self, name: str) -> StrategyAdapter:
        strategy = self._strategies.get(name)
        if strategy is None:
            raise ValueError(f"Unknown strategy: {name}")
        return strategy
