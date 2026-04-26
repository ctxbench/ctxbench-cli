import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.cli import main


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
                        "validation": {"type": "heuristic", "schema": {"type": "number"}},
                    },
                    {
                        "id": "q_summary",
                        "question": "Summarize the main research areas for {researcher_name}.",
                        "tags": ["subjective", "simple"],
                        "validation": {"type": "judge"},
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
                            {"id": "q_year", "acceptedAnswers": [2018]},
                            {
                                "id": "q_summary",
                                "template_parameters": {"researcher_name": "CV Demo"},
                                "contextRefs": ["summary", "research"],
                                "themes": ["software engineering", "distributed systems"],
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
    (instance_dir / "cleaned.html").write_text("ANSWER[q_year]: 2018\n", encoding="utf-8")
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
                    "judge": {"provider": "mock", "model": "mock", "temperature": 0},
                },
                "trace": {
                    "enabled": True,
                    "save_raw_response": True,
                    "save_tool_calls": True,
                    "save_usage": True,
                    "save_errors": True,
                },
                "execution": {"repeats": 1},
            }
        ),
        encoding="utf-8",
    )
    return path


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
    assert first["validationType"] in {"heuristic", "judge"}
    summary = next(row for row in rows if row["questionId"] == "q_summary")
    assert summary["question"] == "Summarize the main research areas for CV Demo."
    assert summary["templateParameters"] == {"researcher_name": "CV Demo"}
    assert (out_dir / "runs.manifest.json").exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 2


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
                        "questions": [{"id": "q_missing", "contextRefs": ["summary"], "themes": ["summary"]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(json.dumps({"summary": {"text": "Research summary"}}), encoding="utf-8")
    (instance_dir / "raw.html").write_text("Research summary\n", encoding="utf-8")
    (instance_dir / "cleaned.html").write_text("Research summary\n", encoding="utf-8")
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
            }
        ),
        encoding="utf-8",
    )

    out_dir = tmp_path / "runspecs"
    assert main(["experiment", "expand", str(experiment_path), "--out", str(out_dir)]) == 0

    payload = json.loads(next(out_dir.glob("rs_*.json")).read_text(encoding="utf-8"))
    captured = capsys.readouterr()
    assert "Missing template parameter" in captured.err
    assert payload["question"] == "Summarize the work of ."
    assert payload["templateParameters"] == {}


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
        del kwargs
        return (
            {
                "groundedness": {"rating": "meets", "justification": "Supported by summary."},
                "correctness": {"rating": "meets", "justification": "Consistent with research section."},
                "completeness": {"rating": "partially meets", "justification": "Covers the main areas but remains short."},
            },
            evaluation_module.EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            evaluation_module.EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    assert main(
        [
            "eval",
            "--run-results-dir",
            str(results_dir),
            "--experiment",
            str(experiment_path),
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
    heuristic = next(row for row in rows if row["questionId"] == "q_year")
    judge = next(row for row in rows if row["questionId"] == "q_summary")
    assert heuristic["details"]["outcome"] == "accepted"
    assert judge["details"]["groundedness"]["justification"] == "Supported by summary."
    assert "score" not in heuristic
    assert eval_csv.exists()
