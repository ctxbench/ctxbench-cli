from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from urllib.request import urlopen


class DescriptorValidationError(ValueError):
    """Raised when a distribution descriptor is invalid."""


@dataclass(slots=True)
class DistributionDescriptor:
    id: str
    datasetVersion: str
    descriptorSchemaVersion: int
    archive_type: str
    archive_url: str
    archive_sha256: str
    name: str | None = None
    description: str | None = None
    release_tag: str | None = None

    def __post_init__(self) -> None:
        required = {
            "id": self.id,
            "datasetVersion": self.datasetVersion,
            "descriptorSchemaVersion": self.descriptorSchemaVersion,
            "archive.type": self.archive_type,
            "archive.url": self.archive_url,
            "archive.sha256": self.archive_sha256,
        }
        missing = [name for name, value in required.items() if value in (None, "")]
        if missing:
            joined = ", ".join(sorted(missing))
            raise DescriptorValidationError(f"Descriptor is missing required field(s): {joined}")
        if not isinstance(self.descriptorSchemaVersion, int):
            raise DescriptorValidationError("Descriptor field 'descriptorSchemaVersion' must be an integer.")


def load_descriptor(source: str, *, from_url: bool) -> DistributionDescriptor:
    if from_url:
        with urlopen(source) as response:
            payload = response.read().decode("utf-8")
    else:
        payload = Path(source).expanduser().read_text(encoding="utf-8")
    raw = json.loads(payload)
    if not isinstance(raw, dict):
        raise DescriptorValidationError("Descriptor payload must be a JSON object.")
    archive = raw.get("archive")
    if not isinstance(archive, dict):
        raise DescriptorValidationError("Descriptor field 'archive' must be a JSON object.")
    return DistributionDescriptor(
        id=_require_str(raw, "id"),
        datasetVersion=_require_str(raw, "datasetVersion"),
        descriptorSchemaVersion=_require_int(raw, "descriptorSchemaVersion"),
        archive_type=_require_str(archive, "type", prefix="archive."),
        archive_url=_require_str(archive, "url", prefix="archive."),
        archive_sha256=_require_str(archive, "sha256", prefix="archive."),
        name=_optional_str(raw.get("name"), "name"),
        description=_optional_str(raw.get("description"), "description"),
        release_tag=_optional_str(raw.get("releaseTag"), "releaseTag"),
    )


def _require_str(payload: dict[str, object], key: str, *, prefix: str = "") -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise DescriptorValidationError(f"Descriptor field {prefix}{key!r} must be a non-empty string.")
    return value


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int):
        raise DescriptorValidationError(f"Descriptor field {key!r} must be an integer.")
    return value


def _optional_str(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise DescriptorValidationError(f"Descriptor field {key!r} must be a string when present.")
    return value
