from __future__ import annotations

from time import perf_counter
from typing import Any

from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse


class ClaudeModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
        client = self._create_client()
        payload = self._build_payload(model_input, request)
        started_at = perf_counter()
        response = client.messages.create(**payload)
        duration_ms = max(0, int((perf_counter() - started_at) * 1000))
        input_tokens, output_tokens, total_tokens = self._extract_usage(response)
        return ModelResponse(
            text=self._extract_text(response),
            raw_response=self._normalize_raw_response(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            metadata={"provider": "claude", "model": request.model_name},
        )

    def _create_client(self) -> Any:
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Anthropic SDK is not installed.") from exc
        return Anthropic(api_key=self.params.get("api_key"))

    def _build_payload(self, model_input: ModelInput, request: AIRequest) -> dict[str, Any]:
        params = self._merged_params(request)
        payload: dict[str, Any] = {
            "model": request.model_name,
            "system": model_input.system_instruction,
            "messages": [{"role": "user", "content": model_input.prompt}],
            "max_tokens": params.get("max_tokens", 1024),
        }
        if "temperature" in params:
            payload["temperature"] = params["temperature"]
        return payload

    def _extract_text(self, response: Any) -> str:
        content = getattr(response, "content", None)
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                value = getattr(block, "text", None)
                if isinstance(value, str):
                    parts.append(value)
            if parts:
                return "\n".join(parts).strip()
        raise ValueError("Claude response did not contain text output.")

    def _extract_usage(self, response: Any) -> tuple[int | None, int | None, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None, None, None
        input_tokens = getattr(usage, "input_tokens", None)
        output_tokens = getattr(usage, "output_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if total_tokens is None and input_tokens is not None and output_tokens is not None:
            total_tokens = input_tokens + output_tokens
        return input_tokens, output_tokens, total_tokens

    def _normalize_raw_response(self, response: Any) -> Any:
        if hasattr(response, "model_dump"):
            return response.model_dump(mode="json")
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return response

    def _merged_params(self, request: AIRequest) -> dict[str, Any]:
        params = dict(self.params)
        params.update(request.params)
        return params
