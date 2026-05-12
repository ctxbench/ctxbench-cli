from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from ctxbench.benchmark.models import ExperimentDataset
from ctxbench.dataset.capabilities import DatasetCapabilityReport
from ctxbench.dataset.materialization import MaterializationManifest
from ctxbench.dataset.package import DatasetPackage
from ctxbench.dataset.provider import LocalDatasetPackage
from ctxbench.dataset.validation import validate_package


def _package_for_validation(
    package: DatasetPackage,
    manifest: MaterializationManifest | None,
) -> DatasetPackage:
    if manifest is None:
        return package
    if isinstance(package, LocalDatasetPackage):
        return package
    materialized_path = Path(manifest.materializedPath)
    dataset = ExperimentDataset(
        root=str(materialized_path),
        id=manifest.datasetId,
        version=manifest.requestedVersion,
        origin=manifest.origin,
    )
    return LocalDatasetPackage.from_dataset(dataset)


def build_inspect_result(
    package: DatasetPackage,
    manifest: MaterializationManifest | None,
) -> DatasetCapabilityReport:
    report = validate_package(_package_for_validation(package, manifest))
    if manifest is None:
        return report
    return replace(
        report,
        identity=manifest.datasetId,
        version=manifest.requestedVersion,
        origin=manifest.origin,
        resolved_revision=manifest.resolvedRevision,
        materialized_path=manifest.materializedPath,
        content_hash=manifest.contentHash,
    )
