import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.benchmark.models import ExperimentDataset
from copa.cli import main


def write_mock_experiment(path: Path) -> Path:
    dataset_root = path.parent / "datasets"
    contexts_dir = dataset_root / "contexts"
    contexts_dir.mkdir(parents=True, exist_ok=True)

    questions_path = dataset_root / "questions.json"
    question_instances_path = dataset_root / "questions.instance.json"
    context_json_path = contexts_dir / "cv_demo.json"
    context_text_path = contexts_dir / "cv_demo.txt"

    questions_path.write_text(
        json.dumps(
            {
                "datasetId": "mock-questions-v2",
                "domain": "demo",
                "language": "en",
                "questions": [
                    {
                        "id": "q_exact_001",
                        "question": "In which year did the researcher obtain their Ph.D.?",
                        "evaluation": {
                            "mode": "exact",
                            "answerType": "year",
                        },
                    },
                    {
                        "id": "q_analytical_001",
                        "question": "What skills can be inferred from the researcher profile?",
                        "evaluation": {
                            "mode": "analytical",
                            "rubric": [
                                {
                                    "id": "teaching",
                                    "description": "Mentions teaching expertise",
                                    "keywords": ["teaching"],
                                    "weight": 1,
                                },
                                {
                                    "id": "research",
                                    "description": "Mentions research expertise",
                                    "keywords": ["research"],
                                    "weight": 1,
                                },
                                {
                                    "id": "synthesis",
                                    "description": "Provides synthesized interpretation",
                                    "keywords": ["synthesizes", "combines"],
                                    "weight": 1,
                                },
                            ],
                        },
                    },
                    {
                        "id": "q_oos_001",
                        "question": "How many children does the researcher have?",
                        "evaluation": {
                            "mode": "unanswerable",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    question_instances_path.write_text(
        json.dumps(
            {
                "datasetId": "mock-question-instances-v2",
                "instances": [
                    {
                        "questionId": "q_exact_001",
                        "cvId": "cv_demo",
                        "goldAnswer": 2018,
                    },
                    {
                        "questionId": "q_analytical_001",
                        "cvId": "cv_demo",
                        "goldAnswer": "Mentions teaching and research and synthesizes them.",
                    },
                    {
                        "questionId": "q_oos_001",
                        "cvId": "cv_demo",
                        "goldAnswer": "Not enough information.",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    context_json_path.write_text(
        json.dumps(
            {
                "answers": {
                    "q_exact_001": "2018",
                    "q_analytical_001": "The profile combines teaching and research experience and synthesizes both into software engineering expertise.",
                    "q_oos_001": "Not enough information.",
                }
            }
        ),
        encoding="utf-8",
    )
    context_text_path.write_text(
        "\n".join(
            [
                "ANSWER[q_exact_001]: 2018",
                "ANSWER[q_analytical_001]: The profile combines teaching and research experience and synthesizes both into software engineering expertise.",
                "ANSWER[q_oos_001]: Not enough information.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    path.write_text(
        json.dumps(
            {
                "id": "exp_test_mock_001",
                "dataset": {
                    "questions": str(questions_path.resolve()),
                    "contexts": str(contexts_dir.resolve()),
                    "question_instances": str(question_instances_path.resolve()),
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
                    "output": "outputs/eval",
                    "jsonl": "outputs/eval/evaluation-results.jsonl",
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
    files = sorted(out_dir.glob("*.json"))
    assert len(files) == 6
    assert all(path.name.startswith("rs_exp_test_mock_001_") for path in files)
    first = json.loads(files[0].read_text(encoding="utf-8"))
    assert first["provider"] == "mock"
    assert first["params"]["model_name"] == "mock"
    assert first["strategy"] == "inline"
    assert first["format"] in {"json", "text"}
    assert "temperature" in first["params"]
    assert "|" in first["id"]
    assert first["experimentPath"] == str(experiment_path.resolve())
    assert jsonl_path.exists()
    assert len(jsonl_path.read_text(encoding="utf-8").splitlines()) == 6


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
    eval_dir = tmp_path / "manual-eval"
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
    assert len(result_files) == 6
    assert all(path.name.startswith("rr_exp_test_mock_001_") for path in result_files)
    result = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert result["evaluation"]["status"] == "not_evaluated"
    assert result["trace"]["aiTrace"]["metrics"]["model_calls"] == 1
    assert result["trace"]["aiTrace"]["events"][-1]["name"] == "engine.execute"
    assert "|" in result["runId"]
    assert results_jsonl.exists()

    auto_eval_dir = experiment_path.parent / "outputs" / "eval"
    auto_eval_files = sorted(path for path in auto_eval_dir.glob("re_*.json"))
    assert len(auto_eval_files) == 6
    assert (auto_eval_dir / "evaluation-summary.json").exists()
    assert (auto_eval_dir / "evaluation-results.jsonl").exists()

    assert (
        main(
            [
                "eval",
                "--run-results-json",
                str(results_jsonl),
                "--experiment",
                str(experiment_path),
                "--output-dir",
                str(eval_dir),
                "--output-jsonl",
                str(eval_jsonl),
            ]
        )
        == 0
    )

    evaluated_files = sorted(eval_dir.glob("*.json"))
    assert len(evaluated_files) == 7
    assert any(path.name.startswith("re_exp_test_mock_001_") for path in evaluated_files)
    exact_eval = next(
        json.loads(path.read_text(encoding="utf-8"))
        for path in evaluated_files
        if path.name.startswith("re_")
        and json.loads(path.read_text(encoding="utf-8"))["questionId"] == "q_exact_001"
    )
    assert exact_eval["items"][0]["evaluationMode"] == "exact"
    assert exact_eval["items"][0]["score"] == 1.0
    assert exact_eval["items"][0]["label"] == "correct"
    assert exact_eval["items"][0]["details"]["extractedAnswer"] == 2018
    assert eval_jsonl.exists()
    rows = [json.loads(line) for line in eval_jsonl.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6
    assert {"exact", "analytical", "unanswerable"} <= {row["evaluationMode"] for row in rows}


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
    assert "[EVALUATE]" in stderr
    assert "[DONE]" in stderr
    assert "Processing runs:" in stderr
