from __future__ import annotations

from pathlib import Path

import pytest

from ctxbench.benchmark.models import ExperimentDataset
from ctxbench.dataset.cache import DatasetCache
from ctxbench.dataset.conflicts import AmbiguousDatasetError, DatasetConflictDetector
from ctxbench.dataset.materialization import MaterializationManifest
from ctxbench.dataset.resolver import DatasetResolver


def _manifest(*, origin: str, revision: str) -> MaterializationManifest:
    return MaterializationManifest(
        datasetId="ctxbench/fake",
        requestedVersion="0.1.0",
        resolvedRevision=revision,
        origin=origin,
        materializedPath="/tmp/placeholder",
        contentHash="sha256:same",
        fetchedAt="2026-05-12T00:00:00Z",
        ctxbenchVersion="0.1.0",
        fetchMethod="archive-download",
        sourceType="archive-url",
        archiveUrl="https://example.invalid/fake.tar.gz",
        verifiedSha256="sha256:verified",
    )


def _write_source(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "payload.txt").write_text("fixture", encoding="utf-8")
    return path


def test_conflict_detector_accepts_single_materialization(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    cache.store(_manifest(origin="/tmp/source-a", revision="rev-a"), _write_source(tmp_path / "source-a"))

    DatasetConflictDetector.check("ctxbench/fake", "0.1.0", cache)


def test_conflict_detector_rejects_multiple_candidates_and_lists_origins(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    version_root = tmp_path / "cache" / "ctxbench" / "fake" / "0.1.0"
    rev_a = version_root / "rev-a"
    rev_b = version_root / "rev-b"
    rev_a.mkdir(parents=True, exist_ok=True)
    rev_b.mkdir(parents=True, exist_ok=True)
    cache._write_manifest(rev_a / "manifest.json", _manifest(origin="/tmp/source-a", revision="rev-a"))  # type: ignore[attr-defined]
    cache._write_manifest(rev_b / "manifest.json", _manifest(origin="/tmp/source-b", revision="rev-b"))  # type: ignore[attr-defined]

    with pytest.raises(AmbiguousDatasetError) as excinfo:
        DatasetConflictDetector.check("ctxbench/fake", "0.1.0", cache)

    message = str(excinfo.value)
    assert "/tmp/source-a" in message
    assert "/tmp/source-b" in message
    assert "rev-a" in message
    assert "rev-b" in message


def test_semantic_cache_store_keeps_single_materialization_for_same_id_and_version(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    cache.store(_manifest(origin="/tmp/source-a", revision="rev-a"), _write_source(tmp_path / "source-a"))
    cache.store(_manifest(origin="/tmp/source-b", revision="rev-b"), _write_source(tmp_path / "source-b"))

    matches = cache.lookup("ctxbench/fake", "0.1.0")

    assert len(matches) == 1
    assert matches[0].origin == "/tmp/source-b"
    assert matches[0].resolvedRevision == "rev-b"


def test_dataset_resolver_calls_conflict_detector_before_returning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    cache.store(_manifest(origin="/tmp/source-a", revision="rev-a"), _write_source(tmp_path / "source-a"))
    resolver = DatasetResolver()
    calls: list[tuple[str, str]] = []

    def _check(dataset_id: str, version: str, cache_arg: DatasetCache) -> None:
        assert cache_arg is cache
        calls.append((dataset_id, version))

    monkeypatch.setattr(DatasetConflictDetector, "check", staticmethod(_check))

    package = resolver.resolve(ExperimentDataset(id="ctxbench/fake", version="0.1.0"), cache)

    assert calls == [("ctxbench/fake", "0.1.0")]
    assert package.identity() == "ctxbench/fake"
