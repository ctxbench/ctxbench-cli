from __future__ import annotations

from typing import Any

from copa.ai.models.base import AIRequest, ToolResult, ToolSpec
from copa.datasets.lattes.provider import LattesProvider
from copa.datasets.lattes.tools import call_lattes_tool, list_lattes_tool_specs


class LattesMCPServer:
    def __init__(self, provider: LattesProvider) -> None:
        self._provider = provider
        self._tools = list_lattes_tool_specs()

    def bind(self, request: AIRequest) -> None:
        context_path = request.metadata.get("context_path")
        if not isinstance(context_path, str) or not context_path:
            raise ValueError("Lattes MCP binding requires request.metadata['context_path'].")
        self._provider.bind(path=context_path, fmt=request.context_format)

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        return call_lattes_tool(self._provider, name, arguments)

    def close(self) -> None:
        self._provider.close()
