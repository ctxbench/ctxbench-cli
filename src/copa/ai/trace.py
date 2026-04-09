from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Iterator

from copa._compat import BaseModel, Field


class TraceEvent(BaseModel):
    type: str
    name: str
    duration_ms: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIMetrics(BaseModel):
    total_duration_ms: int | None = None
    strategy_duration_ms: int | None = None
    model_duration_ms: int | None = None
    model_calls: int = 0
    mcp_tool_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    context_size_chars: int | None = None
    context_size_bytes: int | None = None
    question_size_chars: int | None = None
    prompt_size_chars: int | None = None


class AITrace(BaseModel):
    events: list[TraceEvent] = Field(default_factory=list)
    metrics: AIMetrics = Field(default_factory=AIMetrics)


class TraceCollector:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self.metrics = AIMetrics()

    @contextmanager
    def span(
        self,
        event_type: str,
        name: str,
        metadata: dict[str, Any] | None = None,
    ) -> Iterator[None]:
        started_at = perf_counter()
        try:
            yield
        finally:
            duration_ms = max(0, int((perf_counter() - started_at) * 1000))
            event = TraceEvent(
                type=event_type,
                name=name,
                duration_ms=duration_ms,
                metadata=metadata or {},
            )
            self.events.append(event)
            self._apply_span_metrics(event)

    def record_model_call(
        self,
        *,
        duration_ms: int | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            TraceEvent(
                type="model.generate",
                name="model.generate",
                duration_ms=duration_ms,
                metadata=metadata or {},
            )
        )
        self.metrics.model_calls += 1
        self.metrics.model_duration_ms = self._sum_optional(self.metrics.model_duration_ms, duration_ms)
        self.metrics.input_tokens = self._sum_optional(self.metrics.input_tokens, input_tokens)
        self.metrics.output_tokens = self._sum_optional(self.metrics.output_tokens, output_tokens)
        derived_total = total_tokens
        if derived_total is None and input_tokens is not None and output_tokens is not None:
            derived_total = input_tokens + output_tokens
        self.metrics.total_tokens = self._sum_optional(self.metrics.total_tokens, derived_total)

    def record_tool_call(self, *, name: str, arguments: dict[str, Any] | None = None) -> None:
        self.events.append(
            TraceEvent(
                type="mcp.tool_call",
                name="mcp.tool_call",
                metadata={"tool_name": name, "arguments": arguments or {}},
            )
        )
        self.metrics.mcp_tool_calls += 1

    def record_tool_result(
        self,
        *,
        name: str,
        result: Any,
        is_error: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event_metadata: dict[str, Any] = {
            "tool_name": name,
            "result": result,
            "is_error": is_error,
        }
        if metadata:
            event_metadata.update(metadata)
        self.events.append(
            TraceEvent(
                type="mcp.tool_result",
                name="mcp.tool_result",
                metadata=event_metadata,
            )
        )

    def record_error(self, error: str, metadata: dict[str, Any] | None = None) -> None:
        event_metadata = {"error": error}
        if metadata:
            event_metadata.update(metadata)
        self.events.append(TraceEvent(type="error", name="error", metadata=event_metadata))

    def to_trace(self) -> AITrace:
        return AITrace(events=list(self.events), metrics=self.metrics)

    def _apply_span_metrics(self, event: TraceEvent) -> None:
        if event.name == "engine.execute":
            self.metrics.total_duration_ms = event.duration_ms
        elif event.name in {"strategy.inline.execute", "strategy.mcp.execute"}:
            self.metrics.strategy_duration_ms = event.duration_ms

    def _sum_optional(self, current: int | None, value: int | None) -> int | None:
        if value is None:
            return current
        if current is None:
            return value
        return current + value
