from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field


class AIRequest(BaseModel):
    question: str
    context: str
    provider_name: str
    model_name: str
    strategy_name: str
    context_format: str
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelInput(BaseModel):
    system_instruction: str
    prompt: str


class ModelResponse(BaseModel):
    text: str
    raw_response: Any | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIResult(BaseModel):
    answer: str
    raw_response: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    trace: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ModelAdapter:
    def __init__(self, params: dict[str, Any] | None = None) -> None:
        self.params = params or {}

    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
        raise NotImplementedError
