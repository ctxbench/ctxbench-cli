import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.cli import main


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
    assert len(files) == 2
    first = json.loads(files[0].read_text(encoding="utf-8"))
    assert first["model"] == "mock"
    assert first["strategy"] == "inline"
    assert first["format"] in {"json", "text"}
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 2


def test_run_and_eval_jsonl_flow(tmp_path):
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
                "examples/basic/experiment.json",
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
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert result["evaluation"]["status"] == "evaluated"
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
    evaluated = json.loads(evaluated_files[0].read_text(encoding="utf-8"))
    assert evaluated["evaluation"]["status"] == "evaluated"
    assert evaluated["evaluation"]["passed"] is True
    assert eval_jsonl.exists()
