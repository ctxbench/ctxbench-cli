from __future__ import annotations

import json
from pathlib import Path

from ctxbench.ai.engine import Engine
from ctxbench.commands.plan import plan_command
from ctxbench.dataset.cache import DatasetCache
from ctxbench.dataset.provider import LocalDatasetPackage
from ctxbench.dataset.resolver import DatasetResolver
from ctxbench.util.jsonl import read_jsonl


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = REPO_ROOT / "tests" / "fixtures" / "fake_dataset"
EXPERIMENT_PATH = FIXTURE_ROOT / "experiment.json"
DATASET_ROOT = FIXTURE_ROOT / "dataset"
FORBIDDEN_TERMS = ("lattes", "curriculum", "lattesprovider")


def test_fake_dataset_plan_workflow_is_provider_free(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(REPO_ROOT)

    provider_calls = {"engine_execute": 0}

    def fail_execute(self: Engine, *args: object, **kwargs: object) -> object:
        del self, args, kwargs
        provider_calls["engine_execute"] += 1
        raise AssertionError("Planning must not execute provider-backed model calls.")

    monkeypatch.setattr(Engine, "execute", fail_execute)

    cache = DatasetCache(cache_dir=tmp_path / "cache")
    resolver = DatasetResolver()
    package = resolver.resolve({"root": str(DATASET_ROOT)}, cache)

    assert isinstance(package, LocalDatasetPackage)
    assert package.identity() == "ctxbench/fake-dataset"
    assert package.version() == "0.1.0"
    assert package.list_instance_ids() == ["person-001"]
    assert package.list_question_ids() == ["task_role"]

    output_root = tmp_path / "planned"
    assert plan_command(str(EXPERIMENT_PATH), output=str(output_root), cache_dir=tmp_path / "cache") == 0

    trials = read_jsonl(output_root / "trials.jsonl")
    manifest = json.loads((output_root / "manifest.json").read_text(encoding="utf-8"))

    assert len(trials) == 1
    assert trials[0]["taskId"] == "task_role"
    assert "questionId" not in trials[0]
    assert trials[0]["dataset"]["id"] == "ctxbench/fake-dataset"
    assert trials[0]["question"] == "What role does Avery Example have?"

    serialized_trials = json.dumps(trials, ensure_ascii=False).lower()
    for term in FORBIDDEN_TERMS:
        assert term not in serialized_trials

    assert manifest["dataset"]["id"] == "ctxbench/fake-dataset"
    assert provider_calls["engine_execute"] == 0
