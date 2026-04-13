from __future__ import annotations

from time import perf_counter
from typing import Any

from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall


class GeminiModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest, trace: Any | None = None) -> ModelResponse:
        client = self._create_client()
        generation_config = self._build_generation_config(request, model_input)
        started_at = perf_counter()
        response = client.models.generate_content(
            model=request.model_name,
            contents=self._build_contents(model_input),
            config=generation_config or None,
        )
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
            metadata={"provider": "gemini", "model": request.model_name},
            continuation_state=self._build_continuation_state(response),
        )

    def _create_client(self) -> Any:
        try:
            from google import genai
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Gemini SDK is not installed.") from exc
        return genai.Client(api_key=self.params.get("api_key"))

    def _build_generation_config(self, request: AIRequest, model_input: ModelInput) -> Any:
        params = self._merged_params(request)
        sdk_types = self._sdk_types()
        config: dict[str, Any] = {"system_instruction": model_input.system_instruction}
        labels = self._request_labels(request)
        if labels:
            config["labels"] = labels
        if model_input.tools:
            if sdk_types is None:
                config["tools"] = [
                    {
                        "function_declarations": [
                            {
                                "name": tool.name,
                                "description": tool.description,
                                "parameters_json_schema": tool.input_schema,
                            }
                            for tool in model_input.tools
                        ]
                    }
                ]
                config["automatic_function_calling"] = {"disable": True}
            else:
                declarations = [
                    sdk_types.FunctionDeclaration(
                        name=tool.name,
                        description=tool.description,
                        parameters_json_schema=tool.input_schema,
                    )
                    for tool in model_input.tools
                ]
                config["tools"] = [sdk_types.Tool(function_declarations=declarations)]
                config["automatic_function_calling"] = sdk_types.AutomaticFunctionCallingConfig(disable=True)
        if "temperature" in params:
            config["temperature"] = params["temperature"]
        if "max_tokens" in params:
            config["max_output_tokens"] = params["max_tokens"]
        if "max_output_tokens" in params:
            config["max_output_tokens"] = params["max_output_tokens"]
        if sdk_types is None:
            return config
        return sdk_types.GenerateContentConfig(**config)

    def _build_contents(self, model_input: ModelInput) -> Any:
        if not model_input.previous_tool_calls and not model_input.tool_results and not model_input.continuation_state:
            return model_input.prompt

        sdk_types = self._sdk_types()
        contents: list[Any] = [self._user_text_content(model_input.prompt, sdk_types)]
        model_content = model_input.continuation_state.get("model_content")
        if model_content is not None and not isinstance(model_content, dict):
            contents.append(model_content)
        elif isinstance(model_content, dict):
            contents.append(self._sdk_content_from_dict(model_content, sdk_types))
        elif model_input.previous_tool_calls:
            if sdk_types is None:
                contents.append(
                    {
                        "role": "model",
                        "parts": [
                            {
                                "functionCall": {
                                    "name": tool_call.name,
                                    "args": tool_call.arguments,
                                }
                            }
                            for tool_call in model_input.previous_tool_calls
                        ],
                    }
                )
            else:
                contents.append(
                    sdk_types.Content(
                        role="model",
                        parts=[
                            sdk_types.Part(
                                function_call=sdk_types.FunctionCall(
                                    name=tool_call.name,
                                    args=tool_call.arguments,
                                    id=tool_call.id,
                                )
                            )
                            for tool_call in model_input.previous_tool_calls
                        ],
                    )
                )
        if model_input.tool_results:
            if sdk_types is None:
                contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "functionResponse": {
                                    "name": result.name,
                                    "id": result.tool_call_id,
                                    "response": {"result": result.content},
                                }
                            }
                            for result in model_input.tool_results
                        ],
                    }
                )
            else:
                contents.append(
                    sdk_types.Content(
                        role="user",
                        parts=[
                            sdk_types.Part(
                                function_response=sdk_types.FunctionResponse(
                                    name=result.name,
                                    id=result.tool_call_id,
                                    response={"result": result.content},
                                )
                            )
                            for result in model_input.tool_results
                        ],
                    )
                )
        return contents

    def _extract_text(self, response: Any) -> str:
        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, list):
            parts: list[str] = []
            for candidate in candidates:
                content = getattr(candidate, "content", None)
                parts_list = getattr(content, "parts", None)
                if not isinstance(parts_list, list):
                    continue
                for part in parts_list:
                    value = None
                    if isinstance(part, dict):
                        value = part.get("text")
                    else:
                        value = getattr(part, "text", None)
                    if isinstance(value, str):
                        parts.append(value)
            if parts:
                return "\n".join(parts).strip()
        text = getattr(response, "text", None)
        if isinstance(text, str):
            return text
        return ""

    def _extract_tool_calls(self, response: Any) -> list[ToolCall]:
        direct_calls = getattr(response, "function_calls", None)
        if isinstance(direct_calls, list):
            return [self._normalize_tool_call(call) for call in direct_calls]

        candidates = getattr(response, "candidates", None)
        if not isinstance(candidates, list):
            return []
        tool_calls: list[ToolCall] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            parts_list = getattr(content, "parts", None)
            if not isinstance(parts_list, list):
                continue
            for part in parts_list:
                call = getattr(part, "function_call", None) or getattr(part, "functionCall", None)
                if call is None and isinstance(part, dict):
                    call = part.get("functionCall") or part.get("function_call")
                if call is not None:
                    tool_calls.append(self._normalize_tool_call(call))
        return tool_calls

    def _normalize_tool_call(self, call: Any) -> ToolCall:
        if isinstance(call, dict):
            return ToolCall(
                id=call.get("id"),
                name=str(call.get("name", "")),
                arguments=call.get("args", {}) or {},
            )
        return ToolCall(
            id=getattr(call, "id", None),
            name=str(getattr(call, "name", "")),
            arguments=getattr(call, "args", {}) or {},
        )

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
        candidates = getattr(response, "candidates", None)
        if isinstance(candidates, list) and candidates:
            content = getattr(candidates[0], "content", None)
            if content is not None:
                return {"model_content": content}
        return {}

    def _sdk_types(self) -> Any | None:
        try:
            from google.genai import types
        except ImportError:  # pragma: no cover
            return None
        return types

    def _user_text_content(self, prompt: str, sdk_types: Any | None) -> Any:
        if sdk_types is None:
            return {"role": "user", "parts": [{"text": prompt}]}
        return sdk_types.Content(role="user", parts=[sdk_types.Part(text=prompt)])

    def _sdk_content_from_dict(self, payload: dict[str, Any], sdk_types: Any | None) -> Any:
        if sdk_types is None:
            return payload
        role = str(payload.get("role", "model"))
        parts_payload = payload.get("parts", [])
        parts = [self._sdk_part_from_dict(part, sdk_types) for part in parts_payload if isinstance(part, dict)]
        return sdk_types.Content(role=role, parts=parts)

    def _sdk_part_from_dict(self, payload: dict[str, Any], sdk_types: Any) -> Any:
        if "text" in payload:
            return sdk_types.Part(text=payload["text"])
        if "functionCall" in payload:
            call = payload["functionCall"]
            kwargs: dict[str, Any] = {
                "function_call": sdk_types.FunctionCall(
                    name=call.get("name"),
                    args=call.get("args", {}),
                    id=call.get("id"),
                )
            }
            if "thought_signature" in payload:
                kwargs["thought_signature"] = payload["thought_signature"]
            return sdk_types.Part(**kwargs)
        if "functionResponse" in payload:
            response = payload["functionResponse"]
            return sdk_types.Part(
                function_response=sdk_types.FunctionResponse(
                    name=response.get("name"),
                    response=response.get("response", {}),
                    id=response.get("id"),
                )
            )
        return sdk_types.Part(text=str(payload))

    def _merged_params(self, request: AIRequest) -> dict[str, Any]:
        params = dict(self.params)
        params.update(request.params)
        return params

    def _request_labels(self, request: AIRequest) -> dict[str, str]:
        labels: dict[str, str] = {}
        for source_key, target_key in (
            ("runId", "runId"),
            ("expId", "expId"),
            ("phase", "phase"),
        ):
            value = request.metadata.get(source_key)
            if value is not None and str(value):
                labels[target_key] = str(value)
        return labels
