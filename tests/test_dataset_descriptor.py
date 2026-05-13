from __future__ import annotations

import json
from pathlib import Path

import pytest

from ctxbench.dataset.descriptor import DescriptorValidationError, DistributionDescriptor, load_descriptor


def _descriptor_payload() -> dict[str, object]:
    return {
        "id": "ctxbench/lattes",
        "datasetVersion": "0.2.0",
        "descriptorSchemaVersion": 1,
        "name": "CTXBench Lattes",
        "description": "Fixture descriptor",
        "releaseTag": "v0.2.0-dataset",
        "archive": {
            "type": "tar.gz",
            "url": "https://example.invalid/ctxbench-lattes-v0.2.0.tar.gz",
            "sha256": "a" * 64,
        },
    }


def test_distribution_descriptor_accepts_valid_required_and_optional_fields() -> None:
    descriptor = DistributionDescriptor(
        id="ctxbench/lattes",
        datasetVersion="0.2.0",
        descriptorSchemaVersion=1,
        archive_type="tar.gz",
        archive_url="https://example.invalid/ctxbench-lattes-v0.2.0.tar.gz",
        archive_sha256="a" * 64,
        name="CTXBench Lattes",
        description="Fixture descriptor",
        release_tag="v0.2.0-dataset",
    )

    assert descriptor.id == "ctxbench/lattes"
    assert descriptor.release_tag == "v0.2.0-dataset"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.pop("id"),
        lambda payload: payload.pop("datasetVersion"),
        lambda payload: payload.pop("descriptorSchemaVersion"),
        lambda payload: payload["archive"].pop("type"),
        lambda payload: payload["archive"].pop("url"),
        lambda payload: payload["archive"].pop("sha256"),
    ],
)
def test_load_descriptor_rejects_missing_required_fields(
    tmp_path: Path,
    mutator,
) -> None:
    payload = _descriptor_payload()
    archive = dict(payload["archive"])
    payload["archive"] = archive
    mutator(payload)
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DescriptorValidationError):
        load_descriptor(str(path), from_url=False)


def test_load_descriptor_from_local_file_returns_distribution_descriptor(tmp_path: Path) -> None:
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(_descriptor_payload()), encoding="utf-8")

    descriptor = load_descriptor(str(path), from_url=False)

    assert descriptor.id == "ctxbench/lattes"
    assert descriptor.datasetVersion == "0.2.0"
    assert descriptor.archive_url == "https://example.invalid/ctxbench-lattes-v0.2.0.tar.gz"


def test_load_descriptor_from_url_returns_distribution_descriptor(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(_descriptor_payload()).encode("utf-8")

    monkeypatch.setattr("ctxbench.dataset.descriptor.urlopen", lambda _: _Response())

    descriptor = load_descriptor("https://example.invalid/dataset.descriptor.json", from_url=True)

    assert descriptor.archive_sha256 == "a" * 64
    assert descriptor.name == "CTXBench Lattes"


def test_load_descriptor_accepts_optional_fields_when_present(tmp_path: Path) -> None:
    path = tmp_path / "descriptor.json"
    path.write_text(json.dumps(_descriptor_payload()), encoding="utf-8")

    descriptor = load_descriptor(str(path), from_url=False)

    assert descriptor.name == "CTXBench Lattes"
    assert descriptor.description == "Fixture descriptor"
    assert descriptor.release_tag == "v0.2.0-dataset"
