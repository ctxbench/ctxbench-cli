from __future__ import annotations

from ctxbench.ai.models.base import AIRequest, AIResult


class FakeResponder:
    def __init__(self) -> None:
        self.calls: list[AIRequest] = []

    def execute(self, _engine: object, request: AIRequest) -> AIResult:
        self.calls.append(request)
        answer = "The researcher works mainly in computer science."
        return AIResult(
            answer=answer,
            raw_response={"answer": answer},
            metadata={"provider": "fake-responder"},
            trace={
                "metrics": {
                    "totalDurationMs": 7,
                    "modelDurationMs": 7,
                    "modelCalls": 1,
                    "toolCalls": 0,
                    "mcpToolCalls": 0,
                    "functionCalls": 0,
                    "inputTokens": 11,
                    "outputTokens": 8,
                    "totalTokens": 19,
                }
            },
            usage={
                "inputTokens": 11,
                "outputTokens": 8,
                "totalTokens": 19,
            },
            tool_calls=[],
        )
