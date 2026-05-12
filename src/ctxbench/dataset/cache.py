from __future__ import annotations

from dataclasses import asdict, replace
import os
from pathlib import Path
import json
import shutil

from ctxbench.dataset.materialization import MaterializationManifest


class DatasetConflictError(ValueError):
    """Raised when the cache already contains conflicting materializations."""


class DatasetCache:
    def __init__(self, cache_dir: Path | str | None = None) -> None:
        if cache_dir is not None:
            self._cache_dir = Path(cache_dir).expanduser()
            return
        env_cache_dir = os.getenv("CTXBENCH_DATASET_CACHE")
        if env_cache_dir:
            self._cache_dir = Path(env_cache_dir).expanduser()
            return
        self._cache_dir = Path("~/.cache/ctxbench/datasets").expanduser()

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
            if self._is_conflicting(item, manifest):
                raise DatasetConflictError(
                    "Conflicting dataset materialization for "
                    f"{manifest.datasetId}@{manifest.requestedVersion}: "
                    f"existing(contentHash={item.contentHash!r}, verifiedSha256={item.verifiedSha256!r}) != "
                    f"new(contentHash={manifest.contentHash!r}, verifiedSha256={manifest.verifiedSha256!r})"
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

    def _is_conflicting(
        self,
        existing: MaterializationManifest,
        candidate: MaterializationManifest,
    ) -> bool:
        if existing.contentHash != candidate.contentHash:
            return True
        if existing.verifiedSha256 != candidate.verifiedSha256:
            return True
        return False
