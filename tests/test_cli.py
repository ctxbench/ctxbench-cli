import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.benchmark.models import ExperimentDataset
from copa.cli import main


def write_mock_experiment(path: Path) -> Path:
    example_root = Path(__file__).resolve().parents[1] / "examples" / "basic" / "datasets"
    path.write_text(
        json.dumps(
            {
                "id": "exp_test_mock_001",
                "dataset": {
                    "questions": str((example_root / "questions.json").resolve()),
                    "contexts": str((example_root / "contexts").resolve()),
                    "question_instances": str((example_root / "questions.instance.json").resolve()),
                },
                "factors": {
                    "model": [{"provider": "mock", "name": "mock"}],
                    "strategy": ["inline"],
                    "format": ["json", "text"],
                },
                "params": {
                    "common": {
                        "temperature": 0,
                    }
                },
                "evaluation": {
                    "enabled": True,
                },
                "trace": {
                    "enabled": True,
                    "save_raw_response": True,
                    "save_tool_calls": True,
                    "save_usage": True,
                    "save_errors": True,
                },
                "execution": {
                    "repeats": 1,
                    "output": "outputs",
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_experiment_validate_example(capsys):
    exit_code = main(["experiment", "validate", "examples/basic/experiment.json"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "valid experiment" in out


def test_experiment_expand_writes_runspecs_and_jsonl(tmp_path):
    out_dir = tmp_path / "runspecs"
    jsonl_path = tmp_path / "runspecs.jsonl"

    exit_code = main(
        [
            "experiment",
            "expand",
            "examples/basic/experiment.json",
            "--out",
            str(out_dir),
            "--jsonl",
            str(jsonl_path),
        ]
    )

    assert exit_code == 0
    files = sorted(out_dir.glob("*.json"))
    assert len(files) == 120
    assert all(path.name.startswith("rs_exp_basic_001_") for path in files)
    first = json.loads(files[0].read_text(encoding="utf-8"))
    assert first["provider"] in {"openai", "google"}
    assert first["params"]["model_name"] in {"gpt-5.4-nano", "gemini-3.1-flash-lite-preview"}
    assert first["strategy"] in {"inline", "mcp"}
    assert first["format"] in {"json", "html"}
    assert "temperature" in first["params"]
    assert "|" in first["id"]
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 120


def test_example_lattes_dataset_shape_is_supported():
    from copa.dataset.provider import DatasetProvider

    provider = DatasetProvider.from_dataset(
        ExperimentDataset(
            questions=str((Path("examples/basic/datasets/lattes/questions.json")).resolve()),
            contexts=str((Path("examples/basic/datasets/lattes/cvs")).resolve()),
            question_instances=str(
                (Path("examples/basic/datasets/lattes/questions.instance.json")).resolve()
            ),
        )
    )

    instance = provider.get_question_instance("q_oos_002", "5660469902738038")

    assert instance is not None
    assert instance.cvId == "5660469902738038"
    assert instance.lattesId == "5660469902738038"
    assert instance.researcherName == "Nabor das Chagas Mendonça"
    assert instance.evaluationType == "unanswerable"
    assert instance.metadata["researcherName"] == "Nabor das Chagas Mendonça"


def test_run_and_eval_jsonl_flow(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    runspecs_dir = tmp_path / "runspecs"
    results_dir = tmp_path / "results"
    eval_dir = tmp_path / "eval"
    results_jsonl = tmp_path / "results.jsonl"
    eval_jsonl = tmp_path / "eval.jsonl"

    assert (
        main(
                [
                    "experiment",
                    "expand",
                    str(experiment_path),
                    "--out",
                    str(runspecs_dir),
                ]
            )
        == 0
    )

    assert (
        main(
            [
                "run",
                str(runspecs_dir),
                "--out",
                str(results_dir),
                "--jsonl",
                str(results_jsonl),
            ]
        )
        == 0
    )

    result_files = sorted(results_dir.glob("*.json"))
    assert len(result_files) == 2
    assert all(path.name.startswith("rr_exp_test_mock_001_") for path in result_files)
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert result["evaluation"]["status"] == "evaluated"
    assert result["trace"]["aiTrace"]["metrics"]["model_calls"] == 1
    assert result["trace"]["aiTrace"]["events"][-1]["name"] == "engine.execute"
    assert "|" in result["runId"]
    assert results_jsonl.exists()

    assert (
        main(
            [
                "eval",
                str(results_jsonl),
                "--out",
                str(eval_dir),
                "--jsonl",
                str(eval_jsonl),
            ]
        )
        == 0
    )

    evaluated_files = sorted(eval_dir.glob("*.json"))
    assert len(evaluated_files) == 2
    assert all(path.name.startswith("re_exp_test_mock_001_") for path in evaluated_files)
    evaluated = json.loads(evaluated_files[0].read_text(encoding="utf-8"))
    assert evaluated["evaluation"]["status"] == "evaluated"
    assert evaluated["evaluation"]["passed"] is True
    assert eval_jsonl.exists()


def test_run_verbose_and_progress_logging(tmp_path, capsys):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    runspecs_dir = tmp_path / "runspecs"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(runspecs_dir)]) == 0

    exit_code = main(
        [
            "run",
            str(runspecs_dir),
            "--out",
            str(tmp_path / "results"),
            "--verbose",
            "--progress",
        ]
    )

    assert exit_code == 0
    stderr = capsys.readouterr().err
    assert "[PLAN]" in stderr
    assert "[EXECUTE]" in stderr
    assert "[WRITE]" in stderr
    assert "[DONE]" in stderr
    assert "Processing runs:" in stderr
