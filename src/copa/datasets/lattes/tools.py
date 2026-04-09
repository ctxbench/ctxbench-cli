from __future__ import annotations

from typing import Any

from copa.ai.models.base import ToolResult, ToolSpec
from copa.datasets.lattes.provider import LattesProvider


def list_lattes_tool_specs() -> list[ToolSpec]:
    year_filter_schema = {
        "type": "object",
        "properties": {
            "startYear": {"type": "integer"},
            "endYear": {"type": "integer"},
        },
        "additionalProperties": False,
    }
    return [
        ToolSpec(
            name="basicInformation",
            description="Return basic profile information for the bound researcher.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="education",
            description="Return education history for the bound researcher.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        ToolSpec(
            name="linesOfResearch",
            description="Return the lines of research for the bound researcher.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
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


def call_lattes_tool(provider: LattesProvider, name: str, arguments: dict[str, Any]) -> ToolResult:
    start_year = _as_int(arguments.get("startYear"))
    end_year = _as_int(arguments.get("endYear"))
    if name == "basicInformation":
        content = provider.get_basic_information()
    elif name == "education":
        content = [entry.model_dump(mode="json") for entry in provider.get_education()]
    elif name == "linesOfResearch":
        content = provider.get_lines_of_research()
    elif name == "listProjects":
        content = [entry.model_dump(mode="json") for entry in provider.get_projects(start_year=start_year, end_year=end_year)]
    elif name == "listPublications":
        content = [
            entry.model_dump(mode="json")
            for entry in provider.get_publications(start_year=start_year, end_year=end_year)
        ]
    else:
        raise KeyError(f"Unknown MCP tool: {name}")
    return ToolResult(name=name, content=content)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
