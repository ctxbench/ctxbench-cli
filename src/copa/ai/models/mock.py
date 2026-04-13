from __future__ import annotations

import json
import re

from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse


class MockModel(ModelAdapter):
    name = "mock"

    def generate(self, model_input: ModelInput, request: AIRequest, trace: object | None = None) -> ModelResponse:
        question_id = request.metadata.get("question_id", "")
        answer = self._extract_answer(request.context, question_id)
        input_tokens = len(model_input.prompt.split())
        output_tokens = len(answer.split())
        return ModelResponse(
            text=answer,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            duration_ms=0,
            raw_response={
                "system_instruction_preview": model_input.system_instruction[:200],
                "prompt_preview": model_input.prompt[:200],
            },
            metadata={"provider": "mock"},
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
