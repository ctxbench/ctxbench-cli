from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

from ctxbench.dataset.archive import discover_dataset_manifest
from ctxbench.dataset.descriptor import DistributionDescriptor
from ctxbench.dataset.materialization import MaterializationManifest


@dataclass(slots=True)
class AcquisitionSource:
    source_type: str
    origin: str
    sha256: str | None = None
    sha256_url: str | None = None
    sha256_file: str | None = None
    descriptor: DistributionDescriptor | None = None
    descriptor_source: str | None = None


@dataclass(slots=True)
class ResolvedArchiveSource:
    source_type: str
    origin: str
    archive_url: str | None = None
    archive_path: Path | None = None


class DescriptorManifestMismatchError(ValueError):
    """Raised when a descriptor does not match the extracted dataset manifest."""


def classify_acquisition_source(
    *,
    descriptor_url: str | None = None,
    descriptor_file: str | None = None,
    dataset_url: str | None = None,
    dataset_file: str | None = None,
    dataset_dir: str | None = None,
    sha256: str | None = None,
    sha256_url: str | None = None,
    sha256_file: str | None = None,
) -> AcquisitionSource:
    provided_sources = [
        ("descriptor-url", descriptor_url),
        ("descriptor-file", descriptor_file),
        ("archive-url", dataset_url),
        ("local-archive", dataset_file),
        ("local-directory", dataset_dir),
    ]
    selected = [(source_type, value) for source_type, value in provided_sources if value]
    if len(selected) != 1:
        raise ValueError(
            "Exactly one dataset source must be provided: "
            "--descriptor-url, --descriptor-file, --dataset-url, --dataset-file, or --dataset-dir."
        )
    source_type, origin = selected[0]
    return AcquisitionSource(
        source_type=source_type,
        origin=origin,
        sha256=sha256,
        sha256_url=sha256_url,
        sha256_file=sha256_file,
    )


def require_checksum_for_archive_source(source: AcquisitionSource) -> None:
    if source.source_type not in {"archive-url", "local-archive"}:
        return
    if source.source_type == "archive-url" and not source.sha256 and not source.sha256_url:
        raise ValueError(
            "Remote archive acquisition requires --sha256 or --sha256-url."
        )
    if source.source_type == "local-archive" and not source.sha256 and not source.sha256_file:
        raise ValueError(
            "Local archive acquisition requires --sha256 or --sha256-file."
        )


def require_checksum_for_remote_archive(source: AcquisitionSource) -> None:
    """Compatibility wrapper retained for provider-free lifecycle tests."""
    require_checksum_for_archive_source(source)


def resolve_archive_source(source: AcquisitionSource) -> ResolvedArchiveSource:
    if source.source_type in {"descriptor-url", "descriptor-file"}:
        if source.descriptor is None:
            raise ValueError(f"Descriptor source is missing descriptor metadata: {source.origin}")
        return ResolvedArchiveSource(
            source_type=source.source_type,
            origin=source.origin,
            archive_url=source.descriptor.archive_url,
        )
    if source.source_type == "archive-url":
        return ResolvedArchiveSource(
            source_type=source.source_type,
            origin=source.origin,
            archive_url=source.origin,
        )
    if source.source_type == "local-archive":
        archive_path = Path(source.origin).expanduser()
        if not archive_path.exists() or not archive_path.is_file():
            raise FileNotFoundError(f"Dataset archive not found: {source.origin}")
        return ResolvedArchiveSource(
            source_type=source.source_type,
            origin=source.origin,
            archive_path=archive_path,
        )
    raise ValueError(f"Archive resolution does not apply to source type: {source.source_type}")


def download_bytes(url: str) -> bytes:
    with urlopen(url) as response:
        return response.read()


def download_text(url: str) -> str:
    return download_bytes(url).decode("utf-8")


def parse_sha256_text(payload: str) -> str:
    match = re.search(r"\b([0-9a-fA-F]{64})\b", payload)
    if match is None:
        raise ValueError("Unable to parse SHA-256 from checksum content.")
    return match.group(1).lower()


