from __future__ import annotations

from typing import Any, Protocol

from copa.ai.models.base import AIRequest, ToolResult, ToolSpec


class MCPServer(Protocol):
    def bind(self, request: AIRequest) -> None:
        ...

    def list_tools(self) -> list[ToolSpec]:
        ...

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        ...

    def close(self) -> None:
        ...


class MCPRuntime:
    def __init__(self, server: MCPServer) -> None:
        self._server = server
        self._bound_request: AIRequest | None = None
        self._closed = False

    def bind(self, request: AIRequest) -> None:
        self._ensure_open()
        self._bound_request = request
        self._server.bind(request)

    def list_tools(self) -> list[ToolSpec]:
        self._ensure_open()
        return self._server.list_tools()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        self._ensure_open()
        return self._server.call_tool(name, arguments)

    def close(self) -> None:
        if self._closed:
            return
        self._server.close()
        self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("MCP runtime is closed.")
