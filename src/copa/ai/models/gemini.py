from __future__ import annotations

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter


class GeminiModel(ModelAdapter):
    def generate(self, prompt: str, request: AIRequest) -> AIResult:
        return AIResult(
            answer="",
            error=f"Gemini model adapter for '{request.model_name}' is not configured.",
            raw_response={"prompt_preview": prompt[:200]},
        )
