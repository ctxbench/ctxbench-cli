from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall, ToolResult, ToolSpec
from copa.ai.trace import TraceCollector
from copa.benchmark.evaluation import _evaluate_judge, _heuristic_compare
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import (
    EvaluationJudgeInfo,
    EvaluationTrace,
    Experiment,
    ExperimentDataset,
    RunMetadata,
    RunSpec,
)
from copa.dataset.provider import DatasetProvider
import json


def make_request(**overrides: object) -> AIRequest:
    payload = {
        "question": "How many publications are listed?",
        "context": '{"answers": {"q1": "3"}}',
        "provider_name": "mock",
        "model_name": "mock",
        "strategy_name": "inline",
        "context_format": "json",
        "params": {},
        "metadata": {"question_id": "q1", "lattes_id": "cv-demo", "instance_id": "cv-demo"},
    }
    payload.update(overrides)
    return AIRequest(**payload)


def make_experiment() -> Experiment:
    return Experiment.model_validate(
        {
            "id": "exp-test",
            "output": "outputs",
            "dataset": str((Path.cwd() / "examples" / "datasets" / "lattes").resolve()),
            "scope": {"instances": [], "questions": []},
            "factors": {
                "model": [{"provider": "mock", "name": "mock"}],
                "strategy": ["inline"],
                "format": ["json"],
            },
            "evaluation": {
                "enabled": True,
                "judges": [{"provider": "mock", "model": "mock", "temperature": 0}],
            },
        }
    )


