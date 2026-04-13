from __future__ import annotations

from typing import Callable

from copa.ai.mcp.runtime import MCPRuntime
from copa.ai.models.base import AIRequest, AIResult, ModelAdapter
from copa.ai.models.claude import ClaudeModel
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.mock import MockModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.rate_control import RateControlRegistry, RateLimitedModelAdapter
from copa.ai.strategies.base import StrategyAdapter
from copa.ai.strategies.inline import InlineStrategy
from copa.ai.strategies.mcp import MCPStrategy
from copa.ai.trace import TraceCollector


class Engine:
    def __init__(
        self,
        mcp_runtime: MCPRuntime | None = None,
        event_logger: Callable[[str, str, dict[str, object]], None] | None = None,
    ) -> None:
        self._models: dict[str, ModelAdapter] = {
            "mock": MockModel(),
            "echo": MockModel(),
        }
        self._strategies: dict[str, StrategyAdapter] = {
            "inline": InlineStrategy(),
        }
        self._mcp_runtime = mcp_runtime
        self._rate_control_registry = RateControlRegistry()
        self._event_logger = event_logger

    def execute(self, request: AIRequest) -> AIResult:
        trace = TraceCollector()
        trace.metrics.context_size_chars = len(request.context)
        trace.metrics.context_size_bytes = len(request.context.encode("utf-8"))
        trace.metrics.question_size_chars = len(request.question)
        owned_runtime: MCPRuntime | None = None
        try:
            with trace.span("engine.execute", "engine.execute"):
                model = self._resolve_model(request.provider_name, request.model_name, request.params)
                strategy, owned_runtime = self._resolve_strategy(request.strategy_name)
                result = strategy.execute(model, request, trace)
        except Exception as exc:
            trace.record_error(
                str(exc),
                metadata={
                    "provider_name": request.provider_name,
                    "model_name": request.model_name,
                    "strategy_name": request.strategy_name,
                },
            )
            result = AIResult(answer="", error=str(exc))
        finally:
            if owned_runtime is not None:
                owned_runtime.close()
        result.trace = trace.to_trace().model_dump(mode="json")
        return result

    def _resolve_model(self, name: str, model_name: str, params: dict[str, object] | None = None) -> ModelAdapter:
        if name in self._models:
            resolved = self._models[name]
            return RateLimitedModelAdapter(
                resolved,
                self._rate_control_registry,
                provider_name=name,
                model_name=model_name,
                event_logger=self._event_logger,
            )
        lowered = name.lower()
        if lowered.startswith("gpt") or lowered.startswith("openai"):
            resolved = OpenAIModel(params=params)
            return RateLimitedModelAdapter(
                resolved,
                self._rate_control_registry,
                provider_name=name,
                model_name=model_name,
                event_logger=self._event_logger,
            )
        if lowered.startswith("gemini") or lowered.startswith("google"):
            resolved = GeminiModel(params=params)
            return RateLimitedModelAdapter(
                resolved,
                self._rate_control_registry,
                provider_name=name,
                model_name=model_name,
                event_logger=self._event_logger,
            )
        if lowered.startswith("claude") or lowered.startswith("anthropic"):
            resolved = ClaudeModel(params=params)
            return RateLimitedModelAdapter(
                resolved,
                self._rate_control_registry,
                provider_name=name,
                model_name=model_name,
                event_logger=self._event_logger,
            )
        resolved = MockModel(params=params)
        return RateLimitedModelAdapter(
            resolved,
            self._rate_control_registry,
            provider_name=name,
            model_name=model_name,
            event_logger=self._event_logger,
        )

    def _resolve_strategy(self, name: str) -> tuple[StrategyAdapter, MCPRuntime | None]:
        strategy = self._strategies.get(name)
        if strategy is not None:
            return strategy, None
        if name == "mcp":
            if self._mcp_runtime is None:
                raise ValueError("MCP strategy requires an injected MCP runtime.")
            return MCPStrategy(self._mcp_runtime), None
        raise ValueError(f"Unknown strategy: {name}")

    def close(self) -> None:
        if self._mcp_runtime is not None:
            self._mcp_runtime.close()

    def has_mcp_runtime(self) -> bool:
        return self._mcp_runtime is not None

    def copy_with_mcp_runtime(self, runtime: MCPRuntime) -> "Engine":
        engine = Engine(mcp_runtime=runtime)
        engine._models = self._models
        engine._strategies = self._strategies
        engine._rate_control_registry = self._rate_control_registry
        engine._event_logger = self._event_logger
        return engine
