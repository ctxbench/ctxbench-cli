from __future__ import annotations

from pathlib import Path

import pytest

from ctxbench.dataset.cache import DatasetCache, DatasetConflictError
from ctxbench.dataset.materialization import MaterializationManifest


def _manifest(
    *,
    dataset_id: str = "ctxbench/fake-dataset",
    version: str = "0.1.0",
    revision: str | None = "rev-001",
    content_hash: str | None = "sha256:abc123",
    fetch_method: str = "file-copy",
) -> MaterializationManifest:
    return MaterializationManifest(
        datasetId=dataset_id,
        requestedVersion=version,
        resolvedRevision=revision,
        origin="/tmp/source",
        materializedPath="/tmp/placeholder",
        contentHash=content_hash,
        fetchedAt="2026-05-12T00:00:00Z",
        ctxbenchVersion="0.1.0",
        fetchMethod=fetch_method,
    )


def _write_source(path: Path, *, text: str = "fixture") -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "payload.txt").write_text(text, encoding="utf-8")
    return path


def test_dataset_cache_store_and_lookup_round_trip(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    source = _write_source(tmp_path / "source")
    manifest = _manifest()

    cache.store(manifest, source)

    items = cache.lookup("ctxbench/fake-dataset", "0.1.0")
    assert len(items) == 1
    assert items[0].datasetId == "ctxbench/fake-dataset"
    assert items[0].requestedVersion == "0.1.0"
    assert Path(items[0].materializedPath).exists()
    assert (Path(items[0].materializedPath) / "payload.txt").read_text(encoding="utf-8") == "fixture"


def test_dataset_cache_lookup_unknown_returns_empty_list(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")

    assert cache.lookup("ctxbench/unknown", "0.0.1") == []


def test_dataset_cache_store_conflicting_content_hash_raises(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    first_source = _write_source(tmp_path / "source-a", text="one")
    second_source = _write_source(tmp_path / "source-b", text="two")

    cache.store(_manifest(content_hash="sha256:one"), first_source)

    with pytest.raises(DatasetConflictError):
        cache.store(_manifest(content_hash="sha256:two", revision="rev-002"), second_source)


def test_dataset_cache_read_manifest_rejects_unknown_fetch_method(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(
        """
        {
          "datasetId": "ctxbench/fake-dataset",
          "requestedVersion": "0.1.0",
          "resolvedRevision": "rev-001",
          "origin": "/tmp/source",
          "materializedPath": "/tmp/materialized",
          "contentHash": "sha256:abc123",
          "fetchedAt": "2026-05-12T00:00:00Z",
          "ctxbenchVersion": "0.1.0",
          "fetchMethod": "unknown-method"
        }
        """.strip(),
        encoding="utf-8",
    )

    cache = DatasetCache(cache_dir=tmp_path / "cache")
    with pytest.raises(ValueError):
        cache.read_manifest(path)


def test_dataset_cache_directory_is_configurable(tmp_path: Path) -> None:
    configured = tmp_path / "custom-cache"
    cache = DatasetCache(cache_dir=configured)

    assert cache.cache_dir() == configured
