import json
import re
import tomllib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.cli import _selector_from_args, build_parser, main


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_public_cli_parser_uses_ctxbench_prog_name():
    parser = build_parser()

    assert parser.prog == "ctxbench"
    help_output = parser.format_help()
    assert "usage: ctxbench" in help_output
    assert "CTXBench benchmark CLI" in help_output


def test_public_cli_exposes_execute_command_in_help():
    parser = build_parser()

    help_output = parser.format_help()
    assert "execute" in help_output
    assert "query" not in help_output
    assert "plan" in help_output
    assert "eval" in help_output
    assert "export" in help_output
    assert "status" in help_output


def test_execute_help_uses_target_public_terms(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["execute", "--help"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "usage: ctxbench execute" in out
    assert "Path to trials.jsonl" in out
    assert "responses already exist" in out
    assert "query" not in out


def test_query_and_exec_are_rejected_by_parser(capsys):
    parser = build_parser()

    for command in ("query", "exec"):
        with pytest.raises(SystemExit) as excinfo:
            parser.parse_args([command])
        assert excinfo.value.code == 2
        err = capsys.readouterr().err
        assert "invalid choice" in err
        assert f"'{command}'" in err


def test_execute_help_uses_target_selector_flags(capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["execute", "--help"])

    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "--task" in out
    assert "--repetition" in out
    assert "--trial-id" in out
    assert "--question" not in out
    assert "--repeat" not in out
    assert "--ids" not in out


def test_execute_parser_maps_target_selector_flags():
    parser = build_parser()

    args = parser.parse_args(
        [
            "execute",
            "--task", "q_year,q_summary",
            "--repetition", "1,2",
            "--trial-id", "run-a,run-b",
            "--not-task", "q_skip",
            "--not-repetition", "3",
        ]
    )
    selector = _selector_from_args(args)

    assert selector.task == ("q_year", "q_summary")
    assert selector.repetition == (1, 2)
    assert selector.trial_id == ("run-a", "run-b")
    assert selector.not_task == ("q_skip",)
    assert selector.not_repetition == (3,)


@pytest.mark.parametrize("flag", ["--question", "--repeat", "--ids"])
def test_execute_parser_rejects_legacy_selector_flags(flag, capsys):
    parser = build_parser()

    with pytest.raises(SystemExit) as excinfo:
        parser.parse_args(["execute", flag, "value"])

    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "unrecognized arguments" in err
    assert flag in err


def test_pyproject_exposes_ctxbench_script_only():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    scripts = pyproject["project"]["scripts"]

    assert scripts["ctxbench"] == "copa.cli:main"
    assert "copa" not in scripts


def test_flake_exposes_ctxbench_binary_and_app():
    flake = (REPO_ROOT / "flake.nix").read_text(encoding="utf-8")

    assert 'name = "ctxbench";' in flake
    assert '"$out/bin/ctxbench"' in flake
    assert 'program = "${ctxbenchPkg}/bin/ctxbench";' in flake
    assert '--add-flags "copa.cli"' in flake


def write_mock_experiment(path: Path, *, evaluation_enabled: bool = True) -> Path:
    dataset_root = path.parent / "dataset"
    instance_dir = dataset_root / "context" / "cv_demo"
    instance_dir.mkdir(parents=True, exist_ok=True)

    (dataset_root / "questions.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "questions": [
                    {
                        "id": "q_year",
                        "question": "In which year did the researcher obtain their PhD?",
                        "tags": ["objective", "simple"],
                        "validation": {"type": "judge"},
                        "contextBlock": ["summary"],
                    },
                    {
                        "id": "q_summary",
                        "question": "Summarize the main research areas for {researcher_name}.",
                        "tags": ["subjective", "simple"],
                        "validation": {"type": "judge"},
                        "contextBlock": ["summary", "research"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (dataset_root / "questions.instance.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "instances": [
                    {
                        "instanceId": "cv_demo",
                        "contextBlocks": "context/cv_demo/blocks.json",
                        "questions": [
                            {"id": "q_year"},
                            {
                                "id": "q_summary",
                                "parameters": {"researcher_name": "CV Demo"},
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(
        json.dumps(
            {
                "answers": {"q_year": 2018},
                "summary": {"text": "Researcher in software engineering."},
                "research": {"areas": ["software engineering", "distributed systems"]},
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "raw.html").write_text("ANSWER[q_year]: 2018\n", encoding="utf-8")
    (instance_dir / "clean.html").write_text("ANSWER[q_year]: 2018\n", encoding="utf-8")
    (instance_dir / "blocks.json").write_text(
        json.dumps(
            {
                "summary": "Researcher in software engineering.",
                "research": "Works with distributed systems.",
            }
        ),
        encoding="utf-8",
    )

    path.write_text(
        json.dumps(
            {
                "id": "exp_mock_v2",
                "output": "outputs",
                "dataset": str(dataset_root.resolve()),
                "scope": {"instances": ["cv_demo"], "questions": ["q_year", "q_summary"]},
                "factors": {
                    "model": [{"provider": "mock", "name": "mock"}],
                    "strategy": ["inline"],
                    "format": ["json"],
                },
                "params": {"common": {"temperature": 0}},
                "evaluation": {
                    "enabled": evaluation_enabled,
                    "judges": [{"provider": "mock", "model": "mock", "temperature": 0}],
                },
                "trace": {
                    "enabled": True,
                    "writeFiles": True,
                    "save_raw_response": True,
                    "save_tool_calls": True,
                    "save_usage": True,
                    "save_errors": True,
                },
                "execution": {"repeats": 1},
                "artifacts": {
                    "writeJsonl": True,
                    "writeIndividualJson": True,
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def add_mock_instance(dataset_root: Path, instance_id: str, *, researcher_name: str) -> None:
    source_instance_dir = dataset_root / "context" / "cv_demo"
    instance_dir = dataset_root / "context" / instance_id
    instance_dir.mkdir(parents=True, exist_ok=True)

    parsed_payload = json.loads((source_instance_dir / "parsed.json").read_text(encoding="utf-8"))
    (instance_dir / "parsed.json").write_text(json.dumps(parsed_payload), encoding="utf-8")
    (instance_dir / "raw.html").write_text((source_instance_dir / "raw.html").read_text(encoding="utf-8"), encoding="utf-8")
    (instance_dir / "clean.html").write_text((source_instance_dir / "clean.html").read_text(encoding="utf-8"), encoding="utf-8")
    (instance_dir / "blocks.json").write_text((source_instance_dir / "blocks.json").read_text(encoding="utf-8"), encoding="utf-8")

    questions_instance_path = dataset_root / "questions.instance.json"
    questions_instance_payload = json.loads(questions_instance_path.read_text(encoding="utf-8"))
    questions_instance_payload["instances"].append(
        {
            "instanceId": instance_id,
            "contextBlocks": f"context/{instance_id}/blocks.json",
            "questions": [
                {"id": "q_year"},
                {
                    "id": "q_summary",
                    "parameters": {"researcher_name": researcher_name},
                },
            ],
        }
    )
    questions_instance_path.write_text(json.dumps(questions_instance_payload), encoding="utf-8")


def rewrite_runspec_artifacts(runspec_jsonl: Path, *, write_jsonl: bool, write_individual_json: bool) -> None:
    rows = [json.loads(line) for line in runspec_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        row["artifacts"] = {
            "writeJsonl": write_jsonl,
            "writeIndividualJson": write_individual_json,
        }
    runspec_jsonl.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )


def rewrite_evaluation_manifest(expanded_root: Path, *, write_jsonl: bool, write_individual_json: bool) -> None:
    manifest_path = expanded_root / "evaluation.manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["evaluation"]["artifacts"] = {
        "writeJsonl": write_jsonl,
        "writeIndividualJson": write_individual_json,
    }
    manifest_path.write_text(json.dumps(payload), encoding="utf-8")


def test_experiment_validate_example(tmp_path, capsys):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    exit_code = main(["experiment", "validate", str(experiment_path)])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "valid experiment" in out


def test_experiment_expand_respects_scope_and_writes_runspecs(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    out_dir = tmp_path / "runspecs"
    jsonl_path = tmp_path / "runspecs.jsonl"

    exit_code = main(
        [
            "experiment",
            "expand",
            str(experiment_path),
            "--out",
            str(out_dir),
            "--jsonl",
            str(jsonl_path),
        ]
    )

    assert exit_code == 0
    files = sorted(path for path in out_dir.glob("rs_*.json"))
    assert len(files) == 2
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    first = rows[0]
    assert first["questionId"] in {"q_year", "q_summary"}
    assert first["instanceId"] == "cv_demo"
    assert first["modelId"] == "mock"
    assert first["validationType"] == "judge"
    assert first["contextBlock"] in (["summary"], ["summary", "research"])
    assert "dataset" in first
    summary = next(row for row in rows if row["questionId"] == "q_summary")
    assert summary["question"] == "Summarize the main research areas for CV Demo."
    assert summary["parameters"] == {"researcher_name": "CV Demo"}
    assert (out_dir / "runs.manifest.json").exists()
    assert (tmp_path / "evaluation.manifest.json").exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 2


def test_experiment_validate_rejects_duplicate_model_ids(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["factors"]["model"] = [
        {"id": "same", "provider": "mock", "name": "mock-a"},
        {"id": "same", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["experiment", "validate", str(experiment_path)]) == 1


def test_experiment_expand_includes_questions_without_instance_override(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    questions_instance_path = Path(payload["dataset"]) / "questions.instance.json"
    question_instances = json.loads(questions_instance_path.read_text(encoding="utf-8"))
    question_instances["instances"][0]["questions"] = [
        {
            "id": "q_summary",
            "parameters": {"researcher_name": "CV Demo"},
        }
    ]
    questions_instance_path.write_text(json.dumps(question_instances), encoding="utf-8")

    out_dir = tmp_path / "runspecs"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(out_dir)]) == 0

    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(out_dir.glob("rs_*.json"))]
    assert len(rows) == 2
    assert {row["questionId"] for row in rows} == {"q_year", "q_summary"}
    year = next(row for row in rows if row["questionId"] == "q_year")
    assert year["question"] == "In which year did the researcher obtain their PhD?"
    assert year["parameters"] == {}


def test_experiment_expand_warns_and_uses_empty_string_for_missing_template_parameter(tmp_path, capsys):
    dataset_root = tmp_path / "dataset"
    instance_dir = dataset_root / "context" / "cv_demo"
    instance_dir.mkdir(parents=True, exist_ok=True)
    (dataset_root / "questions.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "questions": [
                    {
                        "id": "q_missing",
                        "question": "Summarize the work of {researcher_name}.",
                        "tags": ["subjective"],
                        "validation": {"type": "judge"},
                        "contextBlock": ["summary"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (dataset_root / "questions.instance.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "instances": [
                    {
                        "instanceId": "cv_demo",
                        "contextBlocks": "context/cv_demo/blocks.json",
                        "questions": [{"id": "q_missing"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(json.dumps({"summary": {"text": "Research summary"}}), encoding="utf-8")
    (instance_dir / "raw.html").write_text("Research summary\n", encoding="utf-8")
    (instance_dir / "clean.html").write_text("Research summary\n", encoding="utf-8")
    (instance_dir / "blocks.json").write_text(json.dumps({"summary": "Research summary"}), encoding="utf-8")
    experiment_path = tmp_path / "experiment.json"
    experiment_path.write_text(
        json.dumps(
            {
                "id": "exp_missing_template",
                "output": "outputs",
                "dataset": str(dataset_root.resolve()),
                "scope": {"instances": ["cv_demo"], "questions": ["q_missing"]},
                "factors": {
                    "model": [{"provider": "mock", "name": "mock"}],
                    "strategy": ["inline"],
                    "format": ["json"],
                },
                "evaluation": {"enabled": False},
                "trace": {"enabled": False, "writeFiles": True},
                "artifacts": {
                    "writeJsonl": True,
                    "writeIndividualJson": True,
                },
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "runspecs"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(out_dir)]) == 0

    payload = json.loads(next(out_dir.glob("rs_*.json")).read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert "Missing question parameter" in captured.err
    assert payload["question"] == "Summarize the work of ."
    assert payload["parameters"] == {}


def test_experiment_expand_ignores_format_for_tool_based_strategies(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json")
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["factors"]["strategy"] = ["inline", "local_function", "local_mcp", "mcp"]
    payload["factors"]["format"] = ["json", "html"]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")

    out_dir = tmp_path / "runspecs"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(out_dir)]) == 0

    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(out_dir.glob("rs_*.json"))]
    assert len(rows) == 10

    inline_rows = [row for row in rows if row["strategy"] == "inline"]
    assert len(inline_rows) == 4
    assert {row["format"] for row in inline_rows} == {"json", "html"}

    for strategy_name in ("local_function", "local_mcp", "mcp"):
        strategy_rows = [row for row in rows if row["strategy"] == strategy_name]
        assert len(strategy_rows) == 2
        assert {row["format"] for row in strategy_rows} == {"json"}


def test_run_force_reexecutes_and_overwrites_results(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    runspec_dir = tmp_path / "runspecs"
    results_dir = tmp_path / "results"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(runspec_dir)]) == 0
    assert main(["run", str(runspec_dir), "--out", str(results_dir)]) == 0

    result_path = next(
        path
        for path in sorted(results_dir.glob("rr_*.json"))
        if json.loads(path.read_text(encoding="utf-8"))["questionId"] == "q_year"
    )
    first_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert first_payload["answer"] == "2018"

    parsed_path = tmp_path / "dataset" / "context" / "cv_demo" / "parsed.json"
    parsed_payload = json.loads(parsed_path.read_text(encoding="utf-8"))
    parsed_payload["answers"]["q_year"] = 2020
    parsed_path.write_text(json.dumps(parsed_payload), encoding="utf-8")

    assert main(["run", str(runspec_dir), "--out", str(results_dir), "--force"]) == 0
    second_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert second_payload["answer"] == "2020"


def test_run_from_runs_jsonl_writes_results_inside_expanded_root(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    expanded_root = tmp_path / "expanded"
    runspec_dir = expanded_root / "runs"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(
        [
            "experiment",
            "expand",
            str(experiment_path),
            "--out",
            str(runspec_dir),
            "--jsonl",
            str(runspec_jsonl),
        ]
    ) == 0

    assert main(["run", str(runspec_jsonl)]) == 0

    assert (expanded_root / "results").exists()
    assert (expanded_root / "results.jsonl").exists()
    assert list((expanded_root / "results").glob("rr_*.json"))
    assert list((expanded_root / "traces" / "runs").glob("*.json"))


def test_run_selector_filters_by_model_id(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl), "--model", "m1"]) == 0

    rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["modelId"] for row in rows} == {"m1"}
    assert {row["model"] for row in rows} == {"mock-a"}


def test_run_selector_filters_by_model_name(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl), "--model", "mock-b"]) == 0

    rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["modelId"] for row in rows} == {"m2"}
    assert {row["model"] for row in rows} == {"mock-b"}


def test_run_selector_excludes_instance_for_selected_model(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    dataset_root = Path(payload["dataset"])
    add_mock_instance(dataset_root, "cv_alt", researcher_name="CV Alt")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl), "--model", "m1", "--exclude-instance", "cv_demo"]) == 0

    rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["modelId"] for row in rows} == {"m1"}
    assert {row["instanceId"] for row in rows} == {"cv_alt"}
    assert {row["model"] for row in rows} == {"mock-a"}


def test_run_force_selector_reexecutes_only_selected_model(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    parsed_path = tmp_path / "dataset" / "context" / "cv_demo" / "parsed.json"
    parsed_payload = json.loads(parsed_path.read_text(encoding="utf-8"))
    parsed_payload["answers"]["q_year"] = 2020
    parsed_path.write_text(json.dumps(parsed_payload), encoding="utf-8")

    assert main(["run", str(runspec_jsonl), "--model", "m1", "--force"]) == 0
    rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    year_rows = [row for row in rows if row["questionId"] == "q_year"]
    assert next(row for row in year_rows if row["modelId"] == "m1")["answer"] == "2020"
    assert next(row for row in year_rows if row["modelId"] == "m2")["answer"] == "2018"


def test_run_resume_after_keyboard_interrupt_uses_checkpoint(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["scope"]["questions"] = ["q_year"]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    add_mock_instance(Path(payload["dataset"]), "cv_alt", researcher_name="CV Alt")

    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    rewrite_runspec_artifacts(runspec_jsonl, write_jsonl=False, write_individual_json=False)

    runspec_rows = [json.loads(line) for line in runspec_jsonl.read_text(encoding="utf-8").splitlines()]
    expected_run_ids = [row["runId"] for row in runspec_rows]

    from copa.commands import run as run_module

    original_execute_runspec = run_module.execute_runspec
    state = {"calls": 0}

    def interrupting_execute_runspec(*args, **kwargs):
        state["calls"] += 1
        if state["calls"] == 2:
            raise KeyboardInterrupt()
        return original_execute_runspec(*args, **kwargs)

    monkeypatch.setattr(run_module, "execute_runspec", interrupting_execute_runspec)

    assert main(["run", str(runspec_jsonl)]) == 130
    checkpoint_path = expanded_root / "runs.checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["kind"] == "runs"
    assert set(checkpoint["completedRunIds"]) == {expected_run_ids[0]}

    monkeypatch.setattr(run_module, "execute_runspec", original_execute_runspec)
    assert main(["run", str(runspec_jsonl)]) == 0
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert set(checkpoint["completedRunIds"]) == set(expected_run_ids)


def test_eval_selector_excludes_instance_for_selected_model(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    dataset_root = Path(payload["dataset"])
    add_mock_instance(dataset_root, "cv_alt", researcher_name="CV Alt")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl"), "--model", "m1", "--exclude-instance", "cv_demo"]) == 0
    rows = [json.loads(line) for line in (expanded_root / "evaluation.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["instanceId"] for row in rows} == {"cv_alt"}
    result_rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    expected_run_ids = {
        row["runId"]
        for row in result_rows
        if row["modelId"] == "m1" and row["instanceId"] == "cv_alt"
    }
    assert {row["runId"] for row in rows} == expected_run_ids


def test_eval_resume_after_keyboard_interrupt_uses_checkpoint(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["scope"]["instances"] = ["cv_demo", "cv_alt"]
    payload["scope"]["questions"] = ["q_year"]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    add_mock_instance(Path(payload["dataset"]), "cv_alt", researcher_name="CV Alt")

    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0
    rewrite_evaluation_manifest(expanded_root, write_jsonl=False, write_individual_json=False)

    result_rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    ordered_rows = sorted(
        result_rows,
        key=lambda row: (
            str(row["provider"]),
            str(row.get("model") or ""),
            str(row["instanceId"]),
            str(row["questionId"]),
            str(row["runId"]),
        ),
    )
    expected_run_ids = [row["runId"] for row in ordered_rows]

    from copa.benchmark import evaluation as evaluation_module

    state = {"calls": 0}

    def interrupting_judge_request(**kwargs):
        state["calls"] += 1
        if state["calls"] == 2:
            raise KeyboardInterrupt()
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", interrupting_judge_request)

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl")]) == 130
    checkpoint_path = expanded_root / "evaluation.checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint["kind"] == "evaluation"
    assert set(checkpoint["completedRunIds"]) == {expected_run_ids[0]}

    monkeypatch.setattr(evaluation_module, "_judge_request", lambda **kwargs: (
        {
            "correctness": {"rating": "meets", "justification": "ok"},
            "completeness": {"rating": "meets", "justification": "ok"},
        },
        evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
        evaluation_module.EvaluationTrace(),
    ))

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl")]) == 0
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert set(checkpoint["completedRunIds"]) == set(expected_run_ids)


def test_default_artifacts_use_jsonl_as_canonical_source(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload.pop("artifacts", None)
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_dir = expanded_root / "runs"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(
        [
            "experiment",
            "expand",
            str(experiment_path),
            "--out",
            str(runspec_dir),
            "--jsonl",
            str(runspec_jsonl),
        ]
    ) == 0
    assert not list(runspec_dir.glob("rs_*.json"))

    assert main(["run", str(runspec_jsonl)]) == 0
    results_jsonl = expanded_root / "results.jsonl"
    assert results_jsonl.exists()
    assert not list((expanded_root / "results").glob("rr_*.json"))
    assert list((expanded_root / "traces" / "runs").glob("*.json"))

    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(["eval", "--run-jsonl", str(results_jsonl)]) == 0
    evaluation_jsonl = expanded_root / "evaluation.jsonl"
    assert evaluation_jsonl.exists()
    assert not list((expanded_root / "evaluation").glob("re_*.json"))
    rows = [json.loads(line) for line in evaluation_jsonl.read_text(encoding="utf-8").splitlines()]
    assert rows
    assert rows[0]["outcome"] == "meets"
    assert rows[0]["correctness"] == "meets"
    assert rows[0]["completeness"] == "meets"
    assert rows[0]["judgeProvider"] == "mock"


def test_eval_writes_qualitative_outputs_and_csv(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    runspec_dir = tmp_path / "runspecs"
    results_dir = tmp_path / "results"
    eval_dir = tmp_path / "eval"
    eval_csv = tmp_path / "eval.csv"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(runspec_dir)]) == 0
    assert main(["run", str(runspec_dir), "--out", str(results_dir)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        config = kwargs["config"]
        return (
            {
                "correctness": {"rating": "meets", "justification": f"Consistent with research section according to {config.model}."},
                "completeness": {"rating": "partially meets", "justification": f"Covers the main areas but remains short according to {config.model}."},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider=config.provider, model=config.model),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(
        [
            "eval",
            "--run-dir",
            str(results_dir),
            "--output-dir",
            str(eval_dir),
            "--output-csv",
            str(eval_csv),
        ]
    ) == 0

    rows = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(eval_dir.glob("re_*.json"))
    ]
    assert len(rows) == 2
    year = next(row for row in rows if row["questionId"] == "q_year")
    judge = next(row for row in rows if row["questionId"] == "q_summary")
    assert year["details"]["correctness"]["rating"] == "meets"
    assert year["details"]["completeness"]["rating"] == "partially meets"
    assert judge["details"]["correctness"]["rating"] == "meets"
    assert judge["details"]["completeness"]["rating"] == "partially meets"
    assert len(judge["details"]["judges"]) == 1
    assert eval_csv.exists()
    summary = json.loads((eval_dir / "evaluation-summary.json").read_text(encoding="utf-8"))
    assert len(summary["questions"]) == 2
    judge_summary = next(item for item in summary["questions"] if item["questionId"] == "q_summary")
    assert judge_summary["aggregate"]["correctness"] == "meets"
    assert judge_summary["aggregate"]["completeness"] == "partially meets"
    assert len(judge_summary["judgeRatings"]) == 1


def test_eval_selector_filters_by_model_id(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["artifacts"]["writeIndividualJson"] = False
    payload["factors"]["model"] = [
        {"id": "m1", "provider": "mock", "name": "mock-a"},
        {"id": "m2", "provider": "mock", "name": "mock-b"},
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl"), "--model", "m1"]) == 0
    rows = [json.loads(line) for line in (expanded_root / "evaluation.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    result_rows = [json.loads(line) for line in (expanded_root / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    selected_run_ids = {row["runId"] for row in result_rows if row["modelId"] == "m1"}
    assert {row["runId"] for row in rows} == selected_run_ids


def test_eval_selector_filters_by_judge_id(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "mock",
            "model": "judge-a",
            "temperature": 0,
            "params": {"id": "juiz-gpt"},
        },
        {
            "provider": "mock",
            "model": "judge-b",
            "temperature": 0,
            "params": {"id": "juiz-claude"},
        },
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    seen: list[tuple[str, str, dict[str, object]]] = []

    def fake_judge_request(**kwargs):
        config = kwargs["config"]
        seen.append((config.provider, config.model, dict(config.params)))
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider=config.provider, model=config.model),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl"), "--judge", "juiz-claude"]) == 0
    rows = [json.loads(line) for line in (expanded_root / "evaluation.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert seen == [("mock", "judge-b", {"id": "juiz-claude"})] * 2
    assert {row["judgeModel"] for row in rows} == {"judge-b"}
    assert all(len(row["details"]["judges"]) == 1 for row in rows)


def test_eval_wait_requires_batch(tmp_path, capsys):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl"), "--wait"]) == 1
    assert "--wait can only be used with --batch" in capsys.readouterr().err


def test_eval_batch_custom_id_matches_anthropic_constraints(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "temperature": 0,
            "params": {"id": "juiz:claude/test"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.commands import eval as eval_module

    custom_ids: list[str] = []

    def fake_submit_evaluation_batch(**kwargs):
        custom_ids.extend(job.custom_id for job in kwargs["jobs"])
        return {
            "kind": "evaluation_batch",
            "batchId": "msgbatch_test",
            "processingStatus": "in_progress",
            "requestCount": len(kwargs["jobs"]),
        }

    monkeypatch.setattr(eval_module, "submit_evaluation_batch", fake_submit_evaluation_batch)

    assert main(["eval", "--run-jsonl", str(expanded_root / "results.jsonl"), "--judge", "juiz:claude/test", "--batch"]) == 0
    assert custom_ids
    assert all(len(value) <= 64 for value in custom_ids)
    assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", value) for value in custom_ids)


def test_eval_batch_wait_persists_results(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "anthropic",
            "model": "claude-sonnet-4-6",
            "temperature": 0,
            "params": {"id": "juiz-claude"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark.evaluation import evaluation_from_judge_payload
    from copa.benchmark.models import EvaluationJudgeInfo, EvaluationTrace
    from copa.commands import eval as eval_module

    def fake_submit_evaluation_batch(**kwargs):
        return {
            "kind": "evaluation_batch",
            "batchId": "msgbatch_test",
            "processingStatus": "in_progress",
            "requestCount": len(kwargs["jobs"]),
        }

    def fake_retrieve_evaluation_batch(**kwargs):
        evaluations = [
            evaluation_from_judge_payload(
                job,
                payload={
                    "correctness": {"rating": "meets", "justification": "ok"},
                    "completeness": {"rating": "meets", "justification": "ok"},
                },
                judge_info=EvaluationJudgeInfo(
                    used=True,
                    role="judge",
                    provider=job.judge.provider,
                    model=job.judge.model,
                    inputTokens=10,
                    outputTokens=2,
                ),
                trace=EvaluationTrace(aiTrace={"batch": {"customId": job.custom_id}}),
            )
            for job in kwargs["jobs"]
        ]
        return {
            "kind": "evaluation_batch",
            "batchId": kwargs["batch_id"],
            "processingStatus": "ended",
        }, evaluations

    monkeypatch.setattr(eval_module, "submit_evaluation_batch", fake_submit_evaluation_batch)
    monkeypatch.setattr(eval_module, "retrieve_evaluation_batch", fake_retrieve_evaluation_batch)

    assert main(
        [
            "eval",
            "--run-jsonl",
            str(expanded_root / "results.jsonl"),
            "--judge",
            "juiz-claude",
            "--batch",
            "--wait",
        ]
    ) == 0
    rows = [json.loads(line) for line in (expanded_root / "evaluation.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert {row["judgeModel"] for row in rows} == {"claude-sonnet-4-6"}
    assert {row["outcome"] for row in rows} == {"meets"}


def test_eval_batch_retrieves_openai_results(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "openai",
            "model": "gpt-5.5",
            "temperature": 0,
            "params": {"id": "juiz-gpt"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark.evaluation import build_evaluation_jobs
    from copa.benchmark.evaluation_batch import retrieve_evaluation_batch
    from copa.commands.eval import _load_judges_from_manifest, load_results_from_input

    jobs = build_evaluation_jobs(
        load_results_from_input(run_dir=None, run_jsonl=str(expanded_root / "results.jsonl")),
        judges=_load_judges_from_manifest(expanded_root),
    )

    class FakeOpenAIClient:
        def retrieve(self, batch_id):
            return {"id": batch_id, "status": "completed", "output_file_id": "file_test"}

        def results(self, batch_id, batch=None):
            return [
                {
                    "custom_id": job.custom_id,
                    "response": {
                        "status_code": 200,
                        "body": {
                            "output": [
                                {
                                    "content": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "correctness": {"rating": "meets", "justification": "ok"},
                                                    "completeness": {"rating": "meets", "justification": "ok"},
                                                }
                                            )
                                        }
                                    ]
                                }
                            ],
                            "usage": {"input_tokens": 11, "output_tokens": 3},
                        },
                    },
                    "error": None,
                }
                for job in jobs
            ]

    manifest, evaluations = retrieve_evaluation_batch(
        batch_id="batch_test",
        jobs=jobs,
        source_root=expanded_root,
        client=FakeOpenAIClient(),
    )

    assert manifest["status"] == "completed"
    assert len(evaluations) == 2
    assert {item.items[0].evaluationJudgeProvider for item in evaluations} == {"openai"}
    assert {item.items[0].details["outcome"] for item in evaluations} == {"meets"}
    assert {item.items[0].evaluationInputTokens for item in evaluations} == {11}


def test_eval_batch_retrieves_openai_error_results(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "openai",
            "model": "gpt-5.5",
            "temperature": 0,
            "params": {"id": "juiz-gpt"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark.evaluation import build_evaluation_jobs
    from copa.benchmark.evaluation_batch import retrieve_evaluation_batch
    from copa.commands.eval import _load_judges_from_manifest, load_results_from_input

    jobs = build_evaluation_jobs(
        load_results_from_input(run_dir=None, run_jsonl=str(expanded_root / "results.jsonl")),
        judges=_load_judges_from_manifest(expanded_root),
    )

    class FakeOpenAIClient:
        def retrieve(self, batch_id):
            return {
                "id": batch_id,
                "status": "completed",
                "output_file_id": None,
                "error_file_id": "file_errors",
            }

        def results(self, batch_id, batch=None):
            return [
                {
                    "custom_id": job.custom_id,
                    "response": None,
                    "error": {
                        "code": "invalid_request_error",
                        "message": "The request body was invalid.",
                    },
                }
                for job in jobs
            ]

    manifest, evaluations = retrieve_evaluation_batch(
        batch_id="batch_test",
        jobs=jobs,
        source_root=expanded_root,
        client=FakeOpenAIClient(),
    )

    assert manifest["status"] == "completed"
    assert manifest["errorFileId"] == "file_errors"
    assert len(evaluations) == 2
    assert {item.items[0].evaluationJudgeProvider for item in evaluations} == {"openai"}
    assert {item.items[0].details["error"] for item in evaluations} == {"Judge did not return valid JSON."}
    assert {item.items[0].evaluationTrace.error for item in evaluations} == {"Batch request errored."}


def test_eval_batch_openai_submit_uploads_pathlike_jsonl(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "openai",
            "model": "gpt-5.5",
            "temperature": 0,
            "params": {"id": "juiz-gpt"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark.evaluation import build_evaluation_jobs
    from copa.benchmark.evaluation_batch import OpenAIEvaluationBatchClient
    from copa.commands.eval import _load_judges_from_manifest, load_results_from_input

    jobs = build_evaluation_jobs(
        load_results_from_input(run_dir=None, run_jsonl=str(expanded_root / "results.jsonl")),
        judges=_load_judges_from_manifest(expanded_root),
    )

    class FakeFiles:
        uploaded_payloads: list[dict[str, object]] = []

        def create(self, *, file, purpose):
            assert isinstance(file, Path)
            assert purpose == "batch"
            rows = [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines()]
            assert rows
            assert {row["url"] for row in rows} == {"/v1/responses"}
            assert {row["method"] for row in rows} == {"POST"}
            self.uploaded_payloads = rows
            return type("Uploaded", (), {"id": "file_test"})()

    class FakeBatches:
        def create(self, **kwargs):
            assert kwargs["input_file_id"] == "file_test"
            assert kwargs["endpoint"] == "/v1/responses"
            assert "temperature" not in kwargs
            return {"id": "batch_test", "status": "validating"}

    client = OpenAIEvaluationBatchClient.__new__(OpenAIEvaluationBatchClient)
    client._client = type("FakeOpenAI", (), {"files": FakeFiles(), "batches": FakeBatches()})()

    batch = client.submit(jobs)

    assert batch["id"] == "batch_test"


def test_eval_batch_retrieves_gemini_results(tmp_path):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=True)
    payload = json.loads(experiment_path.read_text(encoding="utf-8"))
    payload["evaluation"]["judges"] = [
        {
            "provider": "google",
            "model": "gemini-3.1-flash-lite-preview",
            "temperature": 0,
            "params": {"id": "juiz-gemini"},
        }
    ]
    experiment_path.write_text(json.dumps(payload), encoding="utf-8")
    expanded_root = tmp_path / "expanded"
    runspec_jsonl = expanded_root / "runs.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(expanded_root / "runs"), "--jsonl", str(runspec_jsonl)]) == 0
    assert main(["run", str(runspec_jsonl)]) == 0

    from copa.benchmark.evaluation import build_evaluation_jobs
    from copa.benchmark.evaluation_batch import retrieve_evaluation_batch
    from copa.commands.eval import _load_judges_from_manifest, load_results_from_input

    jobs = build_evaluation_jobs(
        load_results_from_input(run_dir=None, run_jsonl=str(expanded_root / "results.jsonl")),
        judges=_load_judges_from_manifest(expanded_root),
    )

    class FakeGeminiClient:
        def retrieve(self, batch_id):
            return {"name": batch_id, "state": "JOB_STATE_SUCCEEDED"}

        def results(self, batch_id, batch=None):
            return [
                {
                    "metadata": {"custom_id": job.custom_id},
                    "response": {
                        "candidates": [
                            {
                                "content": {
                                    "parts": [
                                        {
                                            "text": json.dumps(
                                                {
                                                    "correctness": {"rating": "partially meets", "justification": "ok"},
                                                    "completeness": {"rating": "meets", "justification": "ok"},
                                                }
                                            )
                                        }
                                    ]
                                }
                            }
                        ],
                        "usageMetadata": {"promptTokenCount": 13, "candidatesTokenCount": 5},
                    },
                }
                for job in jobs
            ]

    manifest, evaluations = retrieve_evaluation_batch(
        batch_id="batches/test",
        jobs=jobs,
        source_root=expanded_root,
        client=FakeGeminiClient(),
    )

    assert manifest["status"] == "completed"
    assert len(evaluations) == 2
    assert {item.items[0].evaluationJudgeProvider for item in evaluations} == {"google"}
    assert {item.items[0].details["outcome"] for item in evaluations} == {"partially_meets"}
    assert {item.items[0].evaluationInputTokens for item in evaluations} == {13}


def test_eval_allows_questions_without_instance_override(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    dataset_root = Path(json.loads(experiment_path.read_text(encoding="utf-8"))["dataset"])
    questions_instance_path = dataset_root / "questions.instance.json"
    payload = json.loads(questions_instance_path.read_text(encoding="utf-8"))
    payload["instances"][0]["questions"] = [
        {"id": "q_summary", "parameters": {"researcher_name": "CV Demo"}}
    ]
    questions_instance_path.write_text(json.dumps(payload), encoding="utf-8")

    runspec_dir = tmp_path / "runspecs"
    results_dir = tmp_path / "results"
    eval_dir = tmp_path / "eval"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(runspec_dir)]) == 0
    assert main(["run", str(runspec_dir), "--out", str(results_dir)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        return (
            {
                "correctness": {"rating": "meets", "justification": "ok"},
                "completeness": {"rating": "meets", "justification": "ok"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(
        [
            "eval",
            "--run-dir",
            str(results_dir),
            "--output-dir",
            str(eval_dir),
        ]
    ) == 0

    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(eval_dir.glob("re_*.json"))]
    assert len(rows) == 2


def test_eval_force_rewrites_existing_evaluation(tmp_path, monkeypatch):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    runspec_dir = tmp_path / "runspecs"
    results_dir = tmp_path / "results"
    eval_dir = tmp_path / "eval"
    eval_jsonl = tmp_path / "eval.jsonl"

    assert main(["experiment", "expand", str(experiment_path), "--out", str(runspec_dir)]) == 0
    assert main(["run", str(runspec_dir), "--out", str(results_dir)]) == 0

    from copa.benchmark import evaluation as evaluation_module

    state = {"version": 0}

    def fake_judge_request(**kwargs):
        state["version"] += 1
        return (
            {
                "correctness": {"rating": "meets", "justification": f"judge-v{state['version']}"},
                "completeness": {"rating": "meets", "justification": f"judge-v{state['version']}"},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(
        [
            "eval",
            "--run-dir",
            str(results_dir),
            "--output-dir",
            str(eval_dir),
            "--output-jsonl",
            str(eval_jsonl),
        ]
    ) == 0

    judge_path = next(path for path in sorted(eval_dir.glob("re_*.json")) if json.loads(path.read_text(encoding="utf-8"))["questionId"] == "q_summary")
    first_payload = json.loads(judge_path.read_text(encoding="utf-8"))
    assert first_payload["details"]["judges"][0]["correctness"]["justification"] == "judge-v1"

    state["version"] = 9
    assert main(
        [
            "eval",
            "--run-dir",
            str(results_dir),
            "--output-dir",
            str(eval_dir),
            "--output-jsonl",
            str(eval_jsonl),
            "--force",
        ]
    ) == 0

    second_payload = json.loads(judge_path.read_text(encoding="utf-8"))
    assert second_payload["details"]["judges"][0]["correctness"]["justification"] == "judge-v10"
    rows = [json.loads(line) for line in eval_jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2


def test_eval_rejects_runs_jsonl_with_clear_error(tmp_path, capsys):
    experiment_path = write_mock_experiment(tmp_path / "experiment.json", evaluation_enabled=False)
    runspec_dir = tmp_path / "runspecs"
    runspec_jsonl = tmp_path / "runspecs.jsonl"

    assert main(
        [
            "experiment",
            "expand",
            str(experiment_path),
            "--out",
            str(runspec_dir),
            "--jsonl",
            str(runspec_jsonl),
        ]
    ) == 0

    exit_code = main(["eval", "--run-jsonl", str(runspec_jsonl)])
    err = capsys.readouterr().err

    assert exit_code == 1
    assert "run specifications, not run results" in err
    assert "results.jsonl" in err
