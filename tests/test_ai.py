from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse
from copa.ai.models.claude import ClaudeModel
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.strategies.inline import DEFAULT_SYSTEM_INSTRUCTION
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import ExperimentDataset, ExperimentTrace, RunSpec


def make_request(**overrides: object) -> AIRequest:
    payload = {
        "question": "How many publications are listed?",
        "context": '{"answers": {"q1": "3"}}',
        "provider_name": "mock",
        "model_name": "mock",
        "strategy_name": "inline",
        "context_format": "json",
        "params": {},
        "metadata": {"question_id": "q1"},
    }
    payload.update(overrides)
    return AIRequest(**payload)


class RecordingModel(ModelAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.last_input: ModelInput | None = None

    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
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


class FailingModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
        raise RuntimeError("provider exploded")


def test_engine_inline_execution_records_prompt_trace_and_usage():
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model

    result = engine.execute(make_request(provider_name="recording"))

    assert result.answer == "3"
    assert result.error is None
    assert result.usage == {"inputTokens": 11, "outputTokens": 1, "totalTokens": 12}
    assert model.last_input is not None
    assert model.last_input.system_instruction == DEFAULT_SYSTEM_INSTRUCTION
    assert model.last_input.prompt.startswith("Context format: json")
    assert "Context:\n" in model.last_input.prompt
    assert "Question:\nHow many publications are listed?" in model.last_input.prompt

    metrics = result.trace["metrics"]
    assert metrics["context_size_chars"] == len('{"answers": {"q1": "3"}}')
    assert metrics["context_size_bytes"] == len('{"answers": {"q1": "3"}}'.encode("utf-8"))
    assert metrics["question_size_chars"] == len("How many publications are listed?")
    assert metrics["prompt_size_chars"] == len(model.last_input.prompt)
    assert metrics["model_calls"] == 1
    assert metrics["model_duration_ms"] == 7
    assert metrics["input_tokens"] == 11
    assert metrics["output_tokens"] == 1
    assert metrics["total_tokens"] == 12
    assert metrics["strategy_duration_ms"] is not None
    assert metrics["total_duration_ms"] is not None
    assert [event["name"] for event in result.trace["events"]] == [
        "model.generate",
        "strategy.inline.execute",
        "engine.execute",
    ]


def test_engine_normalizes_errors_and_preserves_trace():
    engine = Engine()
    engine._models["failing"] = FailingModel()

    result = engine.execute(make_request(provider_name="failing"))

    assert result.answer == ""
    assert result.error == "provider exploded"
    assert result.trace["metrics"]["model_calls"] == 0
    assert result.trace["metrics"]["strategy_duration_ms"] is not None
    assert result.trace["metrics"]["total_duration_ms"] is not None
    assert [event["name"] for event in result.trace["events"]] == [
        "strategy.inline.execute",
        "engine.execute",
        "error",
    ]
    assert result.trace["events"][-1]["metadata"]["error"] == "provider exploded"


def test_execute_runspec_persists_ai_trace_usage_and_raw_response():
    runspec = RunSpec(
        id="run-1",
        experimentId="exp-1",
        dataset=ExperimentDataset(
            questions=str((Path.cwd() / "examples" / "basic" / "datasets" / "questions.json").resolve()),
            contexts=str((Path.cwd() / "examples" / "basic" / "datasets" / "contexts").resolve()),
            question_instances=str(
                (Path.cwd() / "examples" / "basic" / "datasets" / "questions.instance.json").resolve()
            ),
        ),
        questionId="q_exact_001",
        contextId="cv_demo",
        provider="mock",
        strategy="inline",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=True,
        params={"model_name": "mock"},
        trace=ExperimentTrace(
            enabled=True,
            save_raw_response=True,
            save_tool_calls=True,
            save_usage=True,
            save_errors=True,
        ),
    )

    result = execute_runspec(runspec, Engine())

    assert result.status == "success"
    assert result.answer == "3"
    assert result.usage["inputTokens"] > 0
    assert result.usage["outputTokens"] == 1
    assert result.trace.rawResponse["prompt_preview"].startswith("Context format: json")
    assert result.trace.rawResponse["system_instruction_preview"] == DEFAULT_SYSTEM_INSTRUCTION[:200]
    assert result.trace.aiTrace["metrics"]["model_calls"] == 1
    assert result.trace.aiTrace["metrics"]["prompt_size_chars"] > 0
    assert result.trace.aiTrace["events"][-1]["name"] == "engine.execute"


def test_openai_model_normalizes_response():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        output_text="OpenAI answer",
        usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
        model_dump=lambda mode="json": {"id": "resp-openai"},
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = OpenAIModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(system_instruction="System", prompt="Prompt"),
        make_request(provider_name="openai", model_name="gpt-5"),
    )

    assert captured["instructions"] == "System"
    assert captured["input"] == "Prompt"
    assert result.text == "OpenAI answer"
    assert result.input_tokens == 9
    assert result.output_tokens == 4
    assert result.total_tokens == 13
    assert result.raw_response == {"id": "resp-openai"}
    assert result.metadata["provider"] == "openai"


def test_gemini_model_normalizes_response():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        text="Gemini answer",
        usage_metadata=SimpleNamespace(
            prompt_token_count=8,
            candidates_token_count=3,
            total_token_count=11,
        ),
        model_dump=lambda mode="json": {"id": "resp-gemini"},
    )
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = GeminiModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(system_instruction="System", prompt="Prompt"),
        make_request(provider_name="gemini", model_name="gemini-2.5"),
    )

    assert captured["contents"] == "Prompt"
    assert captured["config"]["system_instruction"] == "System"
    assert result.text == "Gemini answer"
    assert result.input_tokens == 8
    assert result.output_tokens == 3
    assert result.total_tokens == 11
    assert result.raw_response == {"id": "resp-gemini"}
    assert result.metadata["provider"] == "gemini"


def test_claude_model_normalizes_response():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        content=[SimpleNamespace(text="Claude answer")],
        usage=SimpleNamespace(input_tokens=7, output_tokens=2, total_tokens=9),
        model_dump=lambda mode="json": {"id": "resp-claude"},
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = ClaudeModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(system_instruction="System", prompt="Prompt"),
        make_request(provider_name="claude", model_name="claude-3-7-sonnet"),
    )

    assert captured["system"] == "System"
    assert captured["messages"] == [{"role": "user", "content": "Prompt"}]
    assert result.text == "Claude answer"
    assert result.input_tokens == 7
    assert result.output_tokens == 2
    assert result.total_tokens == 9
    assert result.raw_response == {"id": "resp-claude"}
    assert result.metadata["provider"] == "claude"
