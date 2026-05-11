from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall, ToolResult, ToolSpec
from copa.ai.models.claude import ClaudeModel
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.trace import TraceCollector
from copa.benchmark.evaluation import _evaluate_judge, evaluate_run_result
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import (
    EvaluationJudgeInfo,
    EvaluationTrace,
    Experiment,
    ExperimentDataset,
    RunResult,
    RunTiming,
    RunTrace,
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
    (root / "questions.instance.json").write_text(
        json.dumps(
            {
                "datasetId": "mock-v2",
                "instances": [
                    {
                        "instanceId": "cv-demo",
                        "contextBlocks": "context/cv-demo/blocks.json",
                        "questions": [
                            {"id": "q_year"},
                            {"id": "q_summary", "parameters": {"researcher_name": "CV Demo"}},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (instance_dir / "parsed.json").write_text(json.dumps({"answers": {"q_year": 2020}}), encoding="utf-8")
    (instance_dir / "raw.html").write_text("ANSWER[q_year]: 2020\n", encoding="utf-8")
    (instance_dir / "clean.html").write_text("ANSWER[q_year]: 2020\n", encoding="utf-8")
    (instance_dir / "blocks.json").write_text(
        json.dumps({"summary": "Researcher in software engineering.", "research": "Works with distributed systems."}),
        encoding="utf-8",
    )
    return ExperimentDataset(root=str(root.resolve()))


def test_dataset_provider_context_blocks_falls_back_to_instance_blocks_file(tmp_path):
    dataset = write_mock_dataset(tmp_path / "dataset")
    payload = json.loads((Path(dataset.root) / "questions.instance.json").read_text(encoding="utf-8"))
    payload["instances"][0].pop("contextBlocks", None)
    (Path(dataset.root) / "questions.instance.json").write_text(json.dumps(payload), encoding="utf-8")

    provider = DatasetProvider.from_dataset(dataset)

    assert provider.get_context_blocks("cv-demo") == {
        "summary": "Researcher in software engineering.",
        "research": "Works with distributed systems.",
    }


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
            cached_input_tokens=4,
            cache_read_input_tokens=4,
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
    assert result.usage == {
        "inputTokens": 11,
        "outputTokens": 1,
        "totalTokens": 12,
        "cachedInputTokens": 4,
        "cacheReadInputTokens": 4,
    }


def test_classify_provider_error_treats_taskgroup_as_transient():
    from copa.ai.rate_control import classify_provider_error

    info = classify_provider_error("google", RuntimeError("unhandled errors in a TaskGroup (1 sub-exception)"))

    assert info.kind == "transient"


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
    assert result.trace["metrics"]["mcpToolCalls"] == 1


def test_engine_resolves_remote_mcp_and_keeps_local_mcp_distinct():
    engine = Engine(tool_runtime_factories={"local_mcp": lambda: FakeLattesRuntime()})

    remote_strategy, remote_runtime = engine._resolve_strategy("remote_mcp")
    local_strategy, local_runtime = engine._resolve_strategy("local_mcp")

    assert type(remote_strategy).__name__ == "MCPStrategy"
    assert remote_runtime is None
    assert type(local_strategy).__name__ == "LocalMCPStrategy"
    assert local_runtime is not None
    local_runtime.close()


def test_engine_rejects_bare_mcp_strategy_name():
    engine = Engine()

    with pytest.raises(ValueError, match="Unknown strategy: mcp"):
        engine._resolve_strategy("mcp")


def test_experiment_validation_rejects_bare_mcp_strategy_factor():
    with pytest.raises(ValueError, match="unknown strategy: mcp"):
        Experiment.model_validate(
            {
                "id": "exp-test",
                "output": "outputs",
                "dataset": "/tmp/dataset",
                "scope": {"instances": [], "questions": []},
                "factors": {
                    "model": [{"provider": "mock", "name": "mock"}],
                    "strategy": ["mcp"],
                    "format": ["json"],
                },
            }
        )


def test_runspec_model_validate_rejects_bare_mcp_strategy_in_public_record():
    with pytest.raises(ValueError, match="unknown strategy: mcp"):
        RunSpec.model_validate(
            {
                "trialId": "trial-1",
                "experimentId": "exp-1",
                "taskId": "q_year",
                "question": "In which year did the researcher obtain their PhD?",
                "dataset": {"root": "/tmp/dataset"},
                "instanceId": "cv-demo",
                "provider": "mock",
                "model": "mock",
                "modelId": "mock",
                "strategy": "mcp",
                "format": "json",
                "params": {},
                "repeatIndex": 1,
                "trace": {"enabled": False, "writeFiles": True, "save_raw_response": False, "save_tool_calls": False, "save_usage": False, "save_errors": False},
                "artifacts": {"writeJsonl": True, "writeIndividualJson": False},
                "metadata": {
                    "canonicalId": "exp-1|q_year|cv-demo|mock|mock|mcp|json|1",
                    "taskId": "q_year",
                    "instanceId": "cv-demo",
                    "provider": "mock",
                    "modelId": "mock",
                    "modelName": "mock",
                    "strategy": "mcp",
                    "format": "json",
                    "repeatIndex": 1,
                },
            }
        )


def test_runresult_model_validate_rejects_bare_mcp_strategy_in_public_record():
    with pytest.raises(ValueError, match="unknown strategy: mcp"):
        RunResult.model_validate(
            {
                "trialId": "trial-1",
                "experimentId": "exp-1",
                "taskId": "q_year",
                "question": "In which year did the researcher obtain their PhD?",
                "dataset": {"root": "/tmp/dataset"},
                "instanceId": "cv-demo",
                "provider": "mock",
                "model": "mock",
                "modelId": "mock",
                "strategy": "mcp",
                "format": "json",
                "repeatIndex": 1,
                "status": "success",
                "response": "2018",
                "timing": {"startedAt": "2026-01-01T00:00:00Z", "finishedAt": "2026-01-01T00:00:01Z", "durationMs": 1000},
                "usage": {},
                "metricsSummary": {},
                "metadata": {
                    "canonicalId": "exp-1|q_year|cv-demo|mock|mock|mcp|json|1",
                    "taskId": "q_year",
                    "instanceId": "cv-demo",
                    "provider": "mock",
                    "modelId": "mock",
                    "modelName": "mock",
                    "strategy": "mcp",
                    "format": "json",
                    "repeatIndex": 1,
                },
            }
        )


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
        result=type("R", (), {"answer": "Answer", "runId": "run-1", "experimentId": "exp-1", "instanceId": "cv-demo", "questionId": "q_summary"})(),
        question_text="Question?",
        context_payload={"summary": "Ground truth answer."},
        judges=make_experiment().evaluation.judges,
        engine=Engine(),
    )

    assert details["outcome"]["correctness"]["rating"] == "meets"
    assert details["outcome"]["completeness"]["rating"] == "partial"
    assert details["outcome"]["correctness"]["agreement"] is True
    assert details["outcome"]["completeness"]["agreement"] is True
    assert len(details["judges"]) == 1
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
        result=type("R", (), {"answer": "Answer", "runId": "run-1", "experimentId": "exp-1", "instanceId": "cv-demo", "questionId": "q_summary"})(),
        question_text="Question?",
        context_payload={"summary": "Ground truth answer."},
        judges=experiment.evaluation.judges,
        engine=Engine(),
    )

    assert details["outcome"]["correctness"]["rating"] == "meets"
    assert details["outcome"]["correctness"]["agreement"] is False
    assert details["outcome"]["completeness"]["rating"] == "partial"
    assert details["outcome"]["completeness"]["agreement"] is True
    assert len(details["judges"]) == 2
    assert judge_info.used is True


def test_judge_request_injects_structured_output_schema():
    from copa.benchmark.evaluation import _judge_request

    engine = Engine()
    model = RecordingJudgeModel()
    engine._models["openai"] = model

    payload, judge_info, _ = _judge_request(
        config=type(
            "Cfg",
            (),
            {
                "provider": "openai",
                "model": "recording_judge",
                "temperature": 0,
                "params": {},
            },
        )(),
        prompt="Judge this answer.",
        answer_text="The candidate answer.",
        run_id="run-1",
        exp_id="exp-1",
        instance_id="cv-demo",
        question_id="q_summary",
        question_text="Question?",
        curriculum_context='{"summary":"Research summary"}',
        engine=engine,
    )

    assert payload is not None
    assert judge_info.used is True
    assert model.last_request is not None
    assert model.last_request.params["structured_output"]["schema"]["type"] == "object"
    assert model.last_request.params["structured_output"]["schema"]["required"] == ["correctness", "completeness"]
    assert model.last_request.params["prompt_cache_key"].startswith("jud:ctx:")


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
        strategy="remote_mcp",
        format="json",
        repeatIndex=1,
        params={"mcp_server": {"server_url": "https://example.test/mcp"}},
        metadata=RunMetadata(
            canonicalId="exp-1|q_year|cv-demo|mock|mock|remote_mcp|json|1",
            questionId="q_year",
            instanceId="cv-demo",
            provider="mock",
            modelName="mock",
            strategy="remote_mcp",
            format="json",
            repeatIndex=1,
        ),
    )

    result = execute_runspec(runspec, Engine())

    assert isinstance(result.answer, str)
    assert result.metricsSummary["toolCalls"] is None
    assert result.metricsSummary["functionCalls"] is None
    assert result.metricsSummary["inputTokens"] is None


def test_execute_runspec_injects_openai_inline_prompt_cache_key(tmp_path):
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
        provider="openai",
        modelName="gpt-5.4-mini",
        strategy="inline",
        format="html",
        repeatIndex=1,
        params={},
        metadata=RunMetadata(
            canonicalId="exp-1|q_year|cv-demo|openai|gpt-5.4-mini|inline|html|1",
            questionId="q_year",
            instanceId="cv-demo",
            provider="openai",
            modelName="gpt-5.4-mini",
            strategy="inline",
            format="html",
            repeatIndex=1,
        ),
    )
    engine = Engine()
    model = RecordingModel()
    engine._models["openai"] = model

    execute_runspec(runspec, engine)

    assert model.last_request is not None
    cache_key = model.last_request.params["prompt_cache_key"]
    assert cache_key.startswith("inl:html:")
    assert len(cache_key) <= 64


def test_openai_model_build_payload_includes_prompt_cache_fields():
    model = OpenAIModel()
    request = AIRequest(
        question="Question?",
        context="Context",
        provider_name="openai",
        model_name="gpt-5.4-mini",
        strategy_name="inline",
        context_format="text",
        params={
            "prompt_cache_key": "inl:html:abc123",
            "prompt_cache_retention": "24h",
        },
        metadata={},
    )
    model_input = ModelInput(system_instruction="System", prompt="Prompt")

    payload = model._build_payload(model_input, request)

    assert payload["prompt_cache_key"] == "inl:html:abc123"
    assert payload["prompt_cache_retention"] == "24h"


def test_evaluate_run_result_skips_when_context_block_missing(tmp_path):
    # Add a question whose contextBlock references a block that doesn't exist in blocks.json
    dataset_root = tmp_path / "dataset"
    dataset = write_mock_dataset(dataset_root)
    questions_path = dataset_root / "questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8"))
    questions["questions"].append({
        "id": "q_missing",
        "question": "What is the missing answer?",
        "tags": [],
        "validation": {"type": "judge"},
        "contextBlock": ["nonexistent_block"],
    })
    questions_path.write_text(json.dumps(questions), encoding="utf-8")
    instances_path = dataset_root / "questions.instance.json"
    instances = json.loads(instances_path.read_text(encoding="utf-8"))
    instances["instances"][0]["questions"].append({"id": "q_missing"})
    instances_path.write_text(json.dumps(instances), encoding="utf-8")

    provider = DatasetProvider.from_dataset(dataset)
    events: list[tuple[str, str, dict[str, object]]] = []
    result = RunResult(
        runId="run-skip",
        experimentId="exp-1",
        dataset=dataset,
        questionId="q_missing",
        question="What is the missing answer?",
        questionTemplate="What is the missing answer?",
        questionTags=[],
        validationType="judge",
        contextBlock=[],
        parameters={},
        instanceId="cv-demo",
        provider="mock",
        modelName="mock",
        strategy="inline",
        format="json",
        repeatIndex=1,
        answer="unknown",
        status="success",
        timing=RunTiming(startedAt="2026-01-01T00:00:00Z", finishedAt="2026-01-01T00:00:01Z", durationMs=1000),
        usage={},
        metricsSummary={},
        trace=RunTrace(),
        metadata=RunMetadata(
            canonicalId="exp-1|q_missing|cv-demo|mock|mock|inline|json|1",
            questionId="q_missing",
            instanceId="cv-demo",
            provider="mock",
            modelName="mock",
            strategy="inline",
            format="json",
            repeatIndex=1,
        ),
    )

    evaluated = evaluate_run_result(
        result,
        provider,
        judges=[make_experiment().evaluation.judges[0]],
        engine=Engine(),
        event_logger=lambda label, message, fields: events.append((label, message, fields)),
    )

    assert evaluated is not None
    item = evaluated.items[0]
    assert item.status == "skipped"
    assert "nonexistent_block" in item.details.get("error", "")
    artifact = item.to_persisted_artifact()
    assert artifact["status"] == "skipped"
    assert artifact["judgeCount"] == 0
    assert any(label == "SKIP" and fields.get("questionId") == "q_missing" for label, _message, fields in events)


def test_openai_model_extracts_cache_metadata():
    class UsageDetails:
        def __init__(self, cached_tokens: int) -> None:
            self.cached_tokens = cached_tokens

    class Usage:
        def __init__(self) -> None:
            self.input_tokens = 100
            self.output_tokens = 10
            self.total_tokens = 110
            self.input_tokens_details = UsageDetails(cached_tokens=64)
            self.prompt_tokens_details = [{"type": "cached_tokens", "token_count": 64}]
            self.cache_tokens_details = {"cached_tokens": 64}
            self.cached_content_token_count = 64

    class Response:
        def __init__(self) -> None:
            self.usage = Usage()
            self.output_text = "ok"
            self.output = []

    model = OpenAIModel()
    metadata = model._extract_cache_metadata(Response())

    assert metadata == {
        "cache": {
            "input_tokens_details": {"cached_tokens": 64},
            "prompt_tokens_details": [{"type": "cached_tokens", "token_count": 64}],
            "cache_tokens_details": {"cached_tokens": 64},
            "cached_content_token_count": 64,
        }
    }


def test_openai_model_extracts_cached_input_tokens():
    class UsageDetails:
        def __init__(self, cached_tokens: int) -> None:
            self.cached_tokens = cached_tokens

    class Usage:
        def __init__(self) -> None:
            self.input_tokens_details = UsageDetails(cached_tokens=64)

    class Response:
        def __init__(self) -> None:
            self.usage = Usage()

    assert OpenAIModel()._extract_cached_input_tokens(Response()) == 64


def test_claude_model_extracts_cache_usage():
    class Usage:
        def __init__(self) -> None:
            self.cache_read_input_tokens = 100
            self.cache_creation_input_tokens = 25

    class Response:
        def __init__(self) -> None:
            self.usage = Usage()

    assert ClaudeModel()._extract_cache_usage(Response()) == (100, 25)


def test_gemini_model_extracts_cached_input_tokens():
    class UsageMetadata:
        def __init__(self) -> None:
            self.cached_content_token_count = 42

    class Response:
        def __init__(self) -> None:
            self.usage_metadata = UsageMetadata()

    assert GeminiModel()._extract_cached_input_tokens(Response()) == 42
