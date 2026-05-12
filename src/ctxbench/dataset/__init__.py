"""Dataset and provider helpers."""

from ctxbench.dataset.capabilities import DatasetCapabilityReport
from ctxbench.dataset.cache import DatasetCache, DatasetConflictError
from ctxbench.dataset.conflicts import AmbiguousDatasetError, DatasetConflictDetector
from ctxbench.dataset.inspect import build_inspect_result
from ctxbench.dataset.materialization import MaterializationManifest
from ctxbench.dataset.package import DatasetMetadata, DatasetPackage, StrategyDescriptor
from ctxbench.dataset.provider import DatasetProvider, LocalDatasetPackage
from ctxbench.dataset.resolver import DatasetNotFoundError, DatasetResolver, MultiDatasetError
from ctxbench.dataset.validation import validate_package

__all__ = [
    "AmbiguousDatasetError",
    "DatasetCache",
    "DatasetConflictDetector",
    "DatasetConflictError",
    "DatasetCapabilityReport",
    "DatasetMetadata",
    "DatasetNotFoundError",
    "DatasetPackage",
    "DatasetProvider",
    "DatasetResolver",
    "LocalDatasetPackage",
    "MaterializationManifest",
    "MultiDatasetError",
    "StrategyDescriptor",
    "build_inspect_result",
    "validate_package",
]
