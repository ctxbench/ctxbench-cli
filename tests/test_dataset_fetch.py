from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

from ctxbench.cli import build_parser, main
from ctxbench.commands.dataset import fetch_command


def _manifest_paths(cache_dir: Path) -> list[Path]:
    return sorted(cache_dir.rglob("manifest.json"))


def test_fetch_command_local_path_copies_files_and_writes_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
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
        "ctxbench/fake-dataset",
        str(source),
        "0.1.0",
        cache_dir=cache_dir,
    )

    manifests = _manifest_paths(cache_dir)
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding="utf-8"))
    assert manifest["datasetId"] == "ctxbench/fake-dataset"
    assert manifest["requestedVersion"] == "0.1.0"
    assert manifest["origin"] == str(source)
    assert manifest["fetchMethod"] == "file-copy"
    assert sorted(manifest) == [
        "archiveUrl",
        "assetName",
        "contentHash",
        "ctxbenchVersion",
        "datasetId",
        "fetchMethod",
        "fetchedAt",
        "materializedPath",
        "origin",
        "releaseTagUrl",
        "requestedVersion",
        "resolvedRevision",
        "sourceType",
        "verifiedSha256",
    ]
    materialized = Path(manifest["materializedPath"])
    assert materialized.exists()
    assert (materialized / "payload.txt").read_text(encoding="utf-8") == "fixture-data"
    assert not any("module" in name for name in seen_imports)
    assert manifest["sourceType"] == "local-path"


def test_fetch_parser_requires_origin() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset", "fetch", "ctxbench/fake-dataset", "--version", "0.1.0"])


def test_dataset_fetch_help_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset", "fetch", "--help"])

    captured = capsys.readouterr()
    assert "usage:" in captured.out
    assert "dataset fetch" in captured.out
    assert "--asset-name" in captured.out
    assert "--sha256" in captured.out
    assert "--sha256-url" in captured.out


def test_archive_origin_requires_checksum_material(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([
        "dataset",
        "fetch",
        "ctxbench/fake-dataset",
        "--origin",
        "https://example.invalid/fake-dataset.tar.gz",
        "--version",
        "0.1.0",
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--sha256 or --sha256-url" in captured.err


def test_release_tag_origin_accepts_asset_name_but_still_requires_checksum(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([
        "dataset",
        "fetch",
        "ctxbench/fake-dataset",
        "--origin",
        "https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset",
        "--asset-name",
        "ctxbench-lattes-v0.1.0.tar.gz",
        "--version",
        "0.1.0",
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "--sha256 or --sha256-url" in captured.err


def test_dataset_without_subcommand_prints_usage(capsys: pytest.CaptureFixture[str]) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["dataset"])

    captured = capsys.readouterr()
    assert "usage:" in captured.err
