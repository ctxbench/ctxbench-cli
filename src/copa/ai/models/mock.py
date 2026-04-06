from __future__ import annotations

import json
import re

from copa.ai.models.base import AIRequest, AIResult, ModelAdapter


class MockModel(ModelAdapter):
    name = "mock"

    def generate(self, prompt: str, request: AIRequest) -> AIResult:
        question_id = request.metadata.get("question_id", "")
        answer = self._extract_answer(request.context, question_id)
        return AIResult(
            answer=answer,
            usage={
                "inputTokens": len(prompt.split()),
                "outputTokens": len(answer.split()),
            },
            raw_response={"prompt_preview": prompt[:200]},
        )

    def _extract_answer(self, context: str, question_id: str) -> str:
        try:
            payload = json.loads(context)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            answers = payload.get("answers")
            if isinstance(answers, dict):
                value = answers.get(question_id)
                if value is not None:
                    return str(value)
        for pattern in [
            rf"^{re.escape(question_id)}\s*=\s*(.+)$",
            rf"^ANSWER\[{re.escape(question_id)}\]\s*:\s*(.+)$",
            r"^ANSWER\s*:\s*(.+)$",
        ]:
            match = re.search(pattern, context, flags=re.MULTILINE)
            if match:
                return match.group(1).strip()
        return "Not enough information."
