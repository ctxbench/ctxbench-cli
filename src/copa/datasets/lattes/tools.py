from __future__ import annotations

from time import perf_counter
from typing import Any

from copa.ai.models.base import ToolResult, ToolSpec
from copa.datasets.lattes.provider import LattesProvider


def list_lattes_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(
            name="listSections",
            description="List the available sections in the parsed curriculum for the bound researcher.",
            input_schema={
                "type": "object",
                "properties": {"lattesId": {"type": "string"}},
                "required": ["lattesId"],
                "additionalProperties": False,
            },
        ),
        ToolSpec(
            name="getSection",
            description="Return one section from the parsed curriculum for the bound researcher.",
            input_schema={
                "type": "object",
                "properties": {
                    "lattesId": {"type": "string"},
                    "sectionName": {"type": "string"},
                },
                "required": ["lattesId", "sectionName"],
                "additionalProperties": False,
            },
        ),
    ]


class LattesToolService:
    def __init__(self, *, contexts_dir: str, provider: LattesProvider | None = None) -> None:
        self._contexts_dir = contexts_dir
        self._provider = provider or LattesProvider()
        self._tools = list_lattes_tool_specs()

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        started_at = perf_counter()
        lattes_id = _require_lattes_id(arguments)
        if name == "listSections":
            content = self._provider.list_sections(
                contexts_dir=self._contexts_dir,
                lattes_id=lattes_id,
            )
        elif name == "getSection":
            section_name = _require_string(arguments, "sectionName")
            content = self._provider.get_section(
                contexts_dir=self._contexts_dir,
                lattes_id=lattes_id,
                section_name=section_name,
            )
        else:
            raise KeyError(f"Unknown Lattes tool: {name}")
        duration_ms = max(0, int((perf_counter() - started_at) * 1000))
        return ToolResult(
            name=name,
            content=content,
            metadata={
                "server_event": {
                    "toolName": name,
                    "arguments": dict(arguments),
                    "lattesId": lattes_id,
                    "durationMs": duration_ms,
                }
            },
        )

    def close(self) -> None:
        self._provider.close()


def _require_lattes_id(arguments: dict[str, Any]) -> str:
    return _require_string(arguments, "lattesId")


def _require_string(arguments: dict[str, Any], field_name: str) -> str:
    value = arguments.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Lattes tools require a non-empty '{field_name}' argument.")
    return value.strip()
