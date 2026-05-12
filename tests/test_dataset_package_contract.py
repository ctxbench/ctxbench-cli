from __future__ import annotations

import pytest

from ctxbench.dataset.capabilities import DatasetCapabilityReport
from ctxbench.dataset.package import DatasetMetadata, DatasetPackage, StrategyDescriptor


def _metadata() -> DatasetMetadata:
    return DatasetMetadata(
        name="Fake Dataset",
        description="Synthetic dataset for contract testing.",
        domain="testing",
        intended_uses="Protocol and capability checks.",
        limitations="Not a real benchmark dataset.",
        license_url=None,
        citation_url=None,
    )


def _capability_report(*, conformant: bool = True) -> DatasetCapabilityReport:
    return DatasetCapabilityReport(
        identity="ctxbench/fake",
        version="0.1.0",
        origin=None,
        resolved_revision=None,
        materialized_path=None,
        content_hash=None,
        metadata=_metadata(),
        mandatory_capabilities={"instances": True, "tasks": True},
        optional_capabilities={"tool_provider": False},
        contributed_tools=None,
        evaluation_helpers=None,
        strategy_descriptors=[],
        missing_mandatory=[] if conformant else ["get_context_artifact"],
        nonconformant_descriptors=[],
        conformant=conformant,
    )


class CompleteDatasetPackage:
    def metadata(self) -> DatasetMetadata:
        return _metadata()

    def identity(self) -> str:
        return "ctxbench/fake"

    def version(self) -> str:
        return "0.1.0"

    def origin(self) -> str | None:
        return None

    def list_instance_ids(self) -> list[str]:
        return ["inst-001"]

    def list_task_ids(self) -> list[str]:
        return ["task-001"]

    def get_context_artifact(
        self,
        instance_id: str,
        task_id: str,
        strategy: str,
        format_name: str,
    ) -> object:
        return {"instance": instance_id, "task": task_id, "strategy": strategy, "format": format_name}

    def get_evidence_artifact(self, instance_id: str, task_id: str) -> object:
        return {"instance": instance_id, "task": task_id}

    def fixtures(self) -> object:
        return {"fixture": "ok"}

    def capability_report(self) -> DatasetCapabilityReport:
        return _capability_report()

    def tool_provider(self) -> object | None:
        return None

    def evaluation_helpers(self) -> object | None:
        return None

    def strategy_descriptors(self) -> list[StrategyDescriptor] | None:
        return None


class MissingMandatoryMethod:
    def metadata(self) -> DatasetMetadata:
        return _metadata()

    def identity(self) -> str:
        return "ctxbench/fake"

    def version(self) -> str:
        return "0.1.0"

    def origin(self) -> str | None:
        return None

    def list_instance_ids(self) -> list[str]:
        return ["inst-001"]

    def list_task_ids(self) -> list[str]:
        return ["task-001"]

    def get_context_artifact(
        self,
        instance_id: str,
        task_id: str,
        strategy: str,
        format_name: str,
    ) -> object:
        return {"instance": instance_id, "task": task_id, "strategy": strategy, "format": format_name}

    def fixtures(self) -> object:
        return {"fixture": "ok"}

    def capability_report(self) -> DatasetCapabilityReport:
        return _capability_report(conformant=False)

    def tool_provider(self) -> object | None:
        return None

    def evaluation_helpers(self) -> object | None:
        return None

    def strategy_descriptors(self) -> list[StrategyDescriptor] | None:
        return None


def test_dataset_package_protocol_accepts_complete_implementation() -> None:
    assert isinstance(CompleteDatasetPackage(), DatasetPackage)


def test_dataset_package_protocol_rejects_missing_mandatory_method() -> None:
    assert not isinstance(MissingMandatoryMethod(), DatasetPackage)


def test_strategy_descriptor_accepts_all_required_fields() -> None:
    descriptor = StrategyDescriptor(
        name="inline",
        classification="canonical",
        context_access_mode="inline-context",
        inline_vs_operation="inline",
        local_vs_remote="local",
        loop_ownership="benchmark",
        metric_provenance={"totalTokens": "reported"},
        observability_limitations="None",
        comparability_implications="Comparable with canonical inline runs.",
    )

    assert descriptor.name == "inline"
    assert descriptor.metric_provenance == {"totalTokens": "reported"}


def test_strategy_descriptor_missing_required_field_raises_type_error() -> None:
    with pytest.raises(TypeError):
        StrategyDescriptor(
            name="inline",
            classification="canonical",
            context_access_mode="inline-context",
            inline_vs_operation="inline",
            local_vs_remote="local",
            loop_ownership="benchmark",
            metric_provenance={"totalTokens": "reported"},
            observability_limitations="None",
        )


def test_dataset_capability_report_represents_nonconformant_package() -> None:
    report = _capability_report(conformant=False)

    assert report.conformant is False
    assert report.missing_mandatory == ["get_context_artifact"]
