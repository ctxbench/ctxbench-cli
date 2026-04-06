from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter


class StrategyAdapter:
    def execute(self, model: ModelAdapter, request: AIRequest) -> AIResult:
        raise NotImplementedError
