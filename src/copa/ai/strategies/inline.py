from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.strategies.base import StrategyAdapter


class InlineStrategy(StrategyAdapter):
    def execute(self, model: ModelAdapter, request: AIRequest) -> AIResult:
        prompt = (
            "Answer the question using only the provided context.\n"
            f"Context:\n{request.context}\n\n"
            f"Question:\n{request.question}\n"
        )
        return model.generate(prompt, request)
