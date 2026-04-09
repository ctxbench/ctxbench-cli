from __future__ import annotations

from copa.ai.mcp.runtime import MCPRuntime
from copa.datasets.lattes.models import EducationEntry, LattesCurriculum, ProjectEntry, PublicationEntry
from copa.datasets.lattes.readers import HtmlLattesReader, JsonLattesReader, LattesReader


class LattesProvider:
    def __init__(self, readers: dict[str, LattesReader] | None = None) -> None:
        self._readers = readers or {
            "json": JsonLattesReader(),
            "html": HtmlLattesReader(),
        }
        self._curriculum: LattesCurriculum | None = None
        self._bound_path: str | None = None
        self._bound_format: str | None = None

    def bind(self, *, path: str, fmt: str) -> None:
        normalized_format = fmt.lower()
        if self._bound_path == path and self._bound_format == normalized_format and self._curriculum is not None:
            return
        reader = self._readers.get(normalized_format)
        if reader is None:
            raise ValueError(f"Unsupported Lattes context format: {fmt}")
        self._curriculum = reader.read(path)
        self._bound_path = path
        self._bound_format = normalized_format

    def get_basic_information(self) -> dict[str, object]:
        curriculum = self._require_curriculum()
        return {
            "name": curriculum.profile.name,
            "summary": curriculum.profile.summary,
            "fellowship": curriculum.profile.fellowship,
            "nationality": curriculum.profile.nationality,
            "citationNames": list(curriculum.profile.citation_names),
            "addresses": [dict(item) for item in curriculum.profile.addresses],
            "lattesId": curriculum.meta.lattes_id,
            "sourceUrl": curriculum.meta.source_url,
            "lastUpdated": curriculum.meta.last_updated,
        }

    def get_education(self) -> list[EducationEntry]:
        return list(self._require_curriculum().education)

    def get_lines_of_research(self) -> list[str]:
        return list(self._require_curriculum().research.lines_of_research)

    def get_projects(self, start_year: int | None = None, end_year: int | None = None) -> list[ProjectEntry]:
        return self._filter_by_year(self._require_curriculum().projects, start_year=start_year, end_year=end_year)

    def get_publications(
        self,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[PublicationEntry]:
        return self._filter_by_year(self._require_curriculum().publications, start_year=start_year, end_year=end_year)

    def close(self) -> None:
        self._curriculum = None
        self._bound_path = None
        self._bound_format = None

    def _require_curriculum(self) -> LattesCurriculum:
        if self._curriculum is None:
            raise RuntimeError("Lattes provider is not bound to a curriculum.")
        return self._curriculum

    def _filter_by_year(self, items: list[ProjectEntry | PublicationEntry], *, start_year: int | None, end_year: int | None):
        if start_year is None and end_year is None:
            return list(items)
        filtered = []
        for item in items:
            year = item.start_year if hasattr(item, "start_year") else getattr(item, "year", None)
            if year is None:
                continue
            if start_year is not None and year < start_year:
                continue
            if end_year is not None and year > end_year:
                continue
            filtered.append(item)
        return filtered


def create_lattes_mcp_runtime() -> MCPRuntime:
    from copa.datasets.lattes.mcp_server import LattesMCPServer

    return MCPRuntime(server=LattesMCPServer(provider=LattesProvider()))
