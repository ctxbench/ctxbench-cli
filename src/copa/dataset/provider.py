from __future__ import annotations

from pathlib import Path

from copa.benchmark.models import Experiment, ExperimentDataset
from copa.dataset.contexts import context_path, extension_for_format
from copa.dataset.questions import (
    Question,
    QuestionDataset,
    QuestionInstance,
    QuestionInstanceDataset,
)
from copa.util.fs import load_json


class DatasetProvider:
    def __init__(self, dataset_paths: ExperimentDataset) -> None:
        self.dataset_paths = dataset_paths
        self._questions = QuestionDataset.model_validate(load_json(dataset_paths.questions))
        self._question_instances = self._load_question_instances(dataset_paths.question_instances)

    @classmethod
    def from_experiment(cls, experiment: Experiment, base_dir: str | Path) -> "DatasetProvider":
        base = Path(base_dir)
        dataset = ExperimentDataset(root=str((base / experiment.dataset.root).resolve()))
        return cls(dataset)

    @classmethod
    def from_dataset(cls, dataset: ExperimentDataset) -> "DatasetProvider":
        return cls(dataset)

    def list_question_ids(self) -> list[str]:
        return [question.id for question in self._questions.questions]

    def get_question(self, question_id: str) -> Question:
        for question in self._questions.questions:
            if question.id == question_id:
                return question
        raise KeyError(f"Unknown question id: {question_id}")

    def list_context_ids(self, format_name: str) -> list[str]:
        contexts_dir = Path(self.dataset_paths.contexts)
        suffix = extension_for_format(format_name)
        return sorted(path.stem for path in contexts_dir.glob(f"*{suffix}") if path.is_file())

    def get_context(self, context_id: str, format_name: str) -> str:
        path = context_path(self.dataset_paths.contexts, context_id, format_name)
        if not path.exists():
            raise FileNotFoundError(f"Missing context artifact: {path}")
        return path.read_text(encoding="utf-8")

    def get_question_instance(self, question_id: str, context_id: str) -> QuestionInstance | None:
        for instance in self._question_instances.instances:
            if instance.questionId == question_id and instance.cvId == context_id:
                return instance
        question = self.get_question(question_id)
        return None if question is None else None

    def _load_question_instances(self, path: str | None) -> QuestionInstanceDataset:
        if not path or not Path(path).exists():
            return QuestionInstanceDataset(datasetId="missing", instances=[])
        raw = self._normalize_question_instance_dataset(load_json(path), path)
        for instance in raw.get("instances", []):
            if "evaluationType" not in instance:
                question = next(
                    (item for item in self._questions.questions if item.id == instance["questionId"]),
                    None,
                )
                if question is not None:
                    instance["evaluationType"] = question.evaluationType
        return QuestionInstanceDataset.model_validate(raw)

    def _normalize_question_instance_dataset(
        self, raw: object, path: str
    ) -> dict[str, object]:
        if isinstance(raw, list):
            payload: dict[str, object] = {
                "datasetId": Path(path).stem,
                "instances": raw,
            }
        elif isinstance(raw, dict):
            payload = dict(raw)
        else:
            raise ValueError("Question instances dataset must be an object or an array.")

        raw_instances = payload.get("instances", [])
        if not isinstance(raw_instances, list):
            raise ValueError("Question instances dataset field 'instances' must be a list.")

        payload["instances"] = [self._normalize_question_instance(item) for item in raw_instances]
        return payload

    def _normalize_question_instance(self, raw: object) -> dict[str, object]:
        if not isinstance(raw, dict):
            raise ValueError("Question instance entries must be objects.")

        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}

        normalized = dict(raw)
        normalized["cvId"] = str(
            raw.get("cvId")
            or raw.get("instanceId")
            or raw.get("contextId")
            or raw.get("lattesId")
            or ""
        )
        if raw.get("researcherName") is None and metadata.get("researcherName") is not None:
            normalized["researcherName"] = metadata["researcherName"]
        if raw.get("lattesId") is None and raw.get("instanceId") is not None:
            normalized["lattesId"] = raw["instanceId"]
        normalized["metadata"] = metadata
        if raw.get("evaluationContext") is None and metadata.get("evaluationContext") is not None:
            normalized["evaluationContext"] = metadata["evaluationContext"]
        normalized.pop("instanceId", None)
        return normalized
