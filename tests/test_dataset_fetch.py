from __future__ import annotations

import importlib
import json
from pathlib import Path
import tarfile

import pytest

from ctxbench.cli import build_parser
from ctxbench.commands.dataset import fetch_command
from ctxbench.dataset.archive import DATASET_MANIFEST_NAME


def _manifest_paths(cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.rglob("manifest.json"))


def _write_dataset_manifest(root: Path, dataset_id: str = "ctxbench/fake-dataset", version: str = "0.1.0") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / DATASET_MANIFEST_NAME).write_text(
        json.dumps({"id": dataset_id, "datasetVersion": version}),
        encoding="utf-8",
    )


def _build_archive_from_directory(tmp_path: Path, dataset_id: str = "ctxbench/fake-dataset", version: str = "0.1.0") -> tuple[Path, str]:
    source_dir = tmp_path / "archive-source"
    dataset_root = source_dir / "dataset"
    _write_dataset_manifest(dataset_root, dataset_id=dataset_id, version=version)
    (dataset_root / "payload.txt").write_text("fixture-data", encoding="utf-8")

    archive_path = tmp_path / "dataset.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as handle:
        handle.add(dataset_root, arcname="dataset")

    sha_path = tmp_path / "dataset.tar.gz.sha256"
    import hashlib

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    sha_path.write_text(f"{digest}  dataset.tar.gz\n", encoding="utf-8")
    return archive_path, digest


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

    fetch_command(
        dataset_dir=str(source),
        cache_dir=cache_dir,
    )

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
    assert "verifiedSha256:" in captured.out


def test_fetch_parser_requires_exactly_one_source_flag(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset", "fetch"])

    captured = capsys.readouterr()
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
                "--dataset-url",
                "https://example.invalid/dataset.tar.gz",
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
    assert "--dataset-url" in captured.out
    assert "--dataset-file" in captured.out
    assert "--dataset-dir" in captured.out
    assert "--sha256" in captured.out
    assert "--sha256-url" in captured.out
    assert "--sha256-file" in captured.out
    assert "--asset-name" not in captured.out


def test_dataset_url_requires_checksum_material() -> None:
    with pytest.raises(ValueError, match="--sha256 or --sha256-url"):
        fetch_command(
            dataset_url="https://example.invalid/fake-dataset.tar.gz",
        )


def test_dataset_file_requires_checksum_material(tmp_path: Path) -> None:
    archive_path, _ = _build_archive_from_directory(tmp_path)

    with pytest.raises(ValueError, match="--sha256 or --sha256-file"):
        fetch_command(
            dataset_file=str(archive_path),
        )


def test_dataset_without_subcommand_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset"])

    captured = capsys.readouterr()
    assert "usage:" in captured.err
