from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from copa.dataset.contexts import context_path
from copa.util.fs import load_json

YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

ACADEMIC_ACTIVITIES_EMPTY = {
    "reviewerRoles": [],
    "editorialBoards": [],
    "eventParticipations": [],
    "eventOrganizations": [],
    "defenseBoards": [],
    "otherBoards": [],
}

SUPERVISION_LEVELS = (
    "masters",
    "doctoral",
    "undergraduate",
    "specialization",
    "others",
)

SUPERVISIONS_EMPTY = {
    level: {"completed": [], "ongoing": []}
    for level in SUPERVISION_LEVELS
}

PUBLICATION_TYPE_ALIASES = {
    "journal_article": (
        "journal_article",
        "journal",
        "journals",
        "article",
        "articles",
        "periodico",
        "periodicos",
        "artigos completos publicados em periodicos",
    ),
    "journal": (
        "journal_article",
        "journal",
        "journals",
        "article",
        "articles",
        "periodico",
        "periodicos",
        "artigos completos publicados em periodicos",
    ),
    "conference_paper": (
        "conference_paper",
        "conference",
        "conferences",
        "proceedings",
        "anais de congressos",
        "trabalhos completos publicados em anais de congressos",
    ),
    "conference": (
        "conference_paper",
        "conference",
        "conferences",
        "proceedings",
        "anais de congressos",
        "trabalhos completos publicados em anais de congressos",
    ),
    "presentation": (
        "presentation",
        "presentations",
        "apresentacao",
        "apresentacoes de trabalho",
    ),
    "book_chapter": (
        "book_chapter",
        "chapter",
        "chapters",
        "capitulo",
        "capitulos",
        "capitulos de livros publicados",
    ),
    "chapter": (
        "book_chapter",
        "chapter",
        "chapters",
        "capitulo",
        "capitulos",
        "capitulos de livros publicados",
    ),
    "expanded_abstract": (
        "expanded_abstract",
        "expanded abstracts",
        "resumos expandidos publicados em anais de congressos",
    ),
    "conference_abstract": (
        "conference_abstract",
        "abstract",
        "abstracts",
        "resumos publicados em anais de congressos",
    ),
    "other_work": (
        "other_work",
        "other works",
        "demais trabalhos",
    ),
    "press_article": (
        "press_article",
        "news",
        "magazine",
        "magazines",
        "textos em jornais de noticias revistas",
    ),
    "news": (
        "press_article",
        "news",
        "magazine",
        "magazines",
        "textos em jornais de noticias revistas",
    ),
    "edited_book": (
        "edited_book",
        "book",
        "books",
        "livro",
        "livros",
        "livros publicados organizados ou edicoes",
    ),
    "book_and_chapters": (
        "book_and_chapters",
        "livros e capitulos",
    ),
    "technical_process": (
        "technical_process",
        "processos tecnicas",
        "processostecnicas",
    ),
    "technical_other": (
        "technical_other",
        "demais tipos de producao tecnica",
    ),
}

SUPERVISION_ENTRY_PATTERN = re.compile(r"^(?P<kind>[^:]+):\s*(?P<student>[^.]+)\.\s*(?P<body>.*)$")


