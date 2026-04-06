from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.trace import TraceCollector


class MCPStrategy(StrategyAdapter):
    def execute(self, model: ModelAdapter, request: AIRequest, trace: TraceCollector) -> AIResult:
        return AIResult(
            answer="",
            error=f"Strategy '{request.strategy_name}' is not implemented yet.",
        )
