from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
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
    require_checksum_for_archive_source,
    resolve_archive_source,
    resolve_expected_sha256,
    verify_downloaded_bytes,
)
from ctxbench.dataset.materialization import MaterializationManifest
from ctxbench.dataset.resolver import DatasetResolver


def _coerce_dataset_version(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Dataset manifest is missing a non-empty datasetVersion.")
    return value


def _load_persisted_manifest(cache: DatasetCache, dataset_id: str, version: str) -> MaterializationManifest:
    matches = cache.lookup(dataset_id, version)
    if not matches:
        raise ValueError(f"Materialized dataset not found in cache after fetch: {dataset_id}@{version}")
    return matches[0]


def fetch_command(
    dataset_id: str | None = None,
    origin: str | None = None,
    version: str | None = None,
    *,
    dataset_url: str | None = None,
    dataset_file: str | None = None,
    dataset_dir: str | None = None,
    sha256: str | None = None,
    sha256_url: str | None = None,
    sha256_file: str | None = None,
    cache_dir: Path | None = None,
) -> None:
    cache = DatasetCache(cache_dir=cache_dir)
    expected_dataset_id = dataset_id
    expected_version = version
    if not any((dataset_url, dataset_file, dataset_dir)) and origin is not None:
        legacy_source = Path(origin).expanduser()
        if legacy_source.exists() and legacy_source.is_dir():
            dataset_dir = origin
        elif legacy_source.exists() and legacy_source.is_file():
            dataset_file = origin
        else:
            dataset_url = origin
    source = classify_acquisition_source(
        dataset_url=dataset_url,
        dataset_file=dataset_file,
        dataset_dir=dataset_dir,
        sha256=sha256,
        sha256_url=sha256_url,
        sha256_file=sha256_file,
    )
    require_checksum_for_archive_source(source)

    if source.source_type == "local-directory":
        fetch_method = "file-copy"
        source_path = Path(source.origin).expanduser()
        if not source_path.exists() or not source_path.is_dir():
            raise FileNotFoundError(f"Dataset directory not found: {source.origin}")
        _, payload = discover_and_validate_manifest(
            source_path,
            expected_dataset_id=expected_dataset_id,
            expected_version=expected_version,
        )
        discovered_dataset_id = str(payload["id"])
        discovered_version = _coerce_dataset_version(payload.get("datasetVersion", payload.get("version")))
        manifest = MaterializationManifest(
            datasetId=discovered_dataset_id,
            requestedVersion=discovered_version,
            datasetVersion=discovered_version,
            resolvedRevision=None,
            origin=source.origin,
            materializedPath="",
            contentHash=None,
            fetchedAt="unavailable",
            ctxbenchVersion="unavailable",
            fetchMethod=fetch_method,
            sourceType=source.source_type,
            archiveUrl=None,
            releaseTagUrl=None,
            assetName=None,
            verifiedSha256=None,
        )
        cache.store(manifest, source_path)
        persisted = _load_persisted_manifest(cache, discovered_dataset_id, discovered_version)
    else:
        resolved_archive = resolve_archive_source(source)
        expected_sha256 = resolve_expected_sha256(source)
        if resolved_archive.archive_url is not None:
            payload = download_bytes(resolved_archive.archive_url)
        elif resolved_archive.archive_path is not None:
            payload = resolved_archive.archive_path.read_bytes()
        else:
            raise ValueError(f"Archive source is incomplete: {source.origin}")
        verified_sha256 = verify_downloaded_bytes(payload, expected_sha256)
        with tempfile.TemporaryDirectory(prefix="ctxbench-archive-") as tmpdir:
            extraction_root = Path(tmpdir) / "extract"
            safe_extract_tar_gz(payload, extraction_root)
            _, manifest_payload = discover_and_validate_manifest(
                extraction_root,
                expected_dataset_id=expected_dataset_id,
                expected_version=expected_version,
            )
            package_root = determine_package_root(extraction_root)
            discovered_dataset_id = str(manifest_payload["id"])
            discovered_version = _coerce_dataset_version(
                manifest_payload.get("datasetVersion", manifest_payload.get("version"))
            )
            manifest = build_archive_materialization_manifest(
                dataset_id=discovered_dataset_id,
                version=discovered_version,
                source=source,
                resolved=resolved_archive,
                verified_sha256=verified_sha256,
            )
            manifest.contentHash = manifest.verifiedSha256
            cache.store(manifest, package_root)
        persisted = _load_persisted_manifest(cache, discovered_dataset_id, discovered_version)

    print(f"identity: {persisted.datasetId}")
    print(f"datasetVersion: {persisted.datasetVersion}")
    if persisted.verifiedSha256:
        print(f"verifiedSha256: {persisted.verifiedSha256}")
    elif persisted.contentHash:
        print(f"contentHash: {persisted.contentHash}")
    print(f"materializedPath: {persisted.materializedPath}")


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
    fetch_command(
        dataset_url=getattr(args, "dataset_url", None),
        dataset_file=getattr(args, "dataset_file", None),
        dataset_dir=getattr(args, "dataset_dir", None),
        sha256=getattr(args, "sha256", None),
        sha256_url=getattr(args, "sha256_url", None),
        sha256_file=getattr(args, "sha256_file", None),
        cache_dir=getattr(args, "cache_dir", None),
    )
    return 0


def inspect_command_from_args(args: object) -> int:
    inspect_command(
        str(getattr(args, "dataset_ref")),
        json_output=bool(getattr(args, "json_output", False)),
        cache_dir=getattr(args, "cache_dir", None),
    )
    return 0
