from __future__ import annotations

from pathlib import Path

from copa.benchmark.models import Experiment, ExperimentDataset
from copa.dataset.questions import (
    Question,
    QuestionDataset,
    QuestionInstance,
    QuestionInstanceDataset,
    QuestionInstanceEntry,
)
from copa.util.fs import load_json


FORMAT_ARTIFACTS = {
    "html": "clean.html",
    "raw_html": "raw.html",
    "cleaned_html": "clean.html",
    "clean_html": "clean.html",
    "json": "parsed.json",
    "parsed_json": "parsed.json",
    "blocks": "blocks.json",
}


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

    def list_instance_ids(self) -> list[str]:
        return [instance.instanceId for instance in self._question_instances.instances]

    def list_context_ids(self, format_name: str | None = None) -> list[str]:
        return self.list_instance_ids()

    def get_question(self, question_id: str) -> Question:
        for question in self._questions.questions:
            if question.id == question_id:
                return question
        raise KeyError(f"Unknown question id: {question_id}")

    def get_instance(self, instance_id: str) -> QuestionInstance:
        for instance in self._question_instances.instances:
            if instance.instanceId == instance_id:
                return instance
        raise KeyError(f"Unknown instance id: {instance_id}")

    def get_question_instance(self, question_id: str, context_id: str) -> QuestionInstanceEntry | None:
        instance = self.get_instance(context_id)
        return instance.get_question(question_id)

    def list_question_ids_for_instance(self, instance_id: str) -> list[str]:
        instance = self.get_instance(instance_id)
        return [item.id for item in instance.questions]

    def get_instance_dir(self, instance_id: str) -> Path:
        path = Path(self.dataset_paths.contexts) / instance_id
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Missing context directory for instance '{instance_id}': {path}")
        return path

    def get_context_artifact_path(self, instance_id: str, format_name: str) -> Path:
        filename = FORMAT_ARTIFACTS.get(format_name, format_name)
        path = self.get_instance_dir(instance_id) / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing context artifact: {path}")
        return path

    def get_context(self, context_id: str, format_name: str) -> str:
        path = self.get_context_artifact_path(context_id, format_name)
        return path.read_text(encoding="utf-8")

    def get_context_blocks(self, instance_id: str) -> dict[str, object]:
        instance = self.get_instance(instance_id)
        path = Path(self.dataset_paths.root) / instance.contextBlocks if instance.contextBlocks else None
        if path is None or not path.exists() or path.is_dir():
            path = self.get_instance_dir(instance_id) / "blocks.json"
        payload = load_json(path)
        if not isinstance(payload, dict):
            raise ValueError(f"Context blocks must be a JSON object: {path}")
        return payload

    def _load_question_instances(self, path: str | None) -> QuestionInstanceDataset:
        if not path or not Path(path).exists():
            return QuestionInstanceDataset(datasetId="missing", instances=[])
        raw = load_json(path)
        if not isinstance(raw, dict):
            raise ValueError("Question instances dataset must be a JSON object.")
        return QuestionInstanceDataset.model_validate(raw)
