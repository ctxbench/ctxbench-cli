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
    estimated_input_tokens: int | None = None
    estimated_output_tokens: int | None = None
    reserved_tokens: int | None = None
    rate_limit_wait_ms: int | None = None
    retry_count: int = 0
    retry_sleep_ms: int | None = None


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

    def record_rate_limit_reservation(
        self,
        *,
        provider_name: str,
        model_name: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        reserved_tokens: int,
    ) -> None:
        self.metrics.estimated_input_tokens = estimated_input_tokens
        self.metrics.estimated_output_tokens = estimated_output_tokens
        self.metrics.reserved_tokens = reserved_tokens
        self.events.append(
            TraceEvent(
                type="rate_limit.reserve",
                name="rate_limit.reserve",
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "estimated_input_tokens": estimated_input_tokens,
                    "estimated_output_tokens": estimated_output_tokens,
                    "reserved_tokens": reserved_tokens,
                },
            )
        )

    def record_rate_limit_wait(
        self,
        *,
        provider_name: str,
        model_name: str,
        wait_ms: int,
        reason: str,
    ) -> None:
        self.metrics.rate_limit_wait_ms = self._sum_optional(self.metrics.rate_limit_wait_ms, wait_ms)
        self.events.append(
            TraceEvent(
                type="rate_limit.wait",
                name="rate_limit.wait",
                duration_ms=wait_ms,
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "reason": reason,
                },
            )
        )

    def record_rate_limit_reconcile(
        self,
        *,
        provider_name: str,
        model_name: str,
        reserved_tokens: int,
        actual_tokens: int | None,
    ) -> None:
        self.events.append(
            TraceEvent(
                type="rate_limit.reconcile",
                name="rate_limit.reconcile",
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "reserved_tokens": reserved_tokens,
                    "actual_tokens": actual_tokens,
                },
            )
        )

    def record_retry_attempt(
        self,
        *,
        provider_name: str,
        model_name: str,
        attempt: int,
        error_kind: str,
        error: str,
    ) -> None:
        self.metrics.retry_count += 1
        self.events.append(
            TraceEvent(
                type="retry.attempt",
                name="retry.attempt",
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "attempt": attempt,
                    "error_kind": error_kind,
                    "error": error,
                },
            )
        )

    def record_retry_sleep(
        self,
        *,
        provider_name: str,
        model_name: str,
        attempt: int,
        sleep_ms: int,
    ) -> None:
        self.metrics.retry_sleep_ms = self._sum_optional(self.metrics.retry_sleep_ms, sleep_ms)
        self.events.append(
            TraceEvent(
                type="retry.sleep",
                name="retry.sleep",
                duration_ms=sleep_ms,
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "attempt": attempt,
                },
            )
        )

    def record_retry_give_up(
        self,
        *,
        provider_name: str,
        model_name: str,
        attempt: int,
        error_kind: str,
        error: str,
    ) -> None:
        self.events.append(
            TraceEvent(
                type="retry.give_up",
                name="retry.give_up",
                metadata={
                    "provider_name": provider_name,
                    "model_name": model_name,
                    "attempt": attempt,
                    "error_kind": error_kind,
                    "error": error,
                },
            )
        )

    def to_trace(self) -> AITrace:
        return AITrace(events=list(self.events), metrics=self.metrics)

    def _apply_span_metrics(self, event: TraceEvent) -> None:
        if event.name == "engine.execute":
            self.metrics.total_duration_ms = event.duration_ms
        elif event.name in {
            "strategy.inline.execute",
            "strategy.local_function.execute",
            "strategy.local_mcp.execute",
            "strategy.mcp.execute",
        }:
            self.metrics.strategy_duration_ms = event.duration_ms

    def _sum_optional(self, current: int | None, value: int | None) -> int | None:
        if value is None:
            return current
        if current is None:
            return value
        return current + value
