from __future__ import annotations

from time import perf_counter
from typing import Any

from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse


class GeminiModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
        client = self._create_client()
        generation_config = self._build_generation_config(request, model_input)
        started_at = perf_counter()
        response = client.models.generate_content(
            model=request.model_name,
            contents=model_input.prompt,
            config=generation_config or None,
        )
        duration_ms = max(0, int((perf_counter() - started_at) * 1000))
        input_tokens, output_tokens, total_tokens = self._extract_usage(response)
        return ModelResponse(
            text=self._extract_text(response),
            raw_response=self._normalize_raw_response(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            metadata={"provider": "gemini", "model": request.model_name},
        )

    def _create_client(self) -> Any:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Gemini SDK is not installed.") from exc
        return genai.Client(api_key=self.params.get("api_key"))

    def _build_generation_config(self, request: AIRequest, model_input: ModelInput) -> dict[str, Any]:
        params = self._merged_params(request)
        config: dict[str, Any] = {"system_instruction": model_input.system_instruction}
        if "temperature" in params:
            config["temperature"] = params["temperature"]
        if "max_tokens" in params:
            config["max_output_tokens"] = params["max_tokens"]
        if "max_output_tokens" in params:
            config["max_output_tokens"] = params["max_output_tokens"]
        return config

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, list):
            parts: list[str] = []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts_list = getattr(content, "parts", None)
                if not isinstance(parts_list, list):
                    continue
                for part in parts_list:
                    value = getattr(part, "text", None)
                    if isinstance(value, str):
                        parts.append(value)
            if parts:
                return "\n".join(parts).strip()
        raise ValueError("Gemini response did not contain text output.")

    def _extract_usage(self, response: Any) -> tuple[int | None, int | None, int | None]:
        usage = getattr(response, "usage_metadata", None)
        if usage is None:
            return None, None, None
        input_tokens = getattr(usage, "prompt_token_count", None)
        output_tokens = getattr(usage, "candidates_token_count", None)
        total_tokens = getattr(usage, "total_token_count", None)
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
