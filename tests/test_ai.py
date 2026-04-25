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
                "judge": {"provider": "mock", "model": "mock", "temperature": 0},
            },
        }
    )


class RecordingModel(ModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.last_input: ModelInput | None = None

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.last_input = model_input
        return ModelResponse(
            text="3",
            raw_response={"provider": "recording"},
            input_tokens=11,
            output_tokens=1,
            total_tokens=12,
            duration_ms=7,
            metadata={"provider": "recording"},
        )


class ScriptedToolModel(ModelAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.inputs: list[ModelInput] = []

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.inputs.append(model_input)
        return self.responses.pop(0)


class FakeSectionRuntime:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(name="listSections", input_schema={"type": "object"}),
            ToolSpec(name="getSection", input_schema={"type": "object"}),
        ]

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        self.calls.append((name, arguments))
        if name == "listSections":
            return ToolResult(name=name, content=["summary", "research"])
        return ToolResult(name=name, content={"text": "software engineering"})

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
    assert model.last_input.prompt.startswith("Context format: json")
    metrics = result.trace["metrics"]
    assert metrics["question_tokens"] == len("How many publications are listed?".split())
    assert metrics["llm_call_count"] == 1
    assert metrics["total_llm_tokens"] == 12


def test_engine_local_function_uses_section_tools_and_records_calls():
    runtime = FakeSectionRuntime()
    engine = Engine(tool_runtime_factories={"local_function": lambda: runtime})
    model = ScriptedToolModel(
        [
            ModelResponse(
                requested_tool_calls=[ToolCall(name="listSections", arguments={"lattesId": "cv-demo"})],
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
    assert runtime.calls == [("listSections", {"lattesId": "cv-demo"})]
    assert "Tool usage:" in model.inputs[0].prompt
    assert result.trace["metrics"]["tool_call_count_semantic"] == 1


def test_heuristic_compare_supports_structured_answers():
    details = _heuristic_compare(
        '{"where": "UIUC", "yearsAgo": 26}',
        [{"where": "UIUC", "yearsAgo": 26}],
        {"type": "object"},
    )

    assert details["matched"] is True
    assert details["outcome"] == "accepted"


def test_evaluate_judge_persists_rating_and_justification(monkeypatch):
    from copa.benchmark import evaluation as evaluation_module

    def fake_judge_request(**kwargs):
        del kwargs
        return (
            {
                "groundedness": {"rating": "meets", "justification": "Supported by summary."},
                "correctness": {"rating": "meets", "justification": "Consistent with the section."},
                "completeness": {"rating": "partially meets", "justification": "Misses some nuance."},
            },
            EvaluationJudgeInfo(used=True, role="judge", provider="mock", model="mock"),
            EvaluationTrace(),
        )

    monkeypatch.setattr(evaluation_module, "_judge_request", fake_judge_request)

    details, judge_info, _ = _evaluate_judge(
        result=type("R", (), {"answer": "Answer", "runId": "run-1", "experimentId": "exp-1"})(),
        question_text="Question?",
        blocks={"summary": "Summary text", "research": "Research text"},
        refs=["summary", "research"],
        themes=["software engineering"],
        experiment=make_experiment(),
        engine=Engine(),
    )

    assert details["groundedness"]["rating"] == "meets"
    assert details["groundedness"]["justification"] == "Supported by summary."
    assert details["outcome"] == "partially_meets"
    assert judge_info.used is True


def test_execute_runspec_persists_metrics_summary_with_nulls_for_remote_mcp():
    runspec = RunSpec(
        id="run-1",
        runId="run-1",
        experimentId="exp-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "examples" / "datasets" / "lattes-simple").resolve())),
        questionId="q_phd_year",
        instanceId="5660469902738038",
        provider="mock",
        modelName="mock",
        strategy="mcp",
        format="json",
        repeatIndex=1,
        params={"mcp_server": {"server_url": "https://example.test/mcp"}},
        metadata=RunMetadata(
            canonicalId="exp-1|q_phd_year|5660469902738038|mock|mock|mcp|json|1",
            questionId="q_phd_year",
            instanceId="5660469902738038",
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
