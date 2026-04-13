from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall


class OpenAIModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest, trace: Any | None = None) -> ModelResponse:
        client = self._create_client()
        payload = self._build_payload(model_input, request)
        started_at = perf_counter()
        response = client.responses.create(**payload)
        duration_ms = max(0, int((perf_counter() - started_at) * 1000))
        input_tokens, output_tokens, total_tokens = self._extract_usage(response)
        return ModelResponse(
            text=self._extract_text(response),
            requested_tool_calls=self._extract_tool_calls(response),
            raw_response=self._normalize_raw_response(response),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            metadata={"provider": "openai", "model": request.model_name},
            continuation_state=self._build_continuation_state(response),
        )

    def _create_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("OpenAI SDK is not installed.") from exc
        return OpenAI(api_key=self.params.get("api_key"))

    def _build_payload(self, model_input: ModelInput, request: AIRequest) -> dict[str, Any]:
        params = self._merged_params(request)
        payload: dict[str, Any] = {
            "model": request.model_name,
            "instructions": model_input.system_instruction,
            "input": self._build_input(model_input),
        }
        if model_input.tools:
            payload["tools"] = [self._serialize_tool(tool) for tool in model_input.tools]
        if "temperature" in params:
            payload["temperature"] = params["temperature"]
        if "max_tokens" in params:
            payload["max_output_tokens"] = params["max_tokens"]
        if "max_output_tokens" in params:
            payload["max_output_tokens"] = params["max_output_tokens"]
        return payload

    def _build_input(self, model_input: ModelInput) -> str | list[dict[str, Any]]:
        if not model_input.continuation_state and not model_input.tool_results:
            return model_input.prompt

        items: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": model_input.prompt}],
            }
        ]
        items.extend(model_input.continuation_state.get("response_output", []))
        items.extend(self._serialize_tool_result(result) for result in model_input.tool_results)
        return items

    def _serialize_tool(self, tool: Any) -> dict[str, Any]:
        return {
            "type": "function",
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        }

    def _serialize_tool_result(self, result: Any) -> dict[str, Any]:
        return {
            "type": "function_call_output",
            "call_id": result.tool_call_id,
            "output": json.dumps(result.content),
        }

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "output_text", None)
        if isinstance(text, str):
            return text
        output = getattr(response, "output", None)
        if isinstance(output, list):
            parts: list[str] = []
            for item in output:
                content = getattr(item, "content", None)
                if not isinstance(content, list):
                    continue
                for block in content:
                    value = getattr(block, "text", None)
                    if isinstance(value, str):
                        parts.append(value)
            if parts:
                return "\n".join(parts).strip()
        return ""

    def _extract_tool_calls(self, response: Any) -> list[ToolCall]:
        output = getattr(response, "output", None)
        if not isinstance(output, list):
            return []
        tool_calls: list[ToolCall] = []
        for item in output:
            item_type = getattr(item, "type", None)
            if item_type != "function_call":
                continue
            raw_arguments = getattr(item, "arguments", "")
            arguments = self._parse_json_arguments(raw_arguments)
            tool_calls.append(
                ToolCall(
                    id=getattr(item, "call_id", None) or getattr(item, "id", None),
                    name=str(getattr(item, "name", "")),
                    arguments=arguments,
                )
            )
        return tool_calls

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
        if hasattr(response, "dict"):
            return response.dict()
        if isinstance(response, list):
            return [self._normalize_raw_response(item) for item in response]
        if isinstance(response, dict):
            return {key: self._normalize_raw_response(value) for key, value in response.items()}
        if hasattr(response, "__dict__"):
            return {
                key: self._normalize_raw_response(value)
                for key, value in vars(response).items()
                if not key.startswith("_")
            }
        return response

    def _build_continuation_state(self, response: Any) -> dict[str, Any]:
        output = getattr(response, "output", None)
        if isinstance(output, list):
            return {"response_output": [self._normalize_raw_response(item) for item in output]}
        return {}

    def _parse_json_arguments(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}

    def _merged_params(self, request: AIRequest) -> dict[str, Any]:
        params = dict(self.params)
        params.update(request.params)
        return params
