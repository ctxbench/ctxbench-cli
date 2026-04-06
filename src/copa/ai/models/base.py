from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field


class AIRequest(BaseModel):
    question: str
    context: str
    model_name: str
    strategy_name: str
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIResult(BaseModel):
    answer: str
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw_response: Any | None = None
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelAdapter:
    def generate(self, prompt: str, request: AIRequest) -> AIResult:
        raise NotImplementedError
