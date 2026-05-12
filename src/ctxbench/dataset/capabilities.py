from __future__ import annotations

from dataclasses import dataclass

from ctxbench.dataset.package import DatasetMetadata, StrategyDescriptor


@dataclass(slots=True)
class DatasetCapabilityReport:
    identity: str
    version: str
    origin: str | None
    resolved_revision: str | None
    materialized_path: str | None
    content_hash: str | None
    metadata: DatasetMetadata
    mandatory_capabilities: dict[str, bool]
    optional_capabilities: dict[str, bool]
    contributed_tools: object | None
    evaluation_helpers: object | None
    strategy_descriptors: list[StrategyDescriptor]
    missing_mandatory: list[str]
    nonconformant_descriptors: list[str]
    conformant: bool
