from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from urllib.request import urlopen

from ctxbench.dataset.archive import discover_dataset_manifest
from ctxbench.dataset.materialization import MaterializationManifest


@dataclass(slots=True)
class AcquisitionSource:
    source_type: str
    origin: str
    asset_name: str | None = None
    sha256: str | None = None
    sha256_url: str | None = None


@dataclass(slots=True)
class ResolvedArchiveSource:
    source_type: str
    origin: str
    archive_url: str
    asset_name: str | None = None
    release_tag_url: str | None = None


def is_archive_url(origin: str) -> bool:
    return origin.startswith(("http://", "https://")) and origin.endswith(".tar.gz")


def is_release_tag_url(origin: str) -> bool:
    return origin.startswith(("http://", "https://")) and "/releases/tag/" in origin


def classify_acquisition_source(
    *,
    origin: str,
    asset_name: str | None = None,
    sha256: str | None = None,
    sha256_url: str | None = None,
) -> AcquisitionSource:
    if is_release_tag_url(origin):
        return AcquisitionSource(
            source_type="github-release-tag",
            origin=origin,
            asset_name=asset_name,
            sha256=sha256,
            sha256_url=sha256_url,
        )
    if is_archive_url(origin):
        return AcquisitionSource(
            source_type="archive-url",
            origin=origin,
            asset_name=asset_name,
            sha256=sha256,
            sha256_url=sha256_url,
        )
    return AcquisitionSource(
        source_type="local-path" if Path(origin).expanduser().exists() else "git-origin",
        origin=origin,
        asset_name=asset_name,
        sha256=sha256,
        sha256_url=sha256_url,
    )


def require_checksum_for_remote_archive(source: AcquisitionSource) -> None:
    if source.source_type not in {"archive-url", "github-release-tag"}:
        return
    if not source.sha256 and not source.sha256_url:
        raise ValueError(
            "Archive or release-asset acquisition requires --sha256 or --sha256-url."
        )
    if source.source_type == "github-release-tag" and not source.asset_name:
        raise ValueError(
            "GitHub Release tag acquisition requires --asset-name."
        )


def resolve_release_asset_url(release_tag_url: str, asset_name: str) -> str:
    prefix = "https://github.com/"
    if not release_tag_url.startswith(prefix):
        raise ValueError(f"Unsupported GitHub Release tag URL: {release_tag_url}")
    marker = "/releases/tag/"
    if marker not in release_tag_url:
        raise ValueError(f"Unsupported GitHub Release tag URL: {release_tag_url}")
    repo_part, tag = release_tag_url[len(prefix):].split(marker, 1)
    if not repo_part or not tag:
        raise ValueError(f"Unsupported GitHub Release tag URL: {release_tag_url}")
    return f"{prefix}{repo_part}/releases/download/{tag}/{asset_name}"


def resolve_archive_source(source: AcquisitionSource) -> ResolvedArchiveSource:
    if source.source_type == "archive-url":
        return ResolvedArchiveSource(
            source_type=source.source_type,
            origin=source.origin,
            archive_url=source.origin,
        )
    if source.source_type == "github-release-tag":
        if not source.asset_name:
            raise ValueError("GitHub Release tag acquisition requires --asset-name.")
        return ResolvedArchiveSource(
            source_type=source.source_type,
            origin=source.origin,
            archive_url=resolve_release_asset_url(source.origin, source.asset_name),
            asset_name=source.asset_name,
            release_tag_url=source.origin,
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
    require_checksum_for_remote_archive(source)
    if source.sha256:
        return normalize_sha256(source.sha256)
    if source.sha256_url:
        return parse_sha256_text(download_text_fn(source.sha256_url))
    raise ValueError("Archive or release-asset acquisition requires --sha256 or --sha256-url.")


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
        resolvedRevision=None,
        origin=source.origin,
        materializedPath="",
        contentHash=None,
        fetchedAt="unavailable",
        ctxbenchVersion="unavailable",
        fetchMethod="archive-download",
        sourceType=source.source_type,
        archiveUrl=resolved.archive_url,
        releaseTagUrl=resolved.release_tag_url,
        assetName=resolved.asset_name,
        verifiedSha256=verified_sha256,
    )


def validate_discovered_manifest(
    manifest_path: Path,
    *,
    expected_dataset_id: str,
    expected_version: str,
) -> dict[str, object]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid dataset manifest payload: {manifest_path}")
    dataset_id = payload.get("id")
    version = payload.get("version")
    if dataset_id != expected_dataset_id:
        raise ValueError(
            f"Dataset identity mismatch: expected {expected_dataset_id!r}, got {dataset_id!r}."
        )
    if version != expected_version:
        raise ValueError(
            f"Dataset version mismatch: expected {expected_version!r}, got {version!r}."
        )
    return payload


def discover_and_validate_manifest(
    extraction_root: Path,
    *,
    expected_dataset_id: str,
    expected_version: str,
) -> Path:
    manifest_path = discover_dataset_manifest(extraction_root)
    validate_discovered_manifest(
        manifest_path,
        expected_dataset_id=expected_dataset_id,
        expected_version=expected_version,
    )
    return manifest_path
