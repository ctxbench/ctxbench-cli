from __future__ import annotations

import json
from pathlib import Path

from ctxbench.benchmark.models import ExperimentDataset
from ctxbench.dataset.cache import DatasetCache
from ctxbench.dataset.package import DatasetPackage
from ctxbench.dataset.provider import LocalDatasetPackage
from ctxbench.dataset.resolver import DatasetResolver


def _write_local_dataset(root: Path) -> Path:
    instance_dir = root / "context" / "cv-demo"
    instance_dir.mkdir(parents=True, exist_ok=True)
    (root / "questions.json").write_text(
        json.dumps(
            {
                "datasetId": "ctxbench/local-fixture",
                "version": "0.1.0",
                "domain": "testing",
                "description": "Local package fixture.",
                "questions": [
                    {
                        "id": "q_year",
                        "question": "In which year did {researcher_name} obtain their PhD?",
                        "tags": ["objective", "simple"],
                        "validation": {"type": "judge"},
                        "contextBlock": ["summary"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "questions.instance.json").write_text(
        json.dumps(
            {
                "datasetId": "ctxbench/local-fixture",
                "version": "0.1.0",
                "instances": [
                    {
                        "instanceId": "cv-demo",
                        "contextBlocks": "context/cv-demo/blocks.json",
                        "questions": [
                            {"id": "q_year", "parameters": {"researcher_name": "CV Demo"}}
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(json.dumps({"answers": {"q_year": 2020}}), encoding="utf-8")
    (instance_dir / "clean.html").write_text("ANSWER[q_year]: 2020\n", encoding="utf-8")
    (instance_dir / "blocks.json").write_text(
        json.dumps({"summary": "Researcher in software engineering."}),
        encoding="utf-8",
    )
    return root


def test_local_dataset_package_resolves_as_dataset_package(tmp_path: Path) -> None:
    dataset_root = _write_local_dataset(tmp_path / "dataset")
    resolver = DatasetResolver()
    cache = DatasetCache(cache_dir=tmp_path / "cache")

    package = resolver.resolve(ExperimentDataset(root=str(dataset_root)), cache)

    assert isinstance(package, DatasetPackage)
    assert isinstance(package, LocalDatasetPackage)
    assert package.identity() == "ctxbench/local-fixture"
    assert package.version() == "0.1.0"


def test_local_dataset_package_preserves_question_template_and_instance_parameters(tmp_path: Path) -> None:
    dataset_root = _write_local_dataset(tmp_path / "dataset")
    package = LocalDatasetPackage.from_dataset(ExperimentDataset(root=str(dataset_root)))

    question = package.get_question("q_year")
    question_instance = package.get_question_instance("q_year", "cv-demo")

    assert question.question == "In which year did {researcher_name} obtain their PhD?"
    assert question.tags == ["objective", "simple"]
    assert question.validation.type == "judge"
    assert question.contextBlock == ["summary"]
    assert question_instance is not None
    assert question_instance.parameters == {"researcher_name": "CV Demo"}
    assert package.get_context_blocks("cv-demo") == {"summary": "Researcher in software engineering."}
    assert package.get_context_artifact("cv-demo", "q_year", "inline", "json") == {"answers": {"q_year": 2020}}
    assert package.get_evidence_artifact("cv-demo", "q_year") == {
        "question": {
            "id": "q_year",
            "question": "In which year did {researcher_name} obtain their PhD?",
            "tags": ["objective", "simple"],
            "validation": {"type": "judge"},
            "contextBlock": ["summary"],
        },
        "questionInstance": {"id": "q_year", "parameters": {"researcher_name": "CV Demo"}},
        "contextBlocks": {"summary": "Researcher in software engineering."},
    }


def test_local_dataset_package_accepts_string_and_root_forms_equivalently(tmp_path: Path) -> None:
    dataset_root = _write_local_dataset(tmp_path / "dataset")
    resolver = DatasetResolver()
    cache = DatasetCache(cache_dir=tmp_path / "cache")

    from_string = resolver.resolve(str(dataset_root), cache)
    from_root = resolver.resolve({"root": str(dataset_root)}, cache)

    assert isinstance(from_string, LocalDatasetPackage)
    assert isinstance(from_root, LocalDatasetPackage)
    assert from_string.identity() == from_root.identity()
    assert from_string.version() == from_root.version()
    assert from_string.origin() == from_root.origin()