def write_mock_dataset(root: Path) -> ExperimentDataset:
    instance_dir = root / "context" / "cv-demo"
    instance_dir.mkdir(parents=True, exist_ok=True)
    (root / "questions.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "questions": [
                    {
                        "id": "q_year",
                        "question": "In which year did the researcher obtain their PhD?",
                        "tags": ["objective", "simple"],
                        "validation": {"type": "heuristic", "schema": {"type": "number"}},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "questions.instance.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "instances": [
                    {
                        "instanceId": "cv-demo",
                        "contextBlocks": "context/cv-demo/blocks.json",
                        "questions": [{"id": "q_year", "acceptedAnswers": [2020]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(json.dumps({"answers": {"q_year": 2020}}), encoding="utf-8")
    (instance_dir / "raw.html").write_text("ANSWER[q_year]: 2020\n", encoding="utf-8")
    (instance_dir / "clean.html").write_text("ANSWER[q_year]: 2020\n", encoding="utf-8")
    (instance_dir / "blocks.json").write_text(json.dumps({"summary": "PhD in 2020"}), encoding="utf-8")
    return ExperimentDataset(root=str(root.resolve()))


def test_dataset_provider_context_blocks_falls_back_to_instance_blocks_file(tmp_path):
    dataset = write_mock_dataset(tmp_path / "dataset")
    payload = json.loads((Path(dataset.root) / "questions.instance.json").read_text(encoding="utf-8"))
    payload["instances"][0].pop("contextBlocks", None)
    (Path(dataset.root) / "questions.instance.json").write_text(json.dumps(payload), encoding="utf-8")

    provider = DatasetProvider.from_dataset(dataset)

    assert provider.get_context_blocks("cv-demo") == {"summary": "PhD in 2020"}


class RecordingModel(ModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.last_input: ModelInput | None = None
        self.last_request: AIRequest | None = None

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.last_input = model_input
        self.last_request = request
        return ModelResponse(
            text="3",
            raw_response={"provider": "recording"},
            input_tokens=11,
            output_tokens=1,
            total_tokens=12,
            duration_ms=7,
            metadata={"provider": "recording"},
        )


class RecordingJudgeModel(ModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.last_input: ModelInput | None = None
        self.last_request: AIRequest | None = None

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.last_input = model_input
        self.last_request = request
        return ModelResponse(
            text='{"correctness":{"rating":"meets","justification":"ok"},"completeness":{"rating":"meets","justification":"ok"}}',
            raw_response={"provider": "recording-judge"},
            input_tokens=10,
            output_tokens=10,
            total_tokens=20,
            duration_ms=5,
            metadata={"provider": "recording-judge"},
        )


class ScriptedToolModel(ModelAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.inputs: list[ModelInput] = []

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.inputs.append(model_input)
        return self.responses.pop(0)


class FakeLattesRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name="get_profile", input_schema={"type": "object"}),
            ToolSpec(name="get_publications", input_schema={"type": "object"}),
        ]

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        self.calls.append((name, arguments))
        if name == "get_profile":
            return ToolResult(name=name, content={"name": "Ada Lovelace"})
        return ToolResult(name=name, content={"items": [{"year": 2024, "title": "Software Engineering Paper"}]})

    def close(self) -> None:
        return None


def test_engine_inline_execution_records_prompt_trace_and_usage():
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model

    result = engine.execute(make_request(provider_name="recording"))

    assert result.answer == "3"
    assert result.usage == {"inputTokens": 11, "outputTokens": 1, "totalTokens": 12}
    assert model.last_input is not None
    assert "# Question:" in model.last_input.prompt
    assert "# Context:" in model.last_input.prompt
    metrics = result.trace["metrics"]
    assert metrics["question_tokens"] == len("How many publications are listed?".split())
    assert metrics["llm_call_count"] == 1
    assert metrics["total_llm_tokens"] == 12


def test_engine_local_function_uses_resource_tools_and_records_calls():
    runtime = FakeLattesRuntime()
    engine = Engine(tool_runtime_factories={"local_function": lambda: runtime})
    model = ScriptedToolModel(
        [
            ModelResponse(
                requested_tool_calls=[ToolCall(name="get_publications", arguments={"lattes_id": "cv-demo", "start_year": 2020})],
                duration_ms=5,
                input_tokens=10,
                output_tokens=0,
                total_tokens=10,
            ),
            ModelResponse(
                text="Software engineering",
                duration_ms=6,
                input_tokens=4,
                output_tokens=2,
                total_tokens=6,
            ),
        ]
    )
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_function"))

    assert result.answer == "Software engineering"
    assert runtime.calls == [("get_publications", {"lattes_id": "cv-demo", "start_year": 2020})]
    assert "Researcher Lattes ID:" in model.inputs[0].prompt
    assert result.trace["metrics"]["tool_call_count_semantic"] == 1


def test_heuristic_compare_supports_structured_answers():
    details = _heuristic_compare(
        '{"where": "UIUC", "yearsAgo": 26}',
        [{"where": "UIUC", "yearsAgo": 26}],
        {"type": "object"},
    )

    assert details["matched"] is True
    assert details["outcome"] == "accepted"


def test_heuristic_compare_supports_aliases_and_text_normalization():
    details = _heuristic_compare(
        '{"where": "PUC Rio", "yearsAgo": 26}',
        [
            {
                "where": {
                    "aliases": [
                        "PUC-Rio",
                        "Pontifícia Universidade Católica do Rio de Janeiro",
                        "Pontifical Catholic University of Rio de Janeiro",
                    ]
                },
                "yearsAgo": 26,
            }
        ],
        {"type": "object"},
    )

    assert details["matched"] is True
    assert details["outcome"] == "accepted"


def test_evaluate_judge_persists_rating_and_justification(monkeypatch):
    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        config = kwargs["config"]
        return (
            {
                "correctness": {"rating": "meets", "justification": f"Consistent according to {config.model}."},
                "completeness": {"rating": "partially meets", "justification": f"Partial according to {config.model}."},
            },
            EvaluationJudgeInfo(used=True, role="judge", provider=config.provider, model=config.model),
            EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    details, judge_info, _ = _evaluate_judge(
        result=type("R", (), {"answer": "Answer", "runId": "run-1", "experimentId": "exp-1"})(),
        question_text="Question?",
        ground_truth="Ground truth answer.",
        experiment=make_experiment(),
        engine=Engine(),
    )

    assert details["correctness"]["rating"] == "meets"
    assert details["completeness"]["rating"] == "partially meets"
    assert len(details["judges"]) == 1
    assert details["outcome"] == "partially_meets"
    assert judge_info.used is True


def test_evaluate_judge_aggregates_multiple_judges(monkeypatch):
    from copa.benchmark import evaluation as evaluation_module

    experiment = Experiment.model_validate(
        {
            "id": "exp-test",
            "output": "outputs",
            "dataset": str((Path.cwd() / "datasets" / "lattes").resolve()),
            "scope": {"instances": [], "questions": []},
            "factors": {
                "model": [{"provider": "mock", "name": "mock"}],
                "strategy": ["inline"],
                "format": ["json"],
            },
            "evaluation": {
                "enabled": True,
                "judges": [
                    {"provider": "mock", "model": "judge-a", "temperature": 0},
                    {"provider": "mock", "model": "judge-b", "temperature": 0},
                ],
            },
        }
    )

    def fake_judge_request(**kwargs):
        config = kwargs["config"]
        if config.model == "judge-a":
            return (
                {
                    "correctness": {"rating": "meets", "justification": "A says correct."},
                    "completeness": {"rating": "partially meets", "justification": "A says partial."},
                },
                EvaluationJudgeInfo(used=True, role="judge", provider=config.provider, model=config.model),
                EvaluationTrace(),
            )
        return (
            {
                "correctness": {"rating": "does not meet", "justification": "B says incorrect."},
                "completeness": {"rating": "partially meets", "justification": "B says partial."},
            },
            EvaluationJudgeInfo(used=True, role="judge", provider=config.provider, model=config.model),
            EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    details, judge_info, _ = _evaluate_judge(
        result=type("R", (), {"answer": "Answer", "runId": "run-1", "experimentId": "exp-1"})(),
        question_text="Question?",
        ground_truth="Ground truth answer.",
        experiment=experiment,
        engine=Engine(),
    )

    assert details["correctness"]["rating"] == "does not meet"
    assert details["correctness"]["votes"] == {"meets": 1, "partially meets": 0, "does not meet": 1}
    assert details["completeness"]["rating"] == "partially meets"
    assert len(details["judges"]) == 2
    assert details["outcome"] == "does_not_meet"
    assert judge_info.used is True


def test_judge_request_injects_structured_output_schema():
    from copa.benchmark.evaluation import _judge_request

    engine = Engine()
    model = RecordingJudgeModel()
    engine._models["recording_judge"] = model

    payload, judge_info, _ = _judge_request(
        config=type(
            "Cfg",
            (),
            {
                "provider": "recording_judge",
                "model": "recording_judge",
                "temperature": 0,
                "params": {},
            },
        )(),
        prompt="Judge this answer.",
        run_id="run-1",
        exp_id="exp-1",
        engine=engine,
    )

    assert payload is not None
    assert judge_info.used is True
    assert model.last_request is not None
    assert model.last_request.params["structured_output"]["schema"]["type"] == "object"
    assert model.last_request.params["structured_output"]["schema"]["required"] == ["correctness", "completeness"]


def test_execute_runspec_persists_metrics_summary_with_nulls_for_remote_mcp(tmp_path):
    dataset = write_mock_dataset(tmp_path / "dataset")
    runspec = RunSpec(
        id="run-1",
        runId="run-1",
        experimentId="exp-1",
        dataset=dataset,
        questionId="q_year",
        instanceId="cv-demo",
        provider="mock",
        modelName="mock",
        strategy="mcp",
        format="json",
        repeatIndex=1,
        params={"mcp_server": {"server_url": "https://example.test/mcp"}},
        metadata=RunMetadata(
            canonicalId="exp-1|q_year|cv-demo|mock|mock|mcp|json|1",
            questionId="q_year",
            instanceId="cv-demo",
            provider="mock",
            modelName="mock",
            strategy="mcp",
            format="json",
            repeatIndex=1,
        ),
    )

    result = execute_runspec(runspec, Engine())

    assert isinstance(result.answer, str)
    assert result.metricsSummary["tool_call_count"] is None
    assert result.metricsSummary["function_call_count"] is None
    assert result.metricsSummary["prompt_tokens"] is None


def test_execute_runspec_injects_structured_output_for_heuristic_questions(tmp_path):
    dataset = write_mock_dataset(tmp_path / "dataset")
    runspec = RunSpec(
        id="run-1",
        runId="run-1",
        experimentId="exp-1",
        dataset=dataset,
        questionId="q_year",
        question="In which year did the researcher obtain their PhD?",
        questionTemplate="In which year did the researcher obtain their PhD?",
        instanceId="cv-demo",
        provider="recording",
        modelName="recording",
        strategy="inline",
        format="json",
        repeatIndex=1,
        params={},
        metadata=RunMetadata(
            canonicalId="exp-1|q_year|cv-demo|recording|recording|inline|json|1",
            questionId="q_year",
            instanceId="cv-demo",
            provider="recording",
            modelName="recording",
            strategy="inline",
            format="json",
            repeatIndex=1,
        ),
    )
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model

    execute_runspec(runspec, engine)

    assert model.last_request is not None
    assert model.last_request.params["structured_output"] == {
        "name": "q_year_response",
        "strict": True,
        "schema": {"type": "number"},
    }
