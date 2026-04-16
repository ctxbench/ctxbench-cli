from __future__ import annotations

from time import perf_counter
from typing import Any

from copa.ai.models.base import ToolResult, ToolSpec
from copa.datasets.lattes.provider import LattesProvider


def list_lattes_tool_specs() -> list[ToolSpec]:
    base_properties = {
        "lattesId": {"type": "string"},
    }
    year_filter_schema = {
        "type": "object",
        "properties": {
            **base_properties,
            "startYear": {"type": "integer"},
            "endYear": {"type": "integer"},
        },
        "additionalProperties": False,
        "required": ["lattesId"],
    }
    basic_schema = {
        "type": "object",
        "properties": dict(base_properties),
        "additionalProperties": False,
        "required": ["lattesId"],
    }
    return [
        ToolSpec(
            name="basicInformation",
            description="Return basic profile information for the bound researcher.",
            input_schema=basic_schema,
        ),
        ToolSpec(
            name="education",
            description="Return education history for the bound researcher.",
            input_schema=basic_schema,
        ),
        ToolSpec(
            name="linesOfResearch",
            description="Return the lines of research for the bound researcher.",
            input_schema=basic_schema,
        ),
        ToolSpec(
            name="listProjects",
            description="List projects for the bound researcher, optionally filtered by year.",
            input_schema=year_filter_schema,
        ),
        ToolSpec(
            name="listPublications",
            description="List publications for the bound researcher, optionally filtered by year.",
            input_schema=year_filter_schema,
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
        path, resolved_format = self._provider.resolve_context_artifact(
            contexts_dir=self._contexts_dir,
            lattes_id=lattes_id,
        )
        start_year = _as_int(arguments.get("startYear"))
        end_year = _as_int(arguments.get("endYear"))
        if name == "basicInformation":
            content = self._provider.get_basic_information(path=path, fmt=resolved_format)
        elif name == "education":
            content = [
                entry.model_dump(mode="json")
                for entry in self._provider.get_education(path=path, fmt=resolved_format)
            ]
        elif name == "linesOfResearch":
            content = self._provider.get_lines_of_research(path=path, fmt=resolved_format)
        elif name == "listProjects":
            content = [
                entry.model_dump(mode="json")
                for entry in self._provider.get_projects(
                    path=path,
                    fmt=resolved_format,
                    start_year=start_year,
                    end_year=end_year,
                )
            ]
        elif name == "listPublications":
            content = [
                entry.model_dump(mode="json")
                for entry in self._provider.get_publications(
                    path=path,
                    fmt=resolved_format,
                    start_year=start_year,
                    end_year=end_year,
                )
            ]
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
                    "contextFormat": resolved_format,
                }
            },
        )

    def close(self) -> None:
        self._provider.close()


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _require_lattes_id(arguments: dict[str, Any]) -> str:
    value = arguments.get("lattesId")
    if not isinstance(value, str) or not value:
        raise ValueError("Lattes tools require a non-empty 'lattesId' argument.")
    return value
