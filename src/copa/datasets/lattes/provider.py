from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.dataset.contexts import context_path
from copa.util.fs import load_json


class LattesProvider:
    def __init__(self) -> None:
        self._cache: dict[str, dict[str, Any]] = {}

    def get_parsed_curriculum(self, *, contexts_dir: str, lattes_id: str) -> dict[str, Any]:
        path = context_path(contexts_dir, lattes_id, "json")
        cache_key = str(path.resolve())
        if cache_key not in self._cache:
            payload = load_json(path)
            if not isinstance(payload, dict):
                raise ValueError(f"Parsed curriculum must be a JSON object: {path}")
            self._cache[cache_key] = payload
        return self._cache[cache_key]

    def list_sections(self, *, contexts_dir: str, lattes_id: str) -> list[str]:
        payload = self.get_parsed_curriculum(contexts_dir=contexts_dir, lattes_id=lattes_id)
        return sorted(
            key for key, value in payload.items()
            if isinstance(key, str) and not key.startswith("_") and value is not None
        )

    def get_section(self, *, contexts_dir: str, lattes_id: str, section_name: str) -> Any:
        payload = self.get_parsed_curriculum(contexts_dir=contexts_dir, lattes_id=lattes_id)
        if section_name not in payload:
            raise KeyError(f"Unknown curriculum section: {section_name}")
        return payload[section_name]

    def resolve_instance_dir(self, *, contexts_dir: str, lattes_id: str) -> str:
        path = Path(contexts_dir) / lattes_id
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Missing context directory for lattesId={lattes_id}: {path}")
        return str(path.resolve())

    def close(self) -> None:
        self._cache.clear()
