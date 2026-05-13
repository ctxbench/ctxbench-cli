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
    source_type: str | None = None,
    archive_url: str | None = None,
    release_tag_url: str | None = None,
    asset_name: str | None = None,
    verified_sha256: str | None = None,
    descriptor_url: str | None = None,
    descriptor_schema_version: int | None = None,
) -> MaterializationManifest:
    return MaterializationManifest(
        datasetId=dataset_id,
        requestedVersion=version,
        datasetVersion=version,
        resolvedRevision=revision,
        origin="/tmp/source",
        materializedPath="/tmp/placeholder",
        contentHash=content_hash,
        fetchedAt="2026-05-12T00:00:00Z",
        ctxbenchVersion="0.1.0",
        fetchMethod=fetch_method,
        sourceType=source_type,
        archiveUrl=archive_url,
        releaseTagUrl=release_tag_url,
        assetName=asset_name,
        verifiedSha256=verified_sha256,
        descriptorUrl=descriptor_url,
        descriptorSchemaVersion=descriptor_schema_version,
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
    assert items[0].datasetVersion == "0.1.0"
    assert Path(items[0].materializedPath).exists()
    assert (Path(items[0].materializedPath) / "payload.txt").read_text(encoding="utf-8") == "fixture"
    assert Path(items[0].materializedPath) == tmp_path / "cache" / "ctxbench" / "fake-dataset" / "0.1.0"


def test_dataset_cache_manifest_round_trip_preserves_archive_release_provenance(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    source = _write_source(tmp_path / "source")
    manifest = _manifest(
        fetch_method="archive-download",
        source_type="github-release-asset",
        archive_url="https://example.invalid/dataset.tar.gz",
        release_tag_url="https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset",
        asset_name="ctxbench-lattes-v0.1.0.tar.gz",
        verified_sha256="sha256:feedbeef",
        descriptor_url="https://example.invalid/dataset.descriptor.json",
        descriptor_schema_version=1,
    )

    cache.store(manifest, source)

    items = cache.lookup("ctxbench/fake-dataset", "0.1.0")
    assert len(items) == 1
    assert items[0].fetchMethod == "archive-download"
    assert items[0].sourceType == "github-release-asset"
    assert items[0].archiveUrl == "https://example.invalid/dataset.tar.gz"
    assert items[0].releaseTagUrl == "https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset"
    assert items[0].assetName == "ctxbench-lattes-v0.1.0.tar.gz"
    assert items[0].verifiedSha256 == "sha256:feedbeef"
    assert items[0].descriptorUrl == "https://example.invalid/dataset.descriptor.json"
    assert items[0].descriptorSchemaVersion == 1


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


def test_dataset_cache_store_identical_manifest_is_idempotent(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    source = _write_source(tmp_path / "source", text="same")
    manifest = _manifest(
        content_hash="sha256:same",
        fetch_method="archive-download",
        source_type="archive-url",
        archive_url="https://example.invalid/fake.tar.gz",
        verified_sha256="sha256:verified",
    )

    cache.store(manifest, source)
    cache.store(manifest, source)

    items = cache.lookup("ctxbench/fake-dataset", "0.1.0")
    assert len(items) == 1
    assert items[0].contentHash == "sha256:same"
    assert items[0].verifiedSha256 == "sha256:verified"


def test_dataset_cache_store_conflicting_verified_sha256_raises(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    first_source = _write_source(tmp_path / "source-a", text="one")
    second_source = _write_source(tmp_path / "source-b", text="one")

    cache.store(
        _manifest(
            content_hash="sha256:one",
            fetch_method="archive-download",
            source_type="archive-url",
            archive_url="https://example.invalid/fake.tar.gz",
            verified_sha256="sha256:verified-one",
        ),
        first_source,
    )

    with pytest.raises(DatasetConflictError):
        cache.store(
            _manifest(
                content_hash="sha256:one",
                revision="rev-002",
                fetch_method="archive-download",
                source_type="archive-url",
                archive_url="https://example.invalid/fake.tar.gz",
                verified_sha256="sha256:verified-two",
            ),
            second_source,
        )


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
          "fetchMethod": "unknown-method",
          "sourceType": null,
          "archiveUrl": null,
          "releaseTagUrl": null,
          "assetName": null,
          "verifiedSha256": null,
          "descriptorUrl": null,
          "descriptorSchemaVersion": null
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


def test_dataset_cache_directory_uses_env_var(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    configured = tmp_path / "env-cache"
    monkeypatch.setenv("CTXBENCH_DATASET_CACHE", str(configured))

    cache = DatasetCache()

    assert cache.cache_dir() == configured


def test_dataset_cache_explicit_directory_overrides_env_var(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("CTXBENCH_DATASET_CACHE", str(tmp_path / "env-cache"))
    configured = tmp_path / "explicit-cache"

    cache = DatasetCache(cache_dir=configured)

    assert cache.cache_dir() == configured


def test_dataset_cache_read_manifest_backfills_dataset_version_for_legacy_payload(
    tmp_path: Path,
) -> None:
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
          "fetchMethod": "file-copy",
          "sourceType": null,
          "archiveUrl": null,
          "releaseTagUrl": null,
          "assetName": null,
          "verifiedSha256": null,
          "descriptorUrl": null,
          "descriptorSchemaVersion": null
        }
        """.strip(),
        encoding="utf-8",
    )

    cache = DatasetCache(cache_dir=tmp_path / "cache")
    manifest = cache.read_manifest(path)

    assert manifest.requestedVersion == "0.1.0"
    assert manifest.datasetVersion == "0.1.0"


def test_dataset_cache_precheck_returns_hit_for_matching_content_identity(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    source = _write_source(tmp_path / "source")
    cache.store(
        _manifest(
            content_hash="sha256:abc123",
            fetch_method="archive-download",
            source_type="archive-url",
            verified_sha256="sha256:abc123",
        ),
        source,
    )

    result = cache.cache_precheck("ctxbench/fake-dataset", "0.1.0", expected_content_identity="sha256:abc123")

    assert result.status == "hit"
    assert result.manifest is not None
    assert result.manifest.datasetId == "ctxbench/fake-dataset"


def test_dataset_cache_precheck_returns_conflict_for_different_content_identity(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")
    source = _write_source(tmp_path / "source")
    cache.store(
        _manifest(
            content_hash="sha256:abc123",
            fetch_method="archive-download",
            source_type="archive-url",
            verified_sha256="sha256:abc123",
        ),
        source,
    )

    result = cache.cache_precheck("ctxbench/fake-dataset", "0.1.0", expected_content_identity="sha256:def456")

    assert result.status == "conflict"
    assert result.manifest is not None


def test_dataset_cache_precheck_returns_miss_when_no_materialization_exists(tmp_path: Path) -> None:
    cache = DatasetCache(cache_dir=tmp_path / "cache")

    result = cache.cache_precheck("ctxbench/missing", "0.1.0", expected_content_identity="sha256:abc123")

    assert result.status == "miss"
    assert result.manifest is None
