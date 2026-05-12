from __future__ import annotations

from pathlib import Path

from ctxbench.benchmark.models import ExperimentDataset
from ctxbench.dataset.capabilities import DatasetCapabilityReport
from ctxbench.dataset.provider import LocalDatasetPackage
from ctxbench.dataset.validation import validate_package
from ctxbench.datasets.lattes.mcp_server import build_lattes_mcp_server
from ctxbench.datasets.lattes.tools import LattesToolService


class LattesDatasetPackage(LocalDatasetPackage):
    def __init__(self, dataset_root: str | Path) -> None:
        root = str(Path(dataset_root).resolve())
        super().__init__(
            ExperimentDataset(
                root=root,
                id="ctxbench/lattes",
                version=self._detect_version(root),
                origin=root,
            )
        )
        self._root = root

    def identity(self) -> str:
        return "ctxbench/lattes"

    def version(self) -> str:
        return self.dataset_paths.version or self._detect_version(self._root)

    def fixtures(self) -> object:
        return self._root

    def tool_provider(self) -> object | None:
        return LattesToolService(contexts_dir=self.dataset_paths.contexts)

    def mcp_server(self) -> object:
        return build_lattes_mcp_server(contexts_dir=self.dataset_paths.contexts)

    def capability_report(self) -> DatasetCapabilityReport:
        report = validate_package(self)
        report.identity = self.identity()
        report.version = self.version()
        report.origin = self.origin()
        report.materialized_path = self._root
        return report

    @staticmethod
    def _detect_version(dataset_root: str | Path) -> str:
        root = Path(dataset_root)
        questions_payload = root / "questions.json"
        instances_payload = root / "questions.instance.json"
        if questions_payload.exists():
            import json

            payload = json.loads(questions_payload.read_text(encoding="utf-8"))
            version = payload.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
        if instances_payload.exists():
            import json

            payload = json.loads(instances_payload.read_text(encoding="utf-8"))
            reference_date = payload.get("referenceDate")
            if isinstance(reference_date, str) and reference_date.strip():
                return reference_date.strip()
            version = payload.get("version")
            if isinstance(version, str) and version.strip():
                return version.strip()
        return "unknown"
