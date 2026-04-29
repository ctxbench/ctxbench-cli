from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from copa.ai.models.base import ToolResult, ToolSpec
from copa.datasets.lattes.provider import LattesProvider

TEMPORAL_SCHEMA = {
    "type": "object",
    "properties": {
        "lattes_id": {"type": "string"},
        "start_year": {"type": "integer"},
        "end_year": {"type": "integer"},
    },
    "required": ["lattes_id"],
    "additionalProperties": False,
}

IDENTITY_SCHEMA = {
    "type": "object",
    "properties": {
        "lattes_id": {"type": "string"},
    },
    "required": ["lattes_id"],
    "additionalProperties": False,
}

PUBLICATION_TYPE_ENUM = (
    "conference_paper",
    "journal_article",
    "presentation",
    "book_chapter",
    "expanded_abstract",
    "conference_abstract",
    "other_work",
    "press_article",
    "edited_book",
    "book_and_chapters",
    "technical_process",
    "technical_other",
)

PUBLICATIONS_SCHEMA = {
    "type": "object",
    "properties": {
        "lattes_id": {"type": "string"},
        "start_year": {"type": "integer"},
        "end_year": {"type": "integer"},
        "coauthors": {
            "type": "array",
            "items": {"type": "string"},
        },
        "publication_type": {
            "anyOf": [
                {"type": "string", "enum": list(PUBLICATION_TYPE_ENUM)},
                {"type": "null"},
            ]
        },
    },
    "required": ["lattes_id"],
    "additionalProperties": False,
}

PUBLICATIONS_DESCRIPTION = (
    "Return the researcher's bibliographic production. "
    "Use start_year/end_year to narrow time, coauthors to match collaborators, "
    "and publication_type to restrict the kind of publication. "
    "Use the short English enum values defined by the schema."
)


def list_lattes_tool_specs() -> list[ToolSpec]:
    return [
        ToolSpec(name="get_profile", description="Return the researcher's identification data.", input_schema=IDENTITY_SCHEMA),
        ToolSpec(name="get_expertise", description="Return the researcher's expertise, research lines and awards.", input_schema=IDENTITY_SCHEMA),
        ToolSpec(name="get_education", description="Return the researcher's academic background.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_projects", description="Return the researcher's projects.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_supervisions", description="Return the researcher's supervision activities grouped by level (masters, doctoral, undergraduate, specialization, others), each with completed and ongoing lists.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_advisees", description="Return a compact list of advisees and co-advisees. Use this before checking publications when the question mentions students or advisees.", input_schema=IDENTITY_SCHEMA),
        ToolSpec(name="get_experience", description="Return the researcher's professional experience.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_academic_activities", description="Return academic service, boards, events and related activities.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_publications", description=PUBLICATIONS_DESCRIPTION, input_schema=PUBLICATIONS_SCHEMA),
        ToolSpec(name="get_technical_output", description="Return the researcher's technical output.", input_schema=TEMPORAL_SCHEMA),
        ToolSpec(name="get_artistic_output", description="Return the researcher's artistic and cultural output.", input_schema=TEMPORAL_SCHEMA),
    ]


class LattesToolService:
    def __init__(self, *, contexts_dir: str, provider: LattesProvider | None = None) -> None:
        self._contexts_dir = contexts_dir
        self._provider = provider or LattesProvider()
        self._tools = list_lattes_tool_specs()
        self._handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "get_profile": self._call_get_profile,
            "get_expertise": self._call_get_expertise,
            "get_education": self._call_get_education,
            "get_projects": self._call_get_projects,
            "get_supervisions": self._call_get_supervisions,
            "get_advisees": self._call_get_advisees,
            "get_experience": self._call_get_experience,
            "get_academic_activities": self._call_get_academic_activities,
            "get_publications": self._call_get_publications,
            "get_technical_output": self._call_get_technical_output,
            "get_artistic_output": self._call_get_artistic_output,
        }

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools)

    def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        handler = self._handlers.get(name)
        if handler is None:
            raise KeyError(f"Unknown Lattes tool: {name}")
        started_at = perf_counter()
        content = handler(arguments)
        duration_ms = max(0, int((perf_counter() - started_at) * 1000))
        lattes_id = _require_lattes_id(arguments)
        return ToolResult(
            name=name,
            content=content,
            metadata={
                "server_event": {
                    "toolName": name,
                    "arguments": dict(arguments),
                    "lattes_id": lattes_id,
                    "durationMs": duration_ms,
                }
            },
        )

    def close(self) -> None:
        self._provider.close()

    def _call_get_profile(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_profile(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
        )

    def _call_get_expertise(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_expertise(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
        )

    def _call_get_education(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_education(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_projects(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_projects(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_supervisions(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_supervisions(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_advisees(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_advisees(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
        )

    def _call_get_experience(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_experience(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_academic_activities(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_academic_activities(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_publications(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_publications(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
            coauthors=_optional_string_list(arguments, "coauthors"),
            publication_type=_optional_string(arguments, "publication_type"),
        )

    def _call_get_technical_output(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_technical_output(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )

    def _call_get_artistic_output(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._provider.get_artistic_output(
            contexts_dir=self._contexts_dir,
            lattes_id=_require_lattes_id(arguments),
            start_year=_optional_year(arguments, "start_year"),
            end_year=_optional_year(arguments, "end_year"),
        )


def _require_lattes_id(arguments: dict[str, Any]) -> str:
    value = arguments.get("lattes_id")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Lattes tools require a non-empty 'lattes_id' argument.")
    return value.strip()


def _optional_year(arguments: dict[str, Any], field_name: str) -> int | None:
    value = arguments.get(field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Lattes tools require '{field_name}' to be an integer when provided.")
    return value


def _optional_string(arguments: dict[str, Any], field_name: str) -> str | None:
    value = arguments.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Lattes tools require '{field_name}' to be a non-empty string when provided.")
    return value.strip()


def _optional_string_list(arguments: dict[str, Any], field_name: str) -> list[str] | None:
    value = arguments.get(field_name)
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError(f"Lattes tools require '{field_name}' to be a list of strings when provided.")
    items: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"Lattes tools require '{field_name}' to contain only non-empty strings.")
        items.append(item.strip())
    return items
