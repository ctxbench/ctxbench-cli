from __future__ import annotations

from pathlib import Path, PurePosixPath
import io
import tarfile


DATASET_MANIFEST_NAME = "ctxbench.dataset.json"


class UnsafeArchiveError(ValueError):
    """Raised when an archive contains unsafe entries."""


class DatasetManifestDiscoveryError(ValueError):
    """Raised when dataset manifest discovery fails."""


def safe_extract_tar_gz(payload: bytes, destination: Path) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as handle:
        members = handle.getmembers()
        for member in members:
            member_path = _validated_member_path(destination, member)
            if member.isdir():
                member_path.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise UnsafeArchiveError(f"Unsupported archive member type: {member.name}")
            member_path.parent.mkdir(parents=True, exist_ok=True)
            extracted = handle.extractfile(member)
            if extracted is None:
                raise UnsafeArchiveError(f"Unable to extract archive member: {member.name}")
            member_path.write_bytes(extracted.read())
            written.append(member_path)

    return written


def determine_package_root(extraction_root: Path) -> Path:
    entries = [entry for entry in extraction_root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extraction_root


def discover_dataset_manifest(extraction_root: Path) -> Path:
    package_root = determine_package_root(extraction_root)
    manifests = sorted(package_root.rglob(DATASET_MANIFEST_NAME))
    if not manifests:
        raise DatasetManifestDiscoveryError(
            f"No dataset manifest '{DATASET_MANIFEST_NAME}' found in extracted archive."
        )
    if len(manifests) > 1:
        raise DatasetManifestDiscoveryError(
            f"Multiple dataset manifests '{DATASET_MANIFEST_NAME}' found in extracted archive."
        )
    manifest = manifests[0]
    if manifest.parent != package_root:
        raise DatasetManifestDiscoveryError(
            f"Dataset manifest must be at the package root: {manifest}"
        )
    return manifest


def _validated_member_path(destination: Path, member: tarfile.TarInfo) -> Path:
    if member.issym() or member.islnk():
        raise UnsafeArchiveError(f"Links are not allowed in dataset archives: {member.name}")
    if member.isfifo():
        raise UnsafeArchiveError(f"FIFOs are not allowed in dataset archives: {member.name}")
    if member.isdev():
        raise UnsafeArchiveError(f"Device nodes are not allowed in dataset archives: {member.name}")

    parts = PurePosixPath(member.name).parts
    if not parts:
        raise UnsafeArchiveError("Archive contains an empty path entry.")
    if PurePosixPath(member.name).is_absolute():
        raise UnsafeArchiveError(f"Absolute paths are not allowed in dataset archives: {member.name}")
    if any(part == ".." for part in parts):
        raise UnsafeArchiveError(f"Path traversal is not allowed in dataset archives: {member.name}")
    if any(part == "" for part in parts):
        raise UnsafeArchiveError(f"Malformed archive path: {member.name}")

    resolved = (destination / Path(*parts)).resolve()
    destination_resolved = destination.resolve()
    if destination_resolved not in resolved.parents and resolved != destination_resolved:
        raise UnsafeArchiveError(f"Archive entry escapes extraction root: {member.name}")
    return resolved
