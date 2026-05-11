from __future__ import annotations

from ctxbench.ai.models.base import AIRequest, AIResult, ModelAdapter
from ctxbench.ai.trace import TraceCollector


class StrategyAdapter:
    def execute(
        self,
        model: ModelAdapter,
        request: AIRequest,
        trace: TraceCollector,
    ) -> AIResult:
        raise NotImplementedError