class LattesProvider:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def get_profile(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
    ) -> dict[str, Any]:
        return self._get_section_object(contexts_dir=contexts_dir, lattes_id=lattes_id, section_name="profile")

    def get_expertise(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
    ) -> dict[str, Any]:
        return self._get_section_object(contexts_dir=contexts_dir, lattes_id=lattes_id, section_name="expertise")

    def get_education(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return self._filter_items_section(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="education",
            start_year=start_year,
            end_year=end_year,
        )

    def get_projects(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return self._filter_items_section(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="projects",
            start_year=start_year,
            end_year=end_year,
        )

    def get_supervisions(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        section = self._get_section_object(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="supervisions",
            default=SUPERVISIONS_EMPTY,
        )
        payload: dict[str, Any] = {}
        for level in SUPERVISION_LEVELS:
            level_section = section.get(level)
            if not isinstance(level_section, dict):
                payload[level] = {"completed": [], "ongoing": []}
                continue
            payload[level] = {
                "completed": self._filter_sequence(level_section.get("completed"), start_year, end_year),
                "ongoing": self._filter_sequence(level_section.get("ongoing"), start_year, end_year),
            }
        return payload

    def get_advisees(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
    ) -> dict[str, Any]:
        section = self._get_section_object(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="supervisions",
            default=SUPERVISIONS_EMPTY,
        )
        items: list[dict[str, Any]] = []
        for level in SUPERVISION_LEVELS:
            level_section = section.get(level)
            if not isinstance(level_section, dict):
                continue
            for status in ("completed", "ongoing"):
                entries = level_section.get(status)
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    parsed = self._parse_supervision_entry(entry, level=level, status=status)
                    if parsed is not None:
                        items.append(parsed)
        return {"items": items}

    def get_experience(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return self._filter_items_section(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="experience",
            start_year=start_year,
            end_year=end_year,
        )

    def get_academic_activities(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        section = self._get_section_object(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="academicActivities",
            default=ACADEMIC_ACTIVITIES_EMPTY,
        )
        return {
            key: self._filter_sequence(section.get(key), start_year, end_year)
            for key in ACADEMIC_ACTIVITIES_EMPTY
        }

    def get_publications(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
        coauthors: list[str] | None = None,
        publication_type: str | None = None,
    ) -> dict[str, Any]:
        section = self._get_section_object(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="publications",
            default={"metadata": {}, "items": []},
        )
        metadata = section.get("metadata")
        items = self._filter_sequence(section.get("items"), start_year, end_year)
        items = self._filter_publications(items, coauthors=coauthors, publication_type=publication_type)
        return {
            "metadata": metadata if isinstance(metadata, dict) else {},
            "items": items,
        }

    def get_technical_output(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return self._filter_items_section(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="technicalOutput",
            start_year=start_year,
            end_year=end_year,
        )

    def get_artistic_output(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        start_year: int | None = None,
        end_year: int | None = None,
    ) -> dict[str, Any]:
        return self._filter_items_section(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name="artisticOutput",
            start_year=start_year,
            end_year=end_year,
        )

    def get_parsed_curriculum(self, *, contexts_dir: str, lattes_id: str) -> dict[str, Any]:
        path = context_path(contexts_dir, lattes_id, "json")
        cache_key = str(path.resolve())
        if cache_key not in self._cache:
            payload = load_json(path)
            if not isinstance(payload, dict):
                raise ValueError(f"Parsed curriculum must be a JSON object: {path}")
            self._cache[cache_key] = payload
        return self._cache[cache_key]

    def resolve_instance_dir(self, *, contexts_dir: str, lattes_id: str) -> str:
        path = Path(contexts_dir) / lattes_id
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Missing context directory for lattes_id={lattes_id}: {path}")
        return str(path.resolve())

    def close(self) -> None:
        self._cache.clear()

    def _get_section_object(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        section_name: str,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = self.get_parsed_curriculum(contexts_dir=contexts_dir, lattes_id=lattes_id)
        section = payload.get(section_name)
        if isinstance(section, dict):
            return dict(section)
        return dict(default or {})

    def _filter_items_section(
        self,
        *,
        contexts_dir: str,
        lattes_id: str,
        section_name: str,
        start_year: int | None,
        end_year: int | None,
    ) -> dict[str, Any]:
        section = self._get_section_object(
            contexts_dir=contexts_dir,
            lattes_id=lattes_id,
            section_name=section_name,
            default={"items": []},
        )
        return {"items": self._filter_sequence(section.get("items"), start_year, end_year)}

    def _filter_sequence(
        self,
        value: Any,
        start_year: int | None,
        end_year: int | None,
    ) -> list[Any]:
        if not isinstance(value, list):
            return []
        if start_year is None and end_year is None:
            return list(value)
        return [item for item in value if self._matches_year_window(item, start_year, end_year)]

    def _matches_year_window(
        self,
        item: Any,
        start_year: int | None,
        end_year: int | None,
    ) -> bool:
        item_start, item_end = self._item_year_range(item)
        if item_start is None and item_end is None:
            return False
        effective_start = item_start if item_start is not None else item_end
        effective_end = item_end if item_end is not None else item_start
        if effective_start is None or effective_end is None:
            return False
        if start_year is not None and effective_end < start_year:
            return False
        if end_year is not None and effective_start > end_year:
            return False
        return True

    def _item_year_range(self, item: Any) -> tuple[int | None, int | None]:
        if isinstance(item, dict):
            year = self._coerce_year(item.get("year"))
            if year is not None:
                return year, year
            interval = item.get("interval")
            if isinstance(interval, dict):
                start = self._coerce_year(interval.get("start"))
                end = self._coerce_year(interval.get("end"))
                if start is not None or end is not None:
                    return start, end
        years = self._extract_years(item)
        if not years:
            return None, None
        return min(years), max(years)

    def _extract_years(self, item: Any) -> list[int]:
        if isinstance(item, str):
            text = item
        elif isinstance(item, dict):
            text = json.dumps(item, ensure_ascii=False)
        else:
            text = str(item)
        years = [int(match.group(0)) for match in YEAR_PATTERN.finditer(text)]
        return sorted(set(years))

    def _coerce_year(self, value: Any) -> int | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    def _filter_publications(
        self,
        items: list[Any],
        *,
        coauthors: list[str] | None,
        publication_type: str | None,
    ) -> list[Any]:
        filtered = list(items)
        if coauthors:
            filtered = [
                item
                for item in filtered
                if self._publication_matches_coauthors(item, coauthors)
            ]
        if publication_type:
            filtered = [
                item
                for item in filtered
                if self._publication_matches_type(item, publication_type)
            ]
        return filtered

    def _publication_matches_coauthors(self, item: Any, coauthors: list[str]) -> bool:
        if not isinstance(item, dict):
            return False
        authors = item.get("authors")
        if not isinstance(authors, list) or not authors:
            return False
        for requested in coauthors:
            if not isinstance(requested, str) or not requested.strip():
                continue
            for author in authors:
                if isinstance(author, str) and self._text_contains_name(author, requested):
                    return True
        return False

    def _publication_matches_type(self, item: Any, publication_type: str) -> bool:
        if not isinstance(item, dict):
            return False
        category = item.get("category") or item.get("type") or ""
        if not isinstance(category, str):
            return False
        normalized_category = self._normalize_text(category)
        normalized_type = self._normalize_text(publication_type)
        if not normalized_category or not normalized_type:
            return False
        if normalized_type in normalized_category or normalized_category in normalized_type:
            return True
        aliases = PUBLICATION_TYPE_ALIASES.get(normalized_type, ())
        for alias in aliases:
            normalized_alias = self._normalize_text(alias)
            if normalized_alias in normalized_category or normalized_category in normalized_alias:
                return True
        return False

    def _text_contains_name(self, text: str, name: str) -> bool:
        normalized_text = self._normalize_text(text)
        normalized_name = self._normalize_text(name)
        if not normalized_text or not normalized_name:
            return False
        if normalized_name == normalized_text or normalized_name in normalized_text or normalized_text in normalized_name:
            return True
        text_tokens = [token for token in normalized_text.split() if len(token) > 1]
        name_tokens = [token for token in normalized_name.split() if len(token) > 1]
        if not text_tokens or not name_tokens:
            return False
        text_set = set(text_tokens)
        name_set = set(name_tokens)
        if text_set <= name_set or name_set <= text_set:
            return True
        overlap = text_set & name_set
        threshold = max(1, min(len(text_set), len(name_set)) - 1)
        return len(overlap) >= threshold

    def _normalize_text(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)
        normalized = normalized.encode("ascii", "ignore").decode("ascii")
        normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())
        return " ".join(normalized.split())

    def _parse_supervision_entry(self, value: Any, *, level: str, status: str) -> dict[str, Any] | None:
        if not isinstance(value, str) or not value.strip():
            return None
        text = value.strip()
        match = SUPERVISION_ENTRY_PATTERN.match(text)
        if match:
            kind = match.group("kind").strip()
            student = match.group("student").strip()
            body = match.group("body").strip()
        else:
            kind = ""
            student = text.split(".", 1)[0].strip()
            body = text
        years = self._extract_years(body or text)
        year = years[0] if years else None
        role = "coadvisor" if "coorientador" in self._normalize_text(text) else "advisor"
        parsed: dict[str, Any] = {
            "level": level,
            "status": status,
            "student": student,
            "role": role,
        }
        if kind:
            parsed["degree"] = kind
        if year is not None:
            parsed["year"] = year
        return parsed
