from __future__ import annotations

from ctxbench.dataset.cache import DatasetCache


class AmbiguousDatasetError(ValueError):
    """Raised when a dataset reference resolves to multiple cached materializations."""


class DatasetConflictDetector:
    @staticmethod
    def check(dataset_id: str, version: str, cache: DatasetCache) -> None:
        matches = cache.lookup(dataset_id, version)
        if len(matches) <= 1:
            return
        candidates = ", ".join(
            f"origin={item.origin!r} resolvedRevision={item.resolvedRevision!r}" for item in matches
        )
        raise AmbiguousDatasetError(
            f"Ambiguous dataset reference {dataset_id}@{version}. Conflicting candidates: {candidates}"
        )
