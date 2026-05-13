from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
import tarfile

import pytest

from ctxbench.cli import build_parser
from ctxbench.commands.dataset import fetch_command
from ctxbench.dataset.archive import DATASET_MANIFEST_NAME
from ctxbench.dataset.cache import DatasetCache, DatasetConflictError
from ctxbench.dataset.descriptor import DistributionDescriptor
from ctxbench.dataset.materialization import MaterializationManifest


def _manifest_paths(cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.rglob("manifest.json"))


def _write_dataset_manifest(root: Path, dataset_id: str = "ctxbench/fake-dataset", version: str = "0.1.0") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / DATASET_MANIFEST_NAME).write_text(
        json.dumps({"id": dataset_id, "datasetVersion": version}),
        encoding="utf-8",
    )


def _build_archive_from_directory(
    tmp_path: Path,
    dataset_id: str = "ctxbench/fake-dataset",
    version: str = "0.1.0",
) -> tuple[Path, str]:
    source_dir = tmp_path / "archive-source"
    dataset_root = source_dir / "dataset"
    _write_dataset_manifest(dataset_root, dataset_id=dataset_id, version=version)
    (dataset_root / "payload.txt").write_text("fixture-data", encoding="utf-8")

    archive_path = tmp_path / "dataset.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as handle:
        handle.add(dataset_root, arcname="dataset")

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    sha_path = tmp_path / "dataset.tar.gz.sha256"
    sha_path.write_text(f"{digest}  dataset.tar.gz\n", encoding="utf-8")
    return archive_path, digest


def _descriptor(
    *,
    dataset_id: str = "ctxbench/fake-dataset",
    version: str = "0.1.0",
    digest: str = "a" * 64,
    archive_url: str = "https://example.invalid/dataset.tar.gz",
) -> DistributionDescriptor:
    return DistributionDescriptor(
        id=dataset_id,
        datasetVersion=version,
        descriptorSchemaVersion=1,
        archive_type="tar.gz",
        archive_url=archive_url,
        archive_sha256=digest,
        name="Fake dataset",
        description="Fixture descriptor",
        release_tag="v0.1.0-dataset",
    )


