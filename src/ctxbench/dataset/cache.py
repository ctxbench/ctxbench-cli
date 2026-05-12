from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import json
import shutil

from ctxbench.dataset.materialization import MaterializationManifest


class DatasetConflictError(ValueError):
    """Raised when the cache already contains conflicting materializations."""


class DatasetCache:
    def __init__(self, cache_dir: Path | str | None = None) -> None:
        self._cache_dir = Path(cache_dir).expanduser() if cache_dir is not None else (
            Path("~/.cache/ctxbench/datasets").expanduser()
        )

    def cache_dir(self) -> Path:
        return self._cache_dir

    def lookup(self, dataset_id: str, version: str) -> list[MaterializationManifest]:
        base = self.cache_dir() / self._dataset_key(dataset_id) / version
        if not base.exists():
            return []
        manifests: list[MaterializationManifest] = []
        for path in sorted(base.rglob("manifest.json")):
            manifests.append(self.read_manifest(path))
        return manifests

    def store(self, manifest: MaterializationManifest, source_path: Path) -> None:
        existing = self.lookup(manifest.datasetId, manifest.requestedVersion)
        for item in existing:
            if item.contentHash != manifest.contentHash:
                raise DatasetConflictError(
                    "Conflicting dataset materialization for "
                    f"{manifest.datasetId}@{manifest.requestedVersion}: "
                    f"{item.contentHash!r} != {manifest.contentHash!r}"
                )

        target_dir = self._target_dir(manifest)
        target_dir.parent.mkdir(parents=True, exist_ok=True)
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.copytree(source_path, target_dir)

        persisted = replace(manifest, materializedPath=str(target_dir.resolve()))
        self._write_manifest(target_dir / "manifest.json", persisted)

    def read_manifest(self, path: Path) -> MaterializationManifest:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid manifest payload: {path}")
        return MaterializationManifest(**payload)

    def _target_dir(self, manifest: MaterializationManifest) -> Path:
        suffix = (
            manifest.resolvedRevision
            or self._safe_segment(manifest.contentHash)
            or "materialized"
        )
        return self.cache_dir() / self._dataset_key(manifest.datasetId) / manifest.requestedVersion / suffix

    def _dataset_key(self, dataset_id: str) -> Path:
        return Path(*[self._safe_segment(part) for part in dataset_id.split("/") if part])

    def _safe_segment(self, value: str | None) -> str:
        if not value:
            return ""
        return value.replace("/", "_").replace(":", "_")

    def _write_manifest(self, path: Path, manifest: MaterializationManifest) -> None:
        path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True), encoding="utf-8")
