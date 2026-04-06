from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.strategies.base import StrategyAdapter


class MCPStrategy(StrategyAdapter):
    def execute(self, model: ModelAdapter, request: AIRequest) -> AIResult:
        return AIResult(
            answer="",
            error=f"Strategy '{request.strategy_name}' is not implemented yet.",
        )