def normalize_sha256(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned.startswith("sha256:"):
        cleaned = cleaned[len("sha256:"):]
    if not re.fullmatch(r"[0-9a-f]{64}", cleaned):
        raise ValueError("Invalid SHA-256 value.")
    return cleaned


def resolve_expected_sha256(
    source: AcquisitionSource,
    *,
    download_text_fn=download_text,
) -> str:
    if source.source_type in {"descriptor-url", "descriptor-file"}:
        if source.descriptor is None:
            raise ValueError(f"Descriptor source is missing descriptor metadata: {source.origin}")
        return normalize_sha256(source.descriptor.archive_sha256)
    require_checksum_for_archive_source(source)
    if source.sha256:
        return normalize_sha256(source.sha256)
    if source.source_type == "archive-url" and source.sha256_url:
        return parse_sha256_text(download_text_fn(source.sha256_url))
    if source.source_type == "local-archive" and source.sha256_file:
        payload = Path(source.sha256_file).expanduser().read_text(encoding="utf-8")
        return parse_sha256_text(payload)
    if source.source_type == "archive-url":
        raise ValueError("Remote archive acquisition requires --sha256 or --sha256-url.")
    raise ValueError("Local archive acquisition requires --sha256 or --sha256-file.")


def verify_downloaded_bytes(payload: bytes, expected_sha256: str) -> str:
    expected = normalize_sha256(expected_sha256)
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError(
            f"SHA-256 mismatch: expected {expected}, got {actual}."
        )
    return f"sha256:{actual}"


def build_archive_materialization_manifest(
    *,
    dataset_id: str,
    version: str,
    source: AcquisitionSource,
    resolved: ResolvedArchiveSource,
    verified_sha256: str,
) -> MaterializationManifest:
    return MaterializationManifest(
        datasetId=dataset_id,
        requestedVersion=version,
        datasetVersion=version,
        resolvedRevision=None,
        origin=source.origin,
        materializedPath="",
        contentHash=None,
        fetchedAt="unavailable",
        ctxbenchVersion="unavailable",
        fetchMethod="archive-download",
        sourceType=source.source_type,
        archiveUrl=resolved.archive_url,
        releaseTagUrl=None,
        assetName=None,
        verifiedSha256=verified_sha256,
        descriptorUrl=source.descriptor_source,
        descriptorSchemaVersion=source.descriptor.descriptorSchemaVersion if source.descriptor else None,
    )


def validate_discovered_manifest(
    manifest_path: Path,
    *,
    expected_dataset_id: str | None = None,
    expected_version: str | None = None,
) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid dataset manifest payload: {manifest_path}")
    dataset_id = payload.get("id")
    version = payload.get("datasetVersion", payload.get("version"))
    if not isinstance(dataset_id, str) or not dataset_id:
        raise ValueError(f"Dataset manifest missing string 'id': {manifest_path}")
    if not isinstance(version, str) or not version:
        raise ValueError(f"Dataset manifest missing string 'datasetVersion': {manifest_path}")
    if expected_dataset_id is not None and dataset_id != expected_dataset_id:
        raise ValueError(
            f"Dataset identity mismatch: expected {expected_dataset_id!r}, got {dataset_id!r}."
        )
    if expected_version is not None and version != expected_version:
        raise ValueError(
            f"Dataset version mismatch: expected {expected_version!r}, got {version!r}."
        )
    return payload


def discover_and_validate_manifest(
    extraction_root: Path,
    *,
    expected_dataset_id: str | None = None,
    expected_version: str | None = None,
) -> tuple[Path, dict[str, object]]:
    manifest_path = discover_dataset_manifest(extraction_root)
    payload = validate_discovered_manifest(
        manifest_path,
        expected_dataset_id=expected_dataset_id,
        expected_version=expected_version,
    )
    return manifest_path, payload


def content_identity_for_source(source: AcquisitionSource) -> str | None:
    if source.source_type in {"descriptor-url", "descriptor-file"}:
        if source.descriptor is None:
            raise ValueError(f"Descriptor source is missing descriptor metadata: {source.origin}")
        return f"sha256:{normalize_sha256(source.descriptor.archive_sha256)}"
    if source.source_type == "archive-url":
        if source.sha256:
            return f"sha256:{normalize_sha256(source.sha256)}"
        if source.sha256_url:
            return f"sha256:{parse_sha256_text(download_text(source.sha256_url))}"
    if source.source_type == "local-archive":
        if source.sha256:
            return f"sha256:{normalize_sha256(source.sha256)}"
        if source.sha256_file:
            payload = Path(source.sha256_file).expanduser().read_text(encoding="utf-8")
            return f"sha256:{parse_sha256_text(payload)}"
    return None


def validate_descriptor_against_manifest(
    descriptor: DistributionDescriptor,
    manifest_payload: dict[str, object],
) -> None:
    dataset_id = manifest_payload.get("id")
    version = manifest_payload.get("datasetVersion", manifest_payload.get("version"))
    if dataset_id != descriptor.id:
        raise DescriptorManifestMismatchError(
            f"Descriptor identity mismatch: descriptor={descriptor.id!r}, manifest={dataset_id!r}."
        )
    if version != descriptor.datasetVersion:
        raise DescriptorManifestMismatchError(
            "Descriptor datasetVersion mismatch: "
            f"descriptor={descriptor.datasetVersion!r}, manifest={version!r}."
        )
