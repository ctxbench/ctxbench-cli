from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.trace import TraceCollector


class StrategyAdapter:
    def execute(
        self,
        model: ModelAdapter,
        request: AIRequest,
        trace: TraceCollector,
    ) -> AIResult:
        raise NotImplementedError
