from __future__ import annotations

from pathlib import Path
import hashlib
import io
import json
import tarfile

import pytest

from ctxbench.commands.dataset import fetch_command
from ctxbench.dataset.acquisition import discover_and_validate_manifest
from ctxbench.dataset.archive import (
    DATASET_MANIFEST_NAME,
    DatasetManifestDiscoveryError,
    determine_package_root,
    discover_dataset_manifest,
)


def _write_manifest(root: Path, dataset_id: str = "ctxbench/fake", version: str = "0.1.0") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / DATASET_MANIFEST_NAME).write_text(
        json.dumps({"id": dataset_id, "datasetVersion": version}),
        encoding="utf-8",
    )


def _build_tar_gz(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as handle:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            handle.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def test_discover_manifest_supports_single_top_level_directory(tmp_path: Path) -> None:
    extraction_root = tmp_path / "extract"
    _write_manifest(extraction_root / "dataset")

    manifest_path = discover_dataset_manifest(extraction_root)

    assert manifest_path == extraction_root / "dataset" / DATASET_MANIFEST_NAME
    assert determine_package_root(extraction_root) == extraction_root / "dataset"


def test_discover_manifest_supports_archive_root_files(tmp_path: Path) -> None:
    extraction_root = tmp_path / "extract"
    _write_manifest(extraction_root)
    (extraction_root / "examples.txt").write_text("root-file", encoding="utf-8")

    manifest_path = discover_dataset_manifest(extraction_root)

    assert manifest_path == extraction_root / DATASET_MANIFEST_NAME
    assert determine_package_root(extraction_root) == extraction_root


def test_discover_manifest_rejects_missing_manifest(tmp_path: Path) -> None:
    extraction_root = tmp_path / "extract"
    extraction_root.mkdir()

    with pytest.raises(DatasetManifestDiscoveryError):
        discover_dataset_manifest(extraction_root)


def test_discover_manifest_rejects_multiple_manifests(tmp_path: Path) -> None:
    extraction_root = tmp_path / "extract"
    _write_manifest(extraction_root / "dataset-a")
    _write_manifest(extraction_root / "dataset-b")

    with pytest.raises(DatasetManifestDiscoveryError):
        discover_dataset_manifest(extraction_root)


def test_discover_and_validate_manifest_rejects_identity_or_version_mismatch(tmp_path: Path) -> None:
    extraction_root = tmp_path / "extract"
    _write_manifest(extraction_root, dataset_id="ctxbench/other", version="0.2.0")

    with pytest.raises(ValueError, match="Dataset identity mismatch"):
        discover_and_validate_manifest(
            extraction_root,
            expected_dataset_id="ctxbench/fake",
            expected_version="0.1.0",
        )


def test_fetch_command_archive_materializes_verified_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _build_tar_gz(
        {
            f"dataset/{DATASET_MANIFEST_NAME}": b'{"id":"ctxbench/fake","datasetVersion":"0.1.0"}',
            "dataset/data/example.txt": b"example",
        }
    )
    digest = hashlib.sha256(payload).hexdigest()
    cache_dir = tmp_path / "cache"

    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda _: payload,
    )

    fetch_command(
        dataset_url="https://example.invalid/ctxbench-fake-0.1.0.tar.gz",
        dataset_id="ctxbench/fake",
        version="0.1.0",
        sha256=digest,
        cache_dir=cache_dir,
    )

    manifests = sorted(cache_dir.rglob("manifest.json"))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["datasetId"] == "ctxbench/fake"
    assert manifest["requestedVersion"] == "0.1.0"
    assert manifest["fetchMethod"] == "archive-download"
    assert manifest["sourceType"] == "archive-url"
    assert manifest["archiveUrl"] == "https://example.invalid/ctxbench-fake-0.1.0.tar.gz"
    assert manifest["verifiedSha256"] == f"sha256:{digest}"
    assert manifest["contentHash"] == f"sha256:{digest}"

    materialized_root = Path(manifest["materializedPath"])
    assert (materialized_root / DATASET_MANIFEST_NAME).exists()
    assert (materialized_root / "data" / "example.txt").read_text(encoding="utf-8") == "example"
