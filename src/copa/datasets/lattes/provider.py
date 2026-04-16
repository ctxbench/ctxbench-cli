from __future__ import annotations

from pathlib import Path

from copa.datasets.lattes.models import EducationEntry, LattesCurriculum, ProjectEntry, PublicationEntry
from copa.datasets.lattes.readers import HtmlLattesReader, JsonLattesReader, LattesReader
from copa.dataset.contexts import context_path


class LattesProvider:
    def __init__(self, readers: dict[str, LattesReader] | None = None) -> None:
        self._readers = readers or {
            "json": JsonLattesReader(),
            "html": HtmlLattesReader(),
        }
        self._cache: dict[tuple[str, str], LattesCurriculum] = {}
        self._preferred_formats = tuple(self._readers.keys())

    def get_curriculum(self, *, path: str, fmt: str) -> LattesCurriculum:
        normalized_format = fmt.lower()
        cache_key = (path, normalized_format)
        if cache_key in self._cache:
            return self._cache[cache_key]
        reader = self._readers.get(normalized_format)
        if reader is None:
            raise ValueError(f"Unsupported Lattes context format: {fmt}")
        curriculum = reader.read(path)
        self._cache[cache_key] = curriculum
        return curriculum

    def resolve_context_path(self, *, contexts_dir: str, lattes_id: str, fmt: str) -> str:
        path = context_path(contexts_dir, lattes_id, fmt)
        if not path.exists():
            raise FileNotFoundError(f"Missing context artifact: {path}")
        return str(path.resolve())

    def resolve_context_artifact(self, *, contexts_dir: str, lattes_id: str) -> tuple[str, str]:
        for fmt in self._preferred_formats:
            path = context_path(contexts_dir, lattes_id, fmt)
            if path.exists():
                return str(path.resolve()), fmt
        available = ", ".join(self._preferred_formats)
        raise FileNotFoundError(
            f"Missing context artifact for lattesId={lattes_id}. Tried formats: {available}."
        )

    def get_basic_information(self, *, path: str, fmt: str) -> dict[str, object]:
        curriculum = self.get_curriculum(path=path, fmt=fmt)
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

    def get_education(self, *, path: str, fmt: str) -> list[EducationEntry]:
        return list(self.get_curriculum(path=path, fmt=fmt).education)

    def get_lines_of_research(self, *, path: str, fmt: str) -> list[str]:
        return list(self.get_curriculum(path=path, fmt=fmt).research.lines_of_research)

    def get_projects(
        self,
        *,
        path: str,
        fmt: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[ProjectEntry]:
        return self._filter_by_year(
            self.get_curriculum(path=path, fmt=fmt).projects,
            start_year=start_year,
            end_year=end_year,
        )

    def get_publications(
        self,
        *,
        path: str,
        fmt: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> list[PublicationEntry]:
        return self._filter_by_year(
            self.get_curriculum(path=path, fmt=fmt).publications,
            start_year=start_year,
            end_year=end_year,
        )

    def close(self) -> None:
        self._cache.clear()

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
