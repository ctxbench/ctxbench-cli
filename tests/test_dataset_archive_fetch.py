from __future__ import annotations

import hashlib

import pytest

from ctxbench.dataset.acquisition import (
    AcquisitionSource,
    build_archive_materialization_manifest,
    classify_acquisition_source,
    require_checksum_for_remote_archive,
    resolve_archive_source,
    resolve_expected_sha256,
    verify_downloaded_bytes,
)


def test_direct_archive_url_with_sha256() -> None:
    payload = b"fake-archive-payload"
    digest = hashlib.sha256(payload).hexdigest()
    source = classify_acquisition_source(
        origin="https://example.invalid/ctxbench-lattes-v0.1.0.tar.gz",
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
    assert verified == f"sha256:{digest}"
    assert manifest.fetchMethod == "archive-download"
    assert manifest.sourceType == "archive-url"
    assert manifest.archiveUrl == resolved.archive_url
    assert manifest.releaseTagUrl is None
    assert manifest.assetName is None
    assert manifest.verifiedSha256 == f"sha256:{digest}"


def test_direct_archive_url_with_sha256_url() -> None:
    payload = b"archive-via-sha256-url"
    digest = hashlib.sha256(payload).hexdigest()
    source = classify_acquisition_source(
        origin="https://example.invalid/dataset.tar.gz",
        sha256_url="https://example.invalid/dataset.tar.gz.sha256",
    )

    expected = resolve_expected_sha256(
        source,
        download_text_fn=lambda _: f"{digest}  dataset.tar.gz\n",
    )
    verified = verify_downloaded_bytes(payload, expected)

    assert expected == digest
    assert verified == f"sha256:{digest}"


def test_release_tag_url_plus_asset_name() -> None:
    payload = b"release-archive"
    digest = hashlib.sha256(payload).hexdigest()
    source = classify_acquisition_source(
        origin="https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset",
        asset_name="ctxbench-lattes-v0.1.0.tar.gz",
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

    assert resolved.archive_url == (
        "https://github.com/ctxbench/lattes/releases/download/"
        "v0.1.0-dataset/ctxbench-lattes-v0.1.0.tar.gz"
    )
    assert resolved.release_tag_url == source.origin
    assert manifest.sourceType == "github-release-tag"
    assert manifest.releaseTagUrl == source.origin
    assert manifest.assetName == "ctxbench-lattes-v0.1.0.tar.gz"
    assert manifest.archiveUrl == resolved.archive_url


def test_missing_checksum_rejected_before_download() -> None:
    source = classify_acquisition_source(
        origin="https://example.invalid/dataset.tar.gz",
    )

    with pytest.raises(ValueError):
        require_checksum_for_remote_archive(source)


def test_invalid_checksum_rejected() -> None:
    source = AcquisitionSource(
        source_type="archive-url",
        origin="https://example.invalid/dataset.tar.gz",
        sha256="not-a-valid-sha",
    )

    with pytest.raises(ValueError):
        resolve_expected_sha256(source)


def test_release_tag_requires_asset_name() -> None:
    source = classify_acquisition_source(
        origin="https://github.com/ctxbench/lattes/releases/tag/v0.1.0-dataset",
        sha256="a" * 64,
    )

    with pytest.raises(ValueError):
        require_checksum_for_remote_archive(source)