def _descriptor_file(tmp_path: Path, *, dataset_id: str = "ctxbench/fake-dataset", version: str = "0.1.0", digest: str) -> Path:
    path = tmp_path / "dataset.descriptor.json"
    path.write_text(
        json.dumps(
            {
                "id": dataset_id,
                "datasetVersion": version,
                "descriptorSchemaVersion": 1,
                "name": "Fake dataset",
                "description": "Fixture descriptor",
                "releaseTag": "v0.1.0-dataset",
                "archive": {
                    "type": "tar.gz",
                    "url": "https://example.invalid/dataset.tar.gz",
                    "sha256": digest,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def _cache_manifest(
    *,
    dataset_id: str = "ctxbench/fake-dataset",
    version: str = "0.1.0",
    content_hash: str,
    verified_sha256: str | None = None,
) -> MaterializationManifest:
    return MaterializationManifest(
        datasetId=dataset_id,
        requestedVersion=version,
        datasetVersion=version,
        resolvedRevision=None,
        origin="/tmp/source",
        materializedPath="",
        contentHash=content_hash,
        fetchedAt="unavailable",
        ctxbenchVersion="unavailable",
        fetchMethod="archive-download",
        sourceType="archive-url",
        archiveUrl="https://example.invalid/dataset.tar.gz",
        verifiedSha256=verified_sha256,
    )


def test_fetch_command_dataset_dir_copies_files_and_writes_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "source"
    _write_dataset_manifest(source)
    (source / "payload.txt").write_text("fixture-data", encoding="utf-8")
    (source / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    cache_dir = tmp_path / "cache"

    seen_imports: list[str] = []
    original_import_module = importlib.import_module

    def recording_import_module(name: str, package: str | None = None):
        seen_imports.append(name)
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", recording_import_module)

    fetch_command(dataset_dir=str(source), cache_dir=cache_dir)

    captured = capsys.readouterr()
    manifests = _manifest_paths(cache_dir)
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["datasetId"] == "ctxbench/fake-dataset"
    assert manifest["requestedVersion"] == "0.1.0"
    assert manifest["origin"] == str(source)
    assert manifest["fetchMethod"] == "file-copy"
    assert manifest["sourceType"] == "local-directory"
    materialized = Path(manifest["materializedPath"])
    assert materialized.exists()
    assert (materialized / "payload.txt").read_text(encoding="utf-8") == "fixture-data"
    assert not any("module" in name for name in seen_imports)
    assert "identity: ctxbench/fake-dataset" in captured.out
    assert "datasetVersion: 0.1.0" in captured.out
    assert "materializedPath:" in captured.out


def test_fetch_command_local_archive_with_sha256_file_materializes_package(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    archive_path, _ = _build_archive_from_directory(tmp_path)
    cache_dir = tmp_path / "cache"

    fetch_command(
        dataset_file=str(archive_path),
        dataset_id="ctxbench/fake-dataset",
        version="0.1.0",
        sha256_file=str(tmp_path / "dataset.tar.gz.sha256"),
        cache_dir=cache_dir,
    )

    captured = capsys.readouterr()
    manifests = _manifest_paths(cache_dir)
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["datasetId"] == "ctxbench/fake-dataset"
    assert manifest["requestedVersion"] == "0.1.0"
    assert manifest["sourceType"] == "local-archive"
    assert manifest["verifiedSha256"].startswith("sha256:")
    assert manifest["materializedPath"].endswith("/ctxbench/fake-dataset/0.1.0")
    assert "verifiedSha256:" in captured.out


def test_descriptor_url_loads_descriptor_then_downloads_on_cache_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path, digest = _build_archive_from_directory(tmp_path)
    cache_dir = tmp_path / "cache"
    calls: list[str] = []

    monkeypatch.setattr(
        "ctxbench.commands.dataset.load_descriptor",
        lambda source, *, from_url: calls.append(f"descriptor:{source}:{from_url}") or _descriptor(digest=digest),
    )
    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda url: calls.append(f"download:{url}") or archive_path.read_bytes(),
    )

    fetch_command(descriptor_url="https://example.invalid/dataset.descriptor.json", cache_dir=cache_dir)

    manifests = _manifest_paths(cache_dir)
    assert len(manifests) == 1
    assert calls == [
        "descriptor:https://example.invalid/dataset.descriptor.json:True",
        "download:https://example.invalid/dataset.tar.gz",
    ]


def test_descriptor_file_loads_descriptor_then_downloads_on_cache_miss(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path, digest = _build_archive_from_directory(tmp_path)
    cache_dir = tmp_path / "cache"
    descriptor_path = _descriptor_file(tmp_path, digest=digest)
    calls: list[str] = []

    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda url: calls.append(f"download:{url}") or archive_path.read_bytes(),
    )

    fetch_command(descriptor_file=str(descriptor_path), cache_dir=cache_dir)

    manifests = _manifest_paths(cache_dir)
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["descriptorUrl"] == str(descriptor_path)
    assert manifest["descriptorSchemaVersion"] == 1
    assert calls == ["download:https://example.invalid/dataset.tar.gz"]


def test_fetch_parser_requires_exactly_one_source_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset", "fetch"])

    captured = capsys.readouterr()
    assert "--descriptor-url" in captured.err
    assert "--descriptor-file" in captured.err
    assert "--dataset-url" in captured.err
    assert "--dataset-file" in captured.err
    assert "--dataset-dir" in captured.err


def test_fetch_parser_rejects_multiple_source_flags() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "dataset",
                "fetch",
                "--descriptor-url",
                "https://example.invalid/dataset.descriptor.json",
                "--dataset-file",
                "/tmp/dataset.tar.gz",
            ]
        )


def test_dataset_fetch_help_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset", "fetch", "--help"])

    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "dataset fetch" in captured.out
    assert "--descriptor-url" in captured.out
    assert "--descriptor-file" in captured.out
    assert "--dataset-url" in captured.out
    assert "--dataset-file" in captured.out
    assert "--dataset-dir" in captured.out
    assert "--id" in captured.out
    assert "--version" in captured.out
    assert "--force" in captured.out
    assert "--sha256" in captured.out
    assert "--sha256-url" in captured.out
    assert "--sha256-file" in captured.out
    assert "--asset-name" not in captured.out


def test_dataset_url_requires_checksum_material() -> None:
    with pytest.raises(ValueError, match="--sha256 or --sha256-url"):
        fetch_command(dataset_url="https://example.invalid/fake-dataset.tar.gz", dataset_id="ctxbench/fake", version="0.1.0")


def test_dataset_file_requires_checksum_material(tmp_path: Path) -> None:
    archive_path, _ = _build_archive_from_directory(tmp_path)

    with pytest.raises(ValueError, match="--sha256 or --sha256-file"):
        fetch_command(dataset_file=str(archive_path), dataset_id="ctxbench/fake", version="0.1.0")


def test_dataset_url_without_id_fails_before_download() -> None:
    with pytest.raises(ValueError, match="--id"):
        fetch_command(dataset_url="https://example.invalid/fake-dataset.tar.gz", version="0.1.0", sha256="a" * 64)


def test_dataset_url_without_version_fails_before_download() -> None:
    with pytest.raises(ValueError, match="--version"):
        fetch_command(dataset_url="https://example.invalid/fake-dataset.tar.gz", dataset_id="ctxbench/fake", sha256="a" * 64)


def test_dataset_file_without_id_or_version_fails_before_extraction(tmp_path: Path) -> None:
    archive_path, _ = _build_archive_from_directory(tmp_path)

    with pytest.raises(ValueError, match="--id, --version"):
        fetch_command(dataset_file=str(archive_path), sha256="a" * 64)


def test_fetch_noops_when_matching_cache_entry_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "cache"
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "payload.txt").write_text("existing", encoding="utf-8")
    cache = DatasetCache(cache_dir=cache_dir)
    cache.store(
        _cache_manifest(content_hash="sha256:" + ("b" * 64), verified_sha256="sha256:" + ("b" * 64)),
        source,
    )

    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda _: (_ for _ in ()).throw(AssertionError("download should not run on cache hit")),
    )

    fetch_command(
        dataset_url="https://example.invalid/fake-dataset.tar.gz",
        dataset_id="ctxbench/fake-dataset",
        version="0.1.0",
        sha256="b" * 64,
        cache_dir=cache_dir,
    )

    output = capsys.readouterr().out
    assert "dataset already exists in cache" in output
    assert "materializedPath:" in output


def test_descriptor_url_noops_when_matching_cache_entry_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "cache"
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "payload.txt").write_text("existing", encoding="utf-8")
    cache = DatasetCache(cache_dir=cache_dir)
    digest = "e" * 64
    cache.store(
        _cache_manifest(content_hash=f"sha256:{digest}", verified_sha256=f"sha256:{digest}"),
        source,
    )

    monkeypatch.setattr(
        "ctxbench.commands.dataset.load_descriptor",
        lambda source, *, from_url: _descriptor(digest=digest),
    )
    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda _: (_ for _ in ()).throw(AssertionError("download should not run on descriptor cache hit")),
    )

    fetch_command(descriptor_url="https://example.invalid/dataset.descriptor.json", cache_dir=cache_dir)

    output = capsys.readouterr().out
    assert "dataset already exists in cache" in output
    assert "materializedPath:" in output


