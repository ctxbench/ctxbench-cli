from __future__ import annotations

import argparse
from pathlib import Path

from fastmcp import FastMCP

from copa.ai.models.base import ToolResult, ToolSpec
from copa.datasets.lattes.tools import LattesToolService


class LattesMCPServer:
    def __init__(
        self,
        *,
        contexts_dir: str,
        provider: object | None = None,
    ) -> None:
        self._service = LattesToolService(
            contexts_dir=contexts_dir,
            provider=provider,
        )
        self.app = FastMCP(
            name="copa-lattes",
            instructions=(
                "MCP server for querying Lattes researcher data."
                " All tools require an explicit lattesId argument."
            ),
        )
        self._register_tools()
        self._tool_specs = self._service.list_tools()

    def _register_tools(self) -> None:
        @self.app.tool(name="listSections", description="List available sections for a researcher.")
        async def list_sections(lattesId: str) -> list[str]:
            return self.call_tool("listSections", {"lattesId": lattesId}).content

        @self.app.tool(name="getSection", description="Return one parsed section for a researcher.")
        async def get_section(lattesId: str, sectionName: str) -> object:
            return self.call_tool(
                "getSection",
                {"lattesId": lattesId, "sectionName": sectionName},
            ).content

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tool_specs)

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        result = self._service.call_tool(name, arguments)
        metadata = dict(result.metadata)
        metadata["transport"] = "mcp_server"
        return result.model_copy(update={"metadata": metadata})

    def close(self) -> None:
        self._service.close()


def build_lattes_mcp_server(*, contexts_dir: str, provider: object | None = None) -> LattesMCPServer:
    return LattesMCPServer(contexts_dir=contexts_dir, provider=provider)


def create_mcp(*, contexts_dir: str | None = None) -> FastMCP:
    resolved_contexts_dir = contexts_dir or _default_contexts_dir()
    return build_lattes_mcp_server(contexts_dir=resolved_contexts_dir).app


def _default_contexts_dir() -> str:
    return str((Path(__file__).resolve().parents[4] / "datasets" / "lattes" / "context").resolve())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the COPA Lattes MCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "http", "sse"],
        default="streamable-http",
        help="FastMCP transport to use.",
    )
    parser.add_argument(
        "--contexts-dir",
        default=_default_contexts_dir(),
        help="Directory containing Lattes context artifacts.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host for HTTP-based transports.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for HTTP-based transports.",
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="Path for streamable HTTP or SSE transports.",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable the FastMCP startup banner.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    server = build_lattes_mcp_server(contexts_dir=args.contexts_dir)
    run_kwargs: dict[str, object] = {"show_banner": not args.no_banner}
    if args.transport in {"streamable-http", "http", "sse"}:
        run_kwargs["host"] = args.host
        run_kwargs["port"] = args.port
        if args.transport == "streamable-http":
            run_kwargs["path"] = args.path
        if args.transport == "sse":
            run_kwargs["path"] = args.path
    try:
        server.app.run(args.transport, **run_kwargs)
    finally:
        server.close()


if __name__ == "__main__":
    main()


mcp = create_mcp()
app = mcp
server = mcp
