from __future__ import annotations

from dataclasses import dataclass


VALID_FETCH_METHODS = {"git-clone", "file-copy"}


@dataclass(slots=True)
class MaterializationManifest:
    datasetId: str
    requestedVersion: str
    resolvedRevision: str | None
    origin: str
    materializedPath: str
    contentHash: str | None
    fetchedAt: str
    ctxbenchVersion: str
    fetchMethod: str

    def __post_init__(self) -> None:
        if self.fetchMethod not in VALID_FETCH_METHODS:
            raise ValueError(
                f"Unsupported fetchMethod '{self.fetchMethod}'. "
                f"Expected one of: {', '.join(sorted(VALID_FETCH_METHODS))}."
            )