def test_fetch_conflict_raises_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_dir = tmp_path / "cache"
    source = tmp_path / "source"
    source.mkdir(parents=True, exist_ok=True)
    (source / "payload.txt").write_text("existing", encoding="utf-8")
    cache = DatasetCache(cache_dir=cache_dir)
    cache.store(_cache_manifest(content_hash="sha256:" + ("c" * 64), verified_sha256="sha256:" + ("c" * 64)), source)

    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda _: (_ for _ in ()).throw(AssertionError("download should not run on conflict without force")),
    )

    with pytest.raises(DatasetConflictError):
        fetch_command(
            dataset_url="https://example.invalid/fake-dataset.tar.gz",
            dataset_id="ctxbench/fake-dataset",
            version="0.1.0",
            sha256="d" * 64,
            cache_dir=cache_dir,
        )


def test_force_replaces_conflicting_cached_materialization_after_validation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    cache_dir = tmp_path / "cache"
    existing_source = tmp_path / "existing-source"
    existing_source.mkdir(parents=True, exist_ok=True)
    (existing_source / "payload.txt").write_text("old", encoding="utf-8")
    cache = DatasetCache(cache_dir=cache_dir)
    cache.store(_cache_manifest(content_hash="sha256:" + ("1" * 64), verified_sha256="sha256:" + ("1" * 64)), existing_source)

    archive_path, digest = _build_archive_from_directory(tmp_path / "replacement")

    fetch_command(
        dataset_file=str(archive_path),
        dataset_id="ctxbench/fake-dataset",
        version="0.1.0",
        sha256_file=str((tmp_path / "replacement") / "dataset.tar.gz.sha256"),
        cache_dir=cache_dir,
        force=True,
    )

    manifest = json.loads(_manifest_paths(cache_dir)[0].read_text(encoding="utf-8"))
    materialized = Path(manifest["materializedPath"])
    assert manifest["verifiedSha256"] == f"sha256:{digest}"
    assert (materialized / "payload.txt").read_text(encoding="utf-8") == "fixture-data"
    assert "verifiedSha256:" in capsys.readouterr().out


def test_descriptor_mismatch_fails_before_materialization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive_path, digest = _build_archive_from_directory(tmp_path, dataset_id="ctxbench/other", version="0.2.0")
    descriptor_path = _descriptor_file(tmp_path, dataset_id="ctxbench/fake-dataset", version="0.1.0", digest=digest)
    cache_dir = tmp_path / "cache"

    monkeypatch.setattr(
        "ctxbench.commands.dataset.download_bytes",
        lambda _: archive_path.read_bytes(),
    )

    with pytest.raises(ValueError, match="Descriptor identity mismatch"):
        fetch_command(descriptor_file=str(descriptor_path), cache_dir=cache_dir)

    assert _manifest_paths(cache_dir) == []


def test_dataset_without_subcommand_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset"])

    captured = capsys.readouterr()
    assert "usage:" in captured.err
