from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter


class OpenAIModel(ModelAdapter):
    def generate(self, prompt: str, request: AIRequest) -> AIResult:
        return AIResult(
            answer="",
            error=f"OpenAI model adapter for '{request.model_name}' is not configured.",
            raw_response={"prompt_preview": prompt[:200]},
        )
