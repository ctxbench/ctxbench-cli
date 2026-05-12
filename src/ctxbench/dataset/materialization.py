from __future__ import annotations

from dataclasses import dataclass


VALID_FETCH_METHODS = {"archive-download", "git-clone", "file-copy"}


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
    datasetVersion: str | None = None
    sourceType: str | None = None
    archiveUrl: str | None = None
    releaseTagUrl: str | None = None
    assetName: str | None = None
    verifiedSha256: str | None = None

    def __post_init__(self) -> None:
        if self.datasetVersion is None:
            self.datasetVersion = self.requestedVersion
        elif self.requestedVersion != self.datasetVersion:
            raise ValueError(
                "Materialization manifest requestedVersion must match datasetVersion when both are present."
            )
        if self.fetchMethod not in VALID_FETCH_METHODS:
            raise ValueError(
                f"Unsupported fetchMethod '{self.fetchMethod}'. "
                f"Expected one of: {', '.join(sorted(VALID_FETCH_METHODS))}."
            )
