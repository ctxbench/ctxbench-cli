from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ctxbench.dataset.capabilities import DatasetCapabilityReport


@dataclass(slots=True)
class DatasetMetadata:
    name: str
    description: str
    domain: str
    intended_uses: str
    limitations: str
    license_url: str | None
    citation_url: str | None


@dataclass(slots=True)
class StrategyDescriptor:
    name: str
    classification: str
    context_access_mode: str
    inline_vs_operation: str
    local_vs_remote: str
    loop_ownership: str
    metric_provenance: dict[str, str]
    observability_limitations: str
    comparability_implications: str


@runtime_checkable
class DatasetPackage(Protocol):
    def metadata(self) -> DatasetMetadata: ...

    def identity(self) -> str: ...

    def version(self) -> str: ...

    def origin(self) -> str | None: ...

    def list_instance_ids(self) -> list[str]: ...

    def list_task_ids(self) -> list[str]: ...

    def get_context_artifact(
        self,
        instance_id: str,
        task_id: str,
        strategy: str,
        format_name: str,
    ) -> object: ...

    def get_evidence_artifact(self, instance_id: str, task_id: str) -> object: ...

    def fixtures(self) -> object: ...

    def capability_report(self) -> DatasetCapabilityReport: ...

    # Optional extension points. They are documented here but not required by the
    # runtime structural check used by the S1 contract tests.
    def tool_provider(self) -> object | None:
        return None

    def evaluation_helpers(self) -> object | None:
        return None

    def strategy_descriptors(self) -> list[StrategyDescriptor] | None:
        return None
