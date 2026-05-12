from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import tempfile

from ctxbench.dataset.archive import determine_package_root, safe_extract_tar_gz
from ctxbench.dataset.cache import DatasetCache
from ctxbench.dataset.conflicts import DatasetConflictDetector
from ctxbench.dataset.inspect import build_inspect_result
from ctxbench.dataset.acquisition import (
    build_archive_materialization_manifest,
    classify_acquisition_source,
    discover_and_validate_manifest,
    download_bytes,
    require_checksum_for_remote_archive,
    resolve_archive_source,
    resolve_expected_sha256,
    verify_downloaded_bytes,
)
from ctxbench.dataset.materialization import MaterializationManifest
from ctxbench.dataset.resolver import DatasetResolver


def _is_git_origin(origin: str) -> bool:
    return origin.startswith(("http://", "https://")) or origin.endswith(".git")


def _resolve_git_revision(origin: str, version: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "ls-remote", origin, version],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        return line.split()[0]
    return None


def fetch_command(
    dataset_id: str,
    origin: str,
    version: str,
    *,
    asset_name: str | None = None,
    sha256: str | None = None,
    sha256_url: str | None = None,
    cache_dir: Path | None = None,
) -> None:
    cache = DatasetCache(cache_dir=cache_dir)
    source_path = Path(origin).expanduser()
    source = classify_acquisition_source(
        origin=origin,
        asset_name=asset_name,
        sha256=sha256,
        sha256_url=sha256_url,
    )
    require_checksum_for_remote_archive(source)

    if source.source_type == "git-origin":
        fetch_method = "git-clone"
        resolved_revision = _resolve_git_revision(origin, version)
    elif source.source_type == "local-path":
        fetch_method = "file-copy"
        resolved_revision = None
        if not source_path.exists() or not source_path.is_dir():
            raise FileNotFoundError(f"Dataset origin path not found: {origin}")
    else:
        fetch_method = "archive-download"
        resolved_revision = None
        resolved_archive = resolve_archive_source(source)
        expected_sha256 = resolve_expected_sha256(source)
        payload = download_bytes(resolved_archive.archive_url)
        verified_sha256 = verify_downloaded_bytes(payload, expected_sha256)
    if fetch_method == "archive-download":
        manifest = build_archive_materialization_manifest(
            dataset_id=dataset_id,
            version=version,
            source=source,
            resolved=resolved_archive,
            verified_sha256=verified_sha256,
        )
    else:
        manifest = MaterializationManifest(
            datasetId=dataset_id,
            requestedVersion=version,
            resolvedRevision=resolved_revision,
            origin=origin,
            materializedPath="",
            contentHash=None,
            fetchedAt="unavailable",
            ctxbenchVersion="unavailable",
            fetchMethod=fetch_method,
            sourceType=source.source_type,
            archiveUrl=None,
            releaseTagUrl=None,
            assetName=asset_name,
            verifiedSha256=sha256,
        )

    if fetch_method == "git-clone":
        raise NotImplementedError(
            "git-clone materialization is not implemented in the provider-free S3 slice."
        )
    if fetch_method == "archive-download":
        with tempfile.TemporaryDirectory(prefix="ctxbench-archive-") as tmpdir:
            extraction_root = Path(tmpdir) / "extract"
            safe_extract_tar_gz(payload, extraction_root)
            discover_and_validate_manifest(
                extraction_root,
                expected_dataset_id=dataset_id,
                expected_version=version,
            )
            package_root = determine_package_root(extraction_root)
            manifest.contentHash = manifest.verifiedSha256
            cache.store(manifest, package_root)
        return

    cache.store(manifest, source_path)


def _parse_dataset_ref(dataset_ref: str) -> str | dict[str, str]:
    candidate_path = Path(dataset_ref).expanduser()
    if candidate_path.exists() or dataset_ref.startswith((".", "/", "~")):
        return str(candidate_path)
    dataset_id, separator, version = dataset_ref.rpartition("@")
    if separator and dataset_id and version:
        return {"id": dataset_id, "version": version}
    return {"root": dataset_ref}


def inspect_command(
    dataset_ref: str,
    json_output: bool = False,
    *,
    cache_dir: Path | None = None,
) -> None:
    cache = DatasetCache(cache_dir=cache_dir)
    resolver = DatasetResolver()
    parsed_ref = _parse_dataset_ref(dataset_ref)
    manifest: MaterializationManifest | None = None
    if isinstance(parsed_ref, dict) and parsed_ref.get("id") and parsed_ref.get("version"):
        dataset_id = str(parsed_ref["id"])
        version = str(parsed_ref["version"])
        DatasetConflictDetector.check(dataset_id, version, cache)
        matches = cache.lookup(dataset_id, version)
        manifest = matches[0] if matches else None
    package = resolver.resolve(parsed_ref, cache)
    if manifest is None:
        manifest = getattr(package, "manifest", None)
    report = build_inspect_result(package, manifest)
    payload = asdict(report)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"identity: {report.identity}")
    print(f"version: {report.version}")
    print(f"conformant: {report.conformant}")
    print(f"origin: {report.origin}")
    print(f"missing_mandatory: {', '.join(report.missing_mandatory) if report.missing_mandatory else 'none'}")


def fetch_command_from_args(args: object) -> int:
    dataset_id = str(getattr(args, "dataset_id"))
    origin = str(getattr(args, "origin"))
    version = str(getattr(args, "version"))
    asset_name = getattr(args, "asset_name", None)
    sha256 = getattr(args, "sha256", None)
    sha256_url = getattr(args, "sha256_url", None)
    fetch_command(
        dataset_id,
        origin,
        version,
        asset_name=asset_name,
        sha256=sha256,
        sha256_url=sha256_url,
    )
    return 0


def inspect_command_from_args(args: object) -> int:
    inspect_command(
        str(getattr(args, "dataset_ref")),
        json_output=bool(getattr(args, "json_output", False)),
    )
    return 0
