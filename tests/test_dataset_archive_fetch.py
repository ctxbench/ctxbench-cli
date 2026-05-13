from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ctxbench.dataset.acquisition import (
    AcquisitionSource,
    build_archive_materialization_manifest,
    classify_acquisition_source,
    content_identity_for_source,
    require_checksum_for_archive_source,
    resolve_archive_source,
    resolve_expected_sha256,
    validate_descriptor_against_manifest,
    verify_downloaded_bytes,
)
from ctxbench.dataset.descriptor import DistributionDescriptor


def test_direct_archive_url_with_sha256() -> None:
    payload = b"fake-archive-payload"
    digest = hashlib.sha256(payload).hexdigest()
    source = classify_acquisition_source(
        dataset_url="https://example.invalid/ctxbench-lattes-v0.1.0.tar.gz",
        sha256=digest,
    )

    resolved = resolve_archive_source(source)
    expected = resolve_expected_sha256(source)
    verified = verify_downloaded_bytes(payload, expected)
    manifest = build_archive_materialization_manifest(
        dataset_id="ctxbench/lattes",
        version="v0.1.0",
        source=source,
        resolved=resolved,
        verified_sha256=verified,
    )

    assert resolved.archive_url == "https://example.invalid/ctxbench-lattes-v0.1.0.tar.gz"
    assert resolved.archive_path is None
    assert verified == f"sha256:{digest}"
    assert manifest.fetchMethod == "archive-download"
    assert manifest.sourceType == "archive-url"
    assert manifest.archiveUrl == resolved.archive_url
    assert manifest.releaseTagUrl is None
    assert manifest.assetName is None
    assert manifest.verifiedSha256 == f"sha256:{digest}"
    assert manifest.descriptorUrl is None
    assert manifest.descriptorSchemaVersion is None


def test_direct_archive_url_with_sha256_url() -> None:
    payload = b"archive-via-sha256-url"
    digest = hashlib.sha256(payload).hexdigest()
    source = classify_acquisition_source(
        dataset_url="https://example.invalid/dataset.tar.gz",
        sha256_url="https://example.invalid/dataset.tar.gz.sha256",
    )

    expected = resolve_expected_sha256(
        source,
        download_text_fn=lambda _: f"{digest}  dataset.tar.gz\n",
    )
    verified = verify_downloaded_bytes(payload, expected)

    assert expected == digest
    assert verified == f"sha256:{digest}"


def test_local_archive_with_sha256_file(tmp_path: Path) -> None:
    archive_path = tmp_path / "dataset.tar.gz"
    archive_path.write_bytes(b"local-archive")
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksum_path = tmp_path / "dataset.tar.gz.sha256"
    checksum_path.write_text(f"{digest}  dataset.tar.gz\n", encoding="utf-8")

    source = classify_acquisition_source(
        dataset_file=str(archive_path),
        sha256_file=str(checksum_path),
    )

    resolved = resolve_archive_source(source)
    expected = resolve_expected_sha256(source)

    assert resolved.archive_url is None
    assert resolved.archive_path == archive_path
    assert expected == digest


def test_missing_remote_checksum_rejected_before_download() -> None:
    source = classify_acquisition_source(
        dataset_url="https://example.invalid/dataset.tar.gz",
    )

    with pytest.raises(ValueError):
        require_checksum_for_archive_source(source)


def test_missing_local_archive_checksum_rejected() -> None:
    source = classify_acquisition_source(
        dataset_file="/tmp/dataset.tar.gz",
    )

    with pytest.raises(ValueError):
        require_checksum_for_archive_source(source)


def test_invalid_checksum_rejected() -> None:
    source = AcquisitionSource(
        source_type="archive-url",
        origin="https://example.invalid/dataset.tar.gz",
        sha256="not-a-valid-sha",
    )

    with pytest.raises(ValueError):
        resolve_expected_sha256(source)


def test_descriptor_source_resolves_archive_and_expected_sha256() -> None:
    descriptor = DistributionDescriptor(
        id="ctxbench/lattes",
        datasetVersion="0.2.0",
        descriptorSchemaVersion=1,
        archive_type="tar.gz",
        archive_url="https://example.invalid/ctxbench-lattes-v0.2.0.tar.gz",
        archive_sha256="a" * 64,
    )
    source = AcquisitionSource(
        source_type="descriptor-file",
        origin="/tmp/ctxbench-lattes.dataset.json",
        descriptor=descriptor,
        descriptor_source="/tmp/ctxbench-lattes.dataset.json",
    )

    resolved = resolve_archive_source(source)
    expected = resolve_expected_sha256(source)
    content_identity = content_identity_for_source(source)
    manifest = build_archive_materialization_manifest(
        dataset_id=descriptor.id,
        version=descriptor.datasetVersion,
        source=source,
        resolved=resolved,
        verified_sha256=f"sha256:{expected}",
    )

    assert resolved.archive_url == descriptor.archive_url
    assert expected == "a" * 64
    assert content_identity == "sha256:" + ("a" * 64)
    assert manifest.descriptorUrl == "/tmp/ctxbench-lattes.dataset.json"
    assert manifest.descriptorSchemaVersion == 1


def test_validate_descriptor_against_manifest_rejects_mismatch() -> None:
    descriptor = DistributionDescriptor(
        id="ctxbench/lattes",
        datasetVersion="0.2.0",
        descriptorSchemaVersion=1,
        archive_type="tar.gz",
        archive_url="https://example.invalid/ctxbench-lattes-v0.2.0.tar.gz",
        archive_sha256="a" * 64,
    )

    with pytest.raises(ValueError, match="Descriptor identity mismatch"):
        validate_descriptor_against_manifest(
            descriptor,
            {"id": "ctxbench/other", "datasetVersion": "0.2.0"},
        )
