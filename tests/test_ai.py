from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall, ToolResult, ToolSpec
from copa.ai.models.claude import ClaudeModel
from copa.ai.models.gemini import GeminiModel
from copa.ai.models.openai import OpenAIModel
from copa.ai.rate_control import (
    ConcurrencyLimiter,
    RateLimitCapacityError,
    RateControlRegistry,
    RateLimitedModelAdapter,
    TokenRateLimiter,
    estimate_tokens,
    extract_rate_limit_config,
)
from copa.ai.strategies.inline import DEFAULT_SYSTEM_INSTRUCTION
from copa.ai.trace import TraceCollector
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import Experiment, ExperimentDataset, ExperimentTrace, RunMetadata, RunSpec
from copa.benchmark.evaluation import EVALUATION_SYSTEM_INSTRUCTION, _evaluate_analytical, _evaluate_exact, _evaluate_unanswerable, evaluate_run_results
from copa.dataset.provider import DatasetProvider
from copa.dataset.questions import EvaluationDimension, EvaluationRubricCriterion, Question, QuestionEvaluation


def make_request(**overrides: object) -> AIRequest:
    payload = {
        "question": "How many publications are listed?",
        "context": '{"answers": {"q1": "3"}}',
        "provider_name": "mock",
        "model_name": "mock",
        "strategy_name": "inline",
        "context_format": "json",
        "params": {},
        "metadata": {"question_id": "q1", "lattes_id": "cv-demo", "context_id": "cv-demo"},
    }
    payload.update(overrides)
    return AIRequest(**payload)


def make_experiment(*, judge: dict[str, object] | None = None, fallback: dict[str, object] | None = None) -> Experiment:
    payload: dict[str, object] = {
        "id": "exp-test",
        "output": "outputs",
        "dataset": str((Path.cwd() / "examples" / "datasets" / "lattes").resolve()),
        "factors": {
            "model": [{"provider": "mock", "name": "mock"}],
            "strategy": ["inline"],
            "format": ["json"],
        },
        "evaluation": {
            "enabled": True,
        },
    }
    evaluation = dict(payload["evaluation"])
    if judge is not None:
        evaluation["judge"] = judge
    if fallback is not None:
        evaluation["fallback"] = fallback
    payload["evaluation"] = evaluation
    return Experiment.model_validate(payload)


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


class FailingModel(ModelAdapter):
    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        raise RuntimeError("provider exploded")


class ScriptedMCPModel(ModelAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.inputs: list[ModelInput] = []

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.inputs.append(model_input)
        if not self.responses:
            raise AssertionError("No scripted response left.")
        return self.responses.pop(0)


class FlakyRateLimitModel(ModelAdapter):
    def __init__(self, failures: int, *, error: Exception | None = None) -> None:
        super().__init__()
        self.failures = failures
        self.calls = 0
        self.error = error or RuntimeError("429 too many requests")

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return ModelResponse(
            text="ok",
            input_tokens=10,
            output_tokens=2,
            total_tokens=12,
            duration_ms=3,
            metadata={"provider": request.provider_name},
        )


class JSONModel(ModelAdapter):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        return ModelResponse(
            text=self.text,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            duration_ms=2,
            metadata={"provider": request.provider_name},
        )


class RecordingJSONModel(ModelAdapter):
    def __init__(self, text: str) -> None:
        super().__init__()
        self.text = text
        self.last_input: ModelInput | None = None

    def generate(self, model_input: ModelInput, request: AIRequest, trace: TraceCollector | None = None) -> ModelResponse:
        self.last_input = model_input
        return ModelResponse(
            text=self.text,
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
            duration_ms=2,
            metadata={"provider": request.provider_name},
        )


class FakeToolRuntime:
    def __init__(self, result_prefix: str = "ctx") -> None:
        self.result_prefix = result_prefix
        self.called_lattes_ids: list[str] = []
        self.closed = False

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="basicInformation",
                description="Return basic information.",
                input_schema={
                    "type": "object",
                    "properties": {"lattesId": {"type": "string"}},
                    "required": ["lattesId"],
                    "additionalProperties": False,
                },
            )
        ]

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        if name == "explode":
            raise RuntimeError("tool exploded")
        lattes_id = str(arguments.get("lattesId", "missing"))
        self.called_lattes_ids.append(lattes_id)
        return ToolResult(name=name, content={"lattesId": lattes_id, "value": f"{self.result_prefix}:{lattes_id}"})

    def close(self) -> None:
        self.closed = True


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


def test_engine_inline_uses_request_system_instruction_override():
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model

    result = engine.execute(
        make_request(
            provider_name="recording",
            system_instruction="Evaluation-only system instruction.",
        )
    )

    assert result.error is None
    assert model.last_input is not None
    assert model.last_input.system_instruction == "Evaluation-only system instruction."


def test_engine_execute_model_input_records_trace_and_usage():
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model
    request = make_request(provider_name="recording")
    model_input = ModelInput(system_instruction="Judge system.", prompt="Prompt body")

    result = engine.execute_model_input(request, model_input)

    assert result.answer == "3"
    assert result.error is None
    assert result.usage == {"inputTokens": 11, "outputTokens": 1, "totalTokens": 12}
    assert model.last_input is not None
    assert model.last_input.system_instruction == "Judge system."
    assert model.last_input.prompt == "Prompt body"
    metrics = result.trace["metrics"]
    assert metrics["prompt_size_chars"] == len("Prompt body")
    assert metrics["model_calls"] == 1
    assert [event["name"] for event in result.trace["events"]] == [
        "model.generate",
        "engine.execute_model_input",
    ]


def test_engine_local_function_executes_tool_loop_and_records_trace():
    runtime = FakeToolRuntime()
    engine = Engine(tool_runtime_factories={"local_function": lambda: runtime})
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(
                requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-demo"})],
                duration_ms=5,
                input_tokens=10,
                output_tokens=0,
                total_tokens=10,
                metadata={"provider": "scripted"},
                raw_response={"step": 1},
            ),
            ModelResponse(
                text="Researcher found",
                duration_ms=6,
                input_tokens=4,
                output_tokens=2,
                total_tokens=6,
                metadata={"provider": "scripted"},
                raw_response={"step": 2},
            ),
        ]
    )
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_function"))

    assert result.answer == "Researcher found"
    assert result.error is None
    assert len(model.inputs) == 2
    assert len(model.inputs[0].tools) == 1
    assert model.inputs[0].tool_results == []
    assert "Researcher Lattes ID:\ncv-demo" in model.inputs[0].prompt
    assert model.inputs[1].tool_results[0].content["lattesId"] == "cv-demo"
    assert result.tool_calls[0]["name"] == "basicInformation"
    assert result.tool_calls[0]["result"]["value"] == "ctx:cv-demo"
    metrics = result.trace["metrics"]
    assert metrics["model_calls"] == 2
    assert metrics["mcp_tool_calls"] == 1
    assert metrics["model_duration_ms"] == 11
    assert metrics["total_tokens"] == 16
    assert [event["name"] for event in result.trace["events"]] == [
        "model.generate",
        "mcp.tool_call",
        "mcp.tool_result",
        "model.generate",
        "strategy.local_function.execute",
        "engine.execute",
    ]


def test_engine_local_mcp_executes_tool_loop_and_records_trace():
    runtime = FakeToolRuntime(result_prefix="mcp")
    engine = Engine(tool_runtime_factories={"local_mcp": lambda: runtime})
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(
                requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-demo"})],
                duration_ms=5,
                input_tokens=10,
                output_tokens=0,
                total_tokens=10,
                metadata={"provider": "scripted"},
                raw_response={"step": 1},
            ),
            ModelResponse(
                text="Researcher found",
                duration_ms=6,
                input_tokens=4,
                output_tokens=2,
                total_tokens=6,
                metadata={"provider": "scripted"},
                raw_response={"step": 2},
            ),
        ]
    )
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_mcp"))

    assert result.answer == "Researcher found"
    assert result.error is None
    assert len(model.inputs) == 2
    assert len(model.inputs[0].tools) == 1
    assert "Researcher Lattes ID:\ncv-demo" in model.inputs[0].prompt
    assert model.inputs[1].tool_results[0].content["lattesId"] == "cv-demo"
    assert result.tool_calls[0]["result"]["value"] == "mcp:cv-demo"
    assert result.trace["metrics"]["mcp_tool_calls"] == 1
    assert [event["name"] for event in result.trace["events"]] == [
        "model.generate",
        "mcp.tool_call",
        "mcp.tool_result",
        "model.generate",
        "strategy.local_mcp.execute",
        "engine.execute",
    ]


def test_rate_limited_model_retries_on_429_and_records_trace():
    model = FlakyRateLimitModel(
        1,
        error=RuntimeError("429 too many requests"),
    )
    wrapper = RateLimitedModelAdapter(
        model,
        RateControlRegistry(),
        provider_name="openai",
        model_name="gpt-5",
    )
    trace = TraceCollector()

    response = wrapper.generate(
        ModelInput(system_instruction="s", prompt="prompt"),
        make_request(
            provider_name="openai",
            model_name="gpt-5",
            params={
                "rate_limit": {
                    "max_attempts": 2,
                    "base_delay_ms": 0,
                    "max_delay_ms": 0,
                    "estimated_output_tokens": 20,
                }
            },
        ),
        trace=trace,
    )

    assert response.text == "ok"
    assert model.calls == 2
    assert trace.metrics.retry_count == 1
    assert trace.metrics.estimated_output_tokens == 20
    assert "retry.attempt" in [event.name for event in trace.events]
    assert "retry.sleep" in [event.name for event in trace.events]
    assert "rate_limit.reserve" in [event.name for event in trace.events]
    assert "rate_limit.reconcile" in [event.name for event in trace.events]


def test_rate_limited_model_honors_tpm_budget_and_tracks_wait():
    clock = {"now": 0.0}

    def fake_clock() -> float:
        return clock["now"]

    def fake_sleep(seconds: float) -> None:
        clock["now"] += seconds

    limiter = TokenRateLimiter(60, clock=fake_clock, sleeper=fake_sleep)
    first_wait = limiter.acquire(60)
    second_wait = limiter.acquire(60)

    assert first_wait == 0
    assert second_wait >= 60000


def test_engine_applies_rate_control_wrapper_to_registered_models():
    engine = Engine()
    model = RecordingModel()
    engine._models["recording"] = model

    result = engine.execute(
        make_request(
            provider_name="recording",
            model_name="recording-v1",
            params={"rate_limit": {"estimated_output_tokens": 9}},
        )
    )

    assert result.answer == "3"
    metrics = result.trace["metrics"]
    assert metrics["estimated_output_tokens"] == 9
    assert metrics["reserved_tokens"] is not None
    assert "rate_limit.reserve" in [event["name"] for event in result.trace["events"]]


def test_concurrency_limiter_releases_slot_after_exception():
    limiter = ConcurrencyLimiter(1)

    try:
        with limiter.slot():
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    with limiter.slot():
        acquired = True

    assert acquired is True


def test_rate_limited_model_fails_fast_when_single_request_exceeds_tpm_budget():
    model = RecordingModel()
    wrapper = RateLimitedModelAdapter(
        model,
        RateControlRegistry(),
        provider_name="openai",
        model_name="gpt-5",
    )

    try:
        wrapper.generate(
            ModelInput(system_instruction="s", prompt="x" * 5000),
            make_request(
                provider_name="openai",
                model_name="gpt-5",
                params={
                    "rate_limit": {
                        "tpm": 100,
                        "estimated_output_tokens": 600,
                    }
                },
                metadata={
                    "question_id": "q1",
                    "context_id": "ctx1",
                    "experiment_id": "exp1",
                },
            ),
            trace=TraceCollector(),
        )
        assert False, "Expected RateLimitCapacityError"
    except RateLimitCapacityError as exc:
        text = str(exc)
        assert "Single request exceeds configured TPM budget" in text
        assert "phase=execution" in text
        assert "question_id=q1" in text
        assert "context_id=ctx1" in text


def test_estimate_tokens_does_not_double_count_inline_context():
    context = Path("examples/datasets/lattes/context/5660469902738038.html").read_text(
        encoding="utf-8",
        errors="ignore",
    )
    prompt = f"Context format: html\n\nQuestion:\nHow many?\n\nContext:\n{context}\n"
    request = make_request(
        question="How many?",
        context=context,
        provider_name="openai",
        model_name="gpt-5.4-nano",
        strategy_name="inline",
        context_format="html",
        params={"rate_limit": {"tpm": 200000, "estimated_output_tokens": 600}},
    )
    config = extract_rate_limit_config(request, None)

    estimated_input, estimated_output, reserved_tokens = estimate_tokens(
        ModelInput(system_instruction="sys", prompt=prompt),
        request,
        config,
    )

    assert estimated_input < 120000
    assert estimated_output == 600
    assert reserved_tokens < 120000


def test_execute_runspec_sets_error_message_on_failure():
    runspec = RunSpec(
        id="run-fail-1",
        runId="run-fail-1",
        experimentId="exp-fail-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "examples" / "datasets" / "lattes").resolve())),
        questionId="q_exact_001",
        contextId="5660469902738038",
        provider="failing",
        strategy="inline",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=True,
        params={"model_name": "mock"},
        metadata=RunMetadata(
            canonicalId="exp-fail-1|q_exact_001|5660469902738038|failing|mock|inline|json|1",
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="failing",
            modelName="mock",
            strategy="inline",
            format="json",
            repeatIndex=1,
        ),
        trace=ExperimentTrace(
            enabled=True,
            save_raw_response=True,
            save_tool_calls=True,
            save_usage=True,
            save_errors=True,
        ),
    )
    engine = Engine()
    engine._models["failing"] = FailingModel()

    result = execute_runspec(runspec, engine)

    assert result.status == "error"
    assert result.errorMessage == "provider exploded"


def test_evaluate_run_results_skips_failed_execution_runs():
    experiment = make_experiment()
    engine = Engine()
    engine._models["failing"] = FailingModel()
    failed = execute_runspec(
        RunSpec(
            id="run-fail-2",
            runId="run-fail-2",
            experimentId="exp-fail-2",
            dataset=ExperimentDataset(root=str((Path.cwd() / "examples" / "datasets" / "lattes").resolve())),
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="failing",
            strategy="inline",
            format="json",
            repeatIndex=1,
            outputRoot=None,
            evaluationEnabled=True,
            params={"model_name": "mock"},
            metadata=RunMetadata(
                canonicalId="exp-fail-2|q_exact_001|5660469902738038|failing|mock|inline|json|1",
                questionId="q_exact_001",
                contextId="5660469902738038",
                provider="failing",
                modelName="mock",
                strategy="inline",
                format="json",
                repeatIndex=1,
            ),
            trace=ExperimentTrace(enabled=True, save_errors=True),
        ),
        engine,
    )

    evaluations = evaluate_run_results([failed], experiment=experiment)

    assert evaluations == []


def test_evaluate_exact_normalizes_numeric_expected_values():
    experiment = make_experiment(
        judge={"provider": "judge", "model": "judge-model", "temperature": 0},
    )
    result = SimpleNamespace(answer="The researcher has **3 publications** in **2026**.")
    question = Question(
        id="q_exact_001",
        question="How many publications?",
        evaluation=QuestionEvaluation(mode="exact", answerType="number"),
    )
    engine = Engine()
    engine._models["judge"] = JSONModel(
        json.dumps(
            {
                "extractedAnswer": 3,
                "isExtractable": True,
                "justification": "The answer explicitly states 3 publications.",
            }
        )
    )

    score, label, details, _, _ = _evaluate_exact(
        result,
        question,
        "3",
        [],
        engine,
        experiment,
    )

    assert score == 1.0
    assert label == "correct"
    assert details["extractedAnswer"] == 3
    assert details["expectedNormalized"] == 3
    assert details["evaluationMethod"] == "judge-extraction"
    assert details["isExtractable"] is True
    assert details["comparisonMethod"] == "numeric-equality"


def test_evaluate_exact_matches_accepted_answers_for_strings():
    experiment = make_experiment()
    result = SimpleNamespace(answer="Federal University of Bahia")
    question = Question(
        id="q_exact_002",
        question="What is the current affiliation?",
        evaluation=QuestionEvaluation(mode="exact", answerType="string"),
    )

    score, label, details, _, _ = _evaluate_exact(
        result,
        question,
        "UFBA",
        ["Federal University of Bahia"],
        Engine(),
        experiment,
    )

    assert score == 1.0
    assert label == "correct"
    assert details["evaluationMethod"] == "rule-fallback-extraction"


def test_evaluate_analytical_uses_judge_for_criteria_but_scores_deterministically():
    question = Question(
        id="q_analytical_001",
        question="Summarize the researcher profile.",
        evaluation=QuestionEvaluation(
            mode="analytical",
            rubric=[
                EvaluationRubricCriterion(id="teaching", description="Mentions teaching", weight=1),
                EvaluationRubricCriterion(id="research", description="Mentions research", weight=1),
                EvaluationRubricCriterion(id="impact", description="Mentions impact", weight=1),
            ],
        ),
    )
    experiment = make_experiment(
        judge={"provider": "judge", "model": "judge-model", "temperature": 0},
    )
    engine = Engine()
    engine._models["judge"] = JSONModel(
        json.dumps(
            {
                "matchedCriteria": ["teaching", "research"],
                "missingCriteria": ["impact"],
                "justification": "The answer covers teaching and research only.",
            }
        )
    )

    score, label, status, details, judge_info, _ = _evaluate_analytical(
        SimpleNamespace(answer="The profile shows teaching and research expertise."),
        question,
        None,
        {"availableThemes": ["teaching", "research", "impact"]},
        engine,
        experiment,
    )

    assert score == 0.6667
    assert label == "partial"
    assert status == "evaluated"
    assert details["matchedCriteria"] == ["teaching", "research"]
    assert details["missingCriteria"] == ["impact"]
    assert details["evaluationMethod"] == "judge-rubric"
    assert details["matchedWeight"] == 2
    assert details["totalWeight"] == 3
    assert judge_info.used is True


def test_evaluate_analytical_missing_rubric_is_invalid_config():
    experiment = make_experiment()
    question = Question(
        id="q_analytical_002",
        question="Summarize the profile.",
        evaluation=QuestionEvaluation(mode="analytical", rubric=[]),
    )

    score, label, status, details, _, _ = _evaluate_analytical(
        SimpleNamespace(answer="Anything."),
        question,
        None,
        None,
        Engine(),
        experiment,
    )

    assert score is None
    assert label is None
    assert status == "invalid-evaluation-config"
    assert details["reason"] == "Missing analytical rubric."
    assert details["evaluationMethod"] == "invalid-evaluation-config"


def test_evaluate_analytical_dimensions_uses_judge_and_scores_weighted():
    question = Question(
        id="q_summary_001",
        question="Summarize the main fields.",
        evaluation=QuestionEvaluation(
            mode="analytical",
            dimensions=[
                EvaluationDimension(
                    id="main-fields",
                    weight=2.0,
                    defaultScale=["absent", "partial", "present"],
                ),
                EvaluationDimension(
                    id="grounded",
                    weight=1.0,
                    defaultScale=["ungrounded", "partially-grounded", "grounded"],
                ),
            ],
        ),
    )
    experiment = make_experiment(
        judge={"provider": "judge", "model": "judge-model", "temperature": 0},
    )
    engine = Engine()
    engine._models["judge"] = JSONModel(
        json.dumps(
            {
                "dimensionAssessments": [
                    {
                        "id": "main-fields",
                        "label": "present",
                        "justification": "The answer identifies the main fields.",
                    },
                    {
                        "id": "grounded",
                        "label": "partially-grounded",
                        "justification": "Mostly grounded but slightly generic.",
                    },
                ],
                "overallJustification": "The answer is strong overall.",
            }
        )
    )

    score, label, status, details, judge_info, _ = _evaluate_analytical(
        SimpleNamespace(answer="Software engineering and distributed systems with cloud and microservices emphasis."),
        question,
        None,
        None,
        engine,
        experiment,
        evaluation_context_by_dimension={
            "main-fields": {"availableThemes": ["software engineering", "distributed systems"]},
            "grounded": {"allowedClaims": {"themes": ["software engineering", "distributed systems"]}},
        },
    )

    assert score == 0.8333
    assert label == "strong"
    assert status == "evaluated"
    assert details["evaluationMethod"] == "judge-dimensions"
    assert details["dimensionResults"]["main-fields"]["label"] == "present"
    assert details["dimensionResults"]["grounded"]["label"] == "partially-grounded"
    assert details["matchedWeight"] == 2.5
    assert details["totalWeight"] == 3.0
    assert judge_info.used is True




def test_evaluate_judge_uses_evaluation_specific_system_instruction():
    experiment = make_experiment(
        judge={"provider": "judge", "model": "judge-model", "temperature": 0},
    )
    engine = Engine()
    model = RecordingJSONModel(
        json.dumps(
            {
                "extractedAnswer": 2018,
                "isExtractable": True,
                "justification": "Explicitly stated.",
            }
        )
    )
    engine._models["judge"] = model
    question = Question(
        id="q_exact_001",
        question="In which year did the researcher obtain their Ph.D.?",
        evaluation=QuestionEvaluation(mode="exact", answerType="year"),
    )

    _evaluate_exact(
        SimpleNamespace(runId="run-1", experimentId="exp-1", answer="The Ph.D. was in 2018."),
        question,
        2018,
        [],
        engine,
        experiment,
    )

    assert model.last_input is not None
    assert model.last_input.system_instruction == EVALUATION_SYSTEM_INSTRUCTION


def test_evaluate_unanswerable_persists_classification_reason():
    score, label, details, _, _ = _evaluate_unanswerable(
        SimpleNamespace(answer="Not enough information in the document.")
    )

    assert score == 1.0
    assert label == "correct-abstention"
    assert details["classificationReason"] == "Matched abstention language."
    assert details["matchedPattern"] == "not enough information"
    assert details["evaluationMethod"] == "rule-unanswerable"


def test_lattes_dataset_loads_dimension_catalog_and_dimensions():
    provider = DatasetProvider.from_dataset(
        ExperimentDataset(root=str((Path("datasets/lattes")).resolve()))
    )

    question = provider.get_question("q_summary_001")
    instance = provider.get_question_instance("q_summary_001", "5660469902738038")

    assert question.evaluation is not None
    assert [item.id for item in question.evaluation.dimensions][:3] == [
        "main-fields",
        "topic-coverage",
        "grounded",
    ]
    assert question.evaluation.dimensions[0].defaultScale == ["absent", "partial", "present"]
    assert question.evaluation.dimensions[0].description == "Identifies the main research fields of the researcher."
    assert instance is not None
    assert "main-fields" in instance.evaluationContextByDimension
    assert "context-dependence" in instance.evaluationContextByDimension


def test_engine_local_function_binding_isolated_per_run():
    runtime = FakeToolRuntime()
    engine = Engine(tool_runtime_factories={"local_function": lambda: runtime})
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-a"})]),
            ModelResponse(text="first"),
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-b"})]),
            ModelResponse(text="second"),
        ]
    )
    engine._models["scripted"] = model

    first = engine.execute(
        make_request(provider_name="scripted", strategy_name="local_function", metadata={"context_id": "cv-a"})
    )
    second = engine.execute(
        make_request(provider_name="scripted", strategy_name="local_function", metadata={"context_id": "cv-b"})
    )

    assert first.tool_calls[0]["result"]["lattesId"] == "cv-a"
    assert second.tool_calls[0]["result"]["lattesId"] == "cv-b"
    assert runtime.called_lattes_ids == ["cv-a", "cv-b"]


def test_engine_local_function_returns_error_when_max_steps_exceeded():
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-demo"})]),
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-demo"})]),
        ]
    )
    engine = Engine(tool_runtime_factories={"local_function": lambda: FakeToolRuntime()})
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_function", params={"max_steps": 2}))

    assert result.answer == ""
    assert result.error == "Local function strategy exceeded max_steps=2."
    assert result.trace["metrics"]["mcp_tool_calls"] == 2
    assert "error" in [event["name"] for event in result.trace["events"]]


def test_engine_local_function_closes_runtime_after_execution():
    runtime = FakeToolRuntime()
    engine = Engine(tool_runtime_factories={"local_function": lambda: runtime})
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={"lattesId": "cv-demo"})]),
            ModelResponse(text="done"),
        ]
    )
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_function"))

    assert result.error is None
    assert runtime.closed is True


def test_engine_local_function_requires_explicit_runtime_injection():
    engine = Engine()

    result = engine.execute(make_request(strategy_name="local_function"))

    assert result.answer == ""
    assert result.error == "Unknown strategy: local_function"
    assert result.trace["events"][-1]["metadata"]["error"] == "Unknown strategy: local_function"


def test_engine_local_function_preserves_trace_on_tool_error():
    class ExplodingRuntime(FakeToolRuntime):
        def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
            raise RuntimeError("tool exploded")

    model = ScriptedMCPModel(
        responses=[ModelResponse(requested_tool_calls=[ToolCall(name="explode", arguments={"lattesId": "cv-demo"})])]
    )
    engine = Engine(tool_runtime_factories={"local_function": lambda: ExplodingRuntime()})
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="local_function"))

    assert result.answer == ""
    assert result.error == "tool exploded"
    assert result.trace["metrics"]["mcp_tool_calls"] == 1
    assert result.trace["events"][-1]["metadata"]["error"] == "tool exploded"


def test_execute_runspec_persists_ai_trace_usage_and_raw_response():
    runspec = RunSpec(
        id="run-1",
        runId="run-1",
        experimentId="exp-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "examples" / "datasets" / "lattes").resolve())),
        questionId="q_exact_001",
        contextId="5660469902738038",
        provider="mock",
        strategy="inline",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=True,
        params={"model_name": "mock"},
        metadata=RunMetadata(
            canonicalId="exp-1|q_exact_001|5660469902738038|mock|mock|inline|json|1",
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="mock",
            modelName="mock",
            strategy="inline",
            format="json",
            repeatIndex=1,
        ),
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
    assert result.answer
    assert result.usage["inputTokens"] > 0
    assert result.usage["outputTokens"] > 0
    assert result.trace.rawResponse["prompt_preview"].startswith("Context format: json")
    assert result.trace.rawResponse["system_instruction_preview"] == DEFAULT_SYSTEM_INSTRUCTION[:200]
    assert result.trace.aiTrace["metrics"]["model_calls"] == 1
    assert result.trace.aiTrace["metrics"]["prompt_size_chars"] > 0
    assert result.trace.aiTrace["events"][-1]["name"] == "engine.execute"


def test_execute_runspec_injects_runtime_for_local_function_strategy():
    runspec = RunSpec(
        id="run-local-function-1",
        runId="run-local-function-1",
        experimentId="exp-local-function-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "datasets" / "lattes").resolve())),
        questionId="q_exact_001",
        contextId="5660469902738038",
        provider="scripted",
        strategy="local_function",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=False,
        params={"model_name": "mock"},
        metadata=RunMetadata(
            canonicalId="exp-local-function-1|q_exact_001|5660469902738038|scripted|mock|local_function|json|1",
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="scripted",
            modelName="mock",
            strategy="local_function",
            format="json",
            repeatIndex=1,
        ),
        trace=ExperimentTrace(
            enabled=True,
            save_raw_response=True,
            save_tool_calls=True,
            save_usage=True,
            save_errors=True,
        ),
    )
    engine = Engine()
    engine._models["scripted"] = ScriptedMCPModel(
        responses=[
            ModelResponse(
                requested_tool_calls=[
                    ToolCall(
                        name="listPublications",
                        arguments={"lattesId": "5660469902738038", "startYear": 2026, "endYear": 2026},
                    )
                ]
            ),
            ModelResponse(text="3"),
        ]
    )

    result = execute_runspec(runspec, engine)

    assert result.status == "success"
    assert result.answer == "3"
    assert len(result.trace.toolCalls) == 1
    assert result.trace.toolCalls[0]["arguments"]["lattesId"] == "5660469902738038"
    assert len(result.trace.toolCalls[0]["result"]) == 3
    assert result.trace.aiTrace["metrics"]["mcp_tool_calls"] == 1


def test_execute_runspec_injects_runtime_for_local_mcp_strategy():
    runspec = RunSpec(
        id="run-local-mcp-1",
        runId="run-local-mcp-1",
        experimentId="exp-local-mcp-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "datasets" / "lattes").resolve())),
        questionId="q_exact_001",
        contextId="5660469902738038",
        provider="scripted",
        strategy="local_mcp",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=False,
        params={"model_name": "mock"},
        metadata=RunMetadata(
            canonicalId="exp-local-mcp-1|q_exact_001|5660469902738038|scripted|mock|local_mcp|json|1",
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="scripted",
            modelName="mock",
            strategy="local_mcp",
            format="json",
            repeatIndex=1,
        ),
        trace=ExperimentTrace(
            enabled=True,
            save_raw_response=True,
            save_tool_calls=True,
            save_usage=True,
            save_errors=True,
        ),
    )
    engine = Engine()
    engine._models["scripted"] = ScriptedMCPModel(
        responses=[
            ModelResponse(
                requested_tool_calls=[
                    ToolCall(
                        name="listPublications",
                        arguments={"lattesId": "5660469902738038", "startYear": 2026, "endYear": 2026},
                    )
                ]
            ),
            ModelResponse(text="3"),
        ]
    )

    result = execute_runspec(runspec, engine)

    assert result.status == "success"
    assert result.answer == "3"
    assert len(result.trace.toolCalls) == 1
    assert result.trace.toolCalls[0]["arguments"]["lattesId"] == "5660469902738038"
    assert len(result.trace.toolCalls[0]["result"]) == 3
    assert result.trace.aiTrace["metrics"]["mcp_tool_calls"] == 1
    assert result.trace.serverMcp


def test_execute_runspec_native_mcp_passes_request_to_provider_model():
    runspec = RunSpec(
        id="run-mcp-1",
        runId="run-mcp-1",
        experimentId="exp-mcp-1",
        dataset=ExperimentDataset(root=str((Path.cwd() / "datasets" / "lattes").resolve())),
        questionId="q_exact_001",
        contextId="5660469902738038",
        provider="scripted",
        strategy="mcp",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=False,
        params={
            "model_name": "mock",
            "mcp_server": {"server_url": "https://mcp.example.test", "server_label": "lattes"},
        },
        metadata=RunMetadata(
            canonicalId="exp-mcp-1|q_exact_001|5660469902738038|scripted|mock|mcp|json|1",
            questionId="q_exact_001",
            contextId="5660469902738038",
            provider="scripted",
            modelName="mock",
            strategy="mcp",
            format="json",
            repeatIndex=1,
        ),
        trace=ExperimentTrace(
            enabled=True,
            save_raw_response=True,
            save_tool_calls=True,
            save_usage=True,
            save_errors=True,
        ),
    )
    model = RecordingModel()
    engine = Engine()
    engine._models["scripted"] = model

    result = execute_runspec(runspec, engine)

    assert result.status == "success"
    assert result.answer == "3"
    assert result.trace.toolCalls == []
    assert model.last_input is not None
    assert "Researcher Lattes ID:\n5660469902738038" in model.last_input.prompt
    assert result.trace.aiTrace["metrics"]["model_calls"] == 1
    assert result.trace.aiTrace["metrics"]["mcp_tool_calls"] == 0


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
        make_request(
            provider_name="openai",
            model_name="gpt-5",
            metadata={"question_id": "q1", "runId": "run-123", "expId": "exp-456", "phase": "execution"},
        ),
    )

    assert captured["instructions"] == "System"
    assert captured["input"] == "Prompt"
    assert captured["metadata"] == {"runId": "run-123", "expId": "exp-456", "phase": "execution"}
    assert result.text == "OpenAI answer"
    assert result.input_tokens == 9
    assert result.output_tokens == 4
    assert result.total_tokens == 13
    assert result.raw_response == {"id": "resp-openai"}
    assert result.metadata["provider"] == "openai"


def test_openai_model_builds_native_mcp_tool_payload():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        output_text="OpenAI MCP answer",
        output=[],
        usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
        model_dump=lambda mode="json": {"id": "resp-openai-mcp"},
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
        make_request(
            provider_name="openai",
            model_name="gpt-5",
            strategy_name="mcp",
            params={
                "mcp_server": {
                    "server_url": "https://mcp.example.test",
                    "server_label": "lattes",
                    "allowed_tools": ["listPublications"],
                }
            },
            metadata={"question_id": "q1", "lattes_id": "cv-demo", "context_id": "cv-demo", "mcp_options": {"require_approval": "never"}},
        ),
    )

    assert captured["tools"] == [
        {
            "type": "mcp",
            "server_label": "lattes",
            "server_url": "https://mcp.example.test",
            "allowed_tools": ["listPublications"],
            "require_approval": "never",
        }
    ]
    assert result.text == "OpenAI MCP answer"


def test_openai_model_drops_authorization_header_when_authorization_param_is_set():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        output_text="OpenAI MCP answer",
        output=[],
        usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
        model_dump=lambda mode="json": {"id": "resp-openai-mcp-auth"},
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = OpenAIModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    model.generate(
        ModelInput(system_instruction="System", prompt="Prompt"),
        make_request(
            provider_name="openai",
            model_name="gpt-5",
            strategy_name="mcp",
            params={
                "mcp_server": {
                    "server_url": "https://mcp.example.test",
                    "server_label": "lattes",
                    "auth_token": "Bearer secret",
                    "headers": {
                        "Authorization": "Bearer stale",
                        "X-Server": "lattes",
                    },
                }
            },
        ),
    )

    assert captured["tools"] == [
        {
            "type": "mcp",
            "server_label": "lattes",
            "server_url": "https://mcp.example.test",
            "authorization": "Bearer secret",
            "headers": {"X-Server": "lattes"},
            "require_approval": "never",
        }
    ]


def test_openai_model_maps_tools_and_tool_results():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        output_text="",
        output=[
            SimpleNamespace(
                type="function_call",
                call_id="call-1",
                name="basicInformation",
                arguments='{"kind":"summary"}',
            )
        ],
        usage=SimpleNamespace(input_tokens=9, output_tokens=0, total_tokens=9),
        model_dump=lambda mode="json": {"id": "resp-openai-tool"},
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = OpenAIModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(
            system_instruction="System",
            prompt="Prompt",
            tools=[
                ToolSpec(
                    name="basicInformation",
                    description="Basic info",
                    input_schema={"type": "object", "properties": {"kind": {"type": "string"}}},
                )
            ],
            continuation_state={
                "response_output": [
                    {
                        "type": "function_call",
                        "call_id": "call-1",
                        "name": "basicInformation",
                        "arguments": '{"kind":"summary"}',
                    }
                ]
            },
            tool_results=[ToolResult(name="basicInformation", tool_call_id="call-1", content={"name": "Nabor"})],
        ),
        make_request(provider_name="openai", model_name="gpt-5"),
    )

    assert captured["tools"] == [
        {
            "type": "function",
            "name": "basicInformation",
            "description": "Basic info",
            "parameters": {"type": "object", "properties": {"kind": {"type": "string"}}},
        }
    ]
    assert captured["input"] == [
        {"role": "user", "content": [{"type": "input_text", "text": "Prompt"}]},
        {"type": "function_call", "call_id": "call-1", "name": "basicInformation", "arguments": '{"kind":"summary"}'},
        {"type": "function_call_output", "call_id": "call-1", "output": '{"name": "Nabor"}'},
    ]
    assert result.requested_tool_calls == [
        ToolCall(id="call-1", name="basicInformation", arguments={"kind": "summary"})
    ]
    assert result.continuation_state == {
        "response_output": [
            {"type": "function_call", "call_id": "call-1", "name": "basicInformation", "arguments": '{"kind":"summary"}'}
        ]
    }


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
        make_request(
            provider_name="gemini",
            model_name="gemini-2.5",
            metadata={"question_id": "q1", "runId": "run-123", "expId": "exp-456", "phase": "execution"},
        ),
    )

    assert captured["contents"] == "Prompt"
    config = captured["config"]
    system_instruction = getattr(config, "system_instruction", None)
    if system_instruction is None and isinstance(config, dict):
        system_instruction = config["system_instruction"]
    assert system_instruction == "System"
    assert result.text == "Gemini answer"
    assert result.input_tokens == 8
    assert result.output_tokens == 3
    assert result.total_tokens == 11
    assert result.raw_response == {"id": "resp-gemini"}
    assert result.metadata["provider"] == "gemini"


def test_gemini_model_uses_mcp_runtime_session_for_native_mcp():
    class DummySession:
        pass

    class AsyncGenerateContent:
        def __init__(self, callback):
            self._callback = callback

        async def __call__(self, **kwargs):
            return self._callback(**kwargs)

    captured: dict[str, object] = {}
    response = SimpleNamespace(
        text="Gemini MCP answer",
        function_calls=[],
        usage_metadata=SimpleNamespace(
            prompt_token_count=8,
            candidates_token_count=3,
            total_token_count=11,
        ),
        model_dump=lambda mode="json": {"id": "resp-gemini-mcp"},
    )
    model = GeminiModel(params={"api_key": "test-key"})
    model._create_client = lambda: SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(
                generate_content=AsyncGenerateContent(lambda **kwargs: captured.update(kwargs) or response)
            )
        )
    )

    from contextlib import asynccontextmanager

    class FakeMCPRuntime:
        @asynccontextmanager
        async def session(self):
            yield DummySession(), {
                "transport": "streamable_http",
                "serverUrl": "https://mcp.example.test",
                "serverLabel": "lattes",
                "clientFramework": "fastmcp",
            }

        def close(self) -> None:
            return None

    model._create_mcp_runtime = lambda _request: FakeMCPRuntime()

    result = model.generate(
        ModelInput(system_instruction="System", prompt="Prompt"),
        make_request(
            provider_name="gemini",
            model_name="gemini-2.5",
            strategy_name="mcp",
            params={"mcp_server": {"server_url": "https://mcp.example.test", "server_label": "lattes"}},
        ),
    )

    config = captured["config"]
    assert config["tools"][0].__class__.__name__ == "DummySession"
    assert result.text == "Gemini MCP answer"
    assert result.metadata["provider"] == "gemini"
    assert result.metadata["native_mcp"]["transport"] == "streamable_http"
    assert result.metadata["native_mcp"]["serverUrl"] == "https://mcp.example.test"


def test_gemini_model_maps_tools_and_tool_results():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        text="",
        function_calls=[SimpleNamespace(id="call-1", name="education", args={"level": "phd"})],
        candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(
                        role="model",
                        parts=[{"functionCall": {"name": "education", "args": {"level": "phd"}}, "thought_signature": b"sig-1"}],
                    )
                )
            ],
        usage_metadata=SimpleNamespace(
            prompt_token_count=8,
            candidates_token_count=0,
            total_token_count=8,
        ),
        model_dump=lambda mode="json": {"id": "resp-gemini-tool"},
    )
    client = SimpleNamespace(
        models=SimpleNamespace(
            generate_content=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = GeminiModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(
            system_instruction="System",
            prompt="Prompt",
            tools=[
                ToolSpec(
                    name="education",
                    description="Education info",
                    input_schema={"type": "object", "properties": {"level": {"type": "string"}}},
                )
            ],
                continuation_state={
                    "model_content": {
                        "role": "model",
                        "parts": [{"functionCall": {"name": "education", "args": {"level": "phd"}}, "thought_signature": b"sig-1"}],
                    }
                },
                tool_results=[ToolResult(name="education", tool_call_id="call-1", content={"items": []})],
        ),
        make_request(provider_name="gemini", model_name="gemini-2.5"),
    )

    config = captured["config"]
    tools = getattr(config, "tools", None)
    if tools is None and isinstance(config, dict):
        tools = config["tools"]
    first_tool = tools[0]
    declarations = getattr(first_tool, "function_declarations", None)
    if declarations is None and isinstance(first_tool, dict):
        declarations = first_tool["function_declarations"]
    first_decl = declarations[0]
    decl_name = getattr(first_decl, "name", None) or first_decl["name"]
    decl_description = getattr(first_decl, "description", None) or first_decl["description"]
    decl_schema = getattr(first_decl, "parameters_json_schema", None)
    if decl_schema is None and isinstance(first_decl, dict):
        decl_schema = first_decl["parameters_json_schema"]
    assert decl_name == "education"
    assert decl_description == "Education info"
    assert decl_schema == {"type": "object", "properties": {"level": {"type": "string"}}}

    contents = captured["contents"]
    model_content = contents[1]
    model_role = getattr(model_content, "role", None) or model_content["role"]
    assert model_role == "model"
    model_part = (getattr(model_content, "parts", None) or model_content["parts"])[0]
    function_call = getattr(model_part, "function_call", None) or model_part["functionCall"]
    call_name = getattr(function_call, "name", None) or function_call["name"]
    thought_signature = getattr(model_part, "thought_signature", None)
    if thought_signature is None and isinstance(model_part, dict):
        thought_signature = model_part["thought_signature"]
    assert call_name == "education"
    assert thought_signature == b"sig-1"

    response_content = contents[2]
    response_part = (getattr(response_content, "parts", None) or response_content["parts"])[0]
    function_response = getattr(response_part, "function_response", None) or response_part["functionResponse"]
    response_id = getattr(function_response, "id", None) or function_response["id"]
    response_payload = getattr(function_response, "response", None) or function_response["response"]
    assert response_id == "call-1"
    assert response_payload == {"result": {"items": []}}
    assert result.requested_tool_calls == [
        ToolCall(id="call-1", name="education", arguments={"level": "phd"})
    ]
    model_content = result.continuation_state["model_content"]
    assert getattr(model_content, "role", None) == "model"
    preserved_part = getattr(model_content, "parts", None)[0]
    if isinstance(preserved_part, dict):
        preserved_call = preserved_part["functionCall"]
        preserved_sig = preserved_part["thought_signature"]
    else:
        preserved_call = getattr(preserved_part, "function_call", None) or getattr(preserved_part, "functionCall", None)
        preserved_sig = getattr(preserved_part, "thought_signature", None)
    preserved_name = getattr(preserved_call, "name", None) or preserved_call["name"]
    assert preserved_name == "education"
    assert preserved_sig == b"sig-1"


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
        make_request(
            provider_name="claude",
            model_name="claude-3-7-sonnet",
            metadata={"question_id": "q1", "runId": "run-123", "expId": "exp-456", "phase": "execution"},
        ),
    )

    assert captured["system"] == "System"
    assert captured["messages"] == [{"role": "user", "content": "Prompt"}]
    assert captured["metadata"] == {"user_id": "runId=run-123;expId=exp-456;phase=execution"}
    assert result.text == "Claude answer"
    assert result.input_tokens == 7
    assert result.output_tokens == 2
    assert result.total_tokens == 9
    assert result.raw_response == {"id": "resp-claude"}
    assert result.metadata["provider"] == "claude"


def test_claude_model_builds_native_mcp_server_payload():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        content=[SimpleNamespace(text="Claude MCP answer")],
        usage=SimpleNamespace(input_tokens=7, output_tokens=2, total_tokens=9),
        model_dump=lambda mode="json": {"id": "resp-claude-mcp"},
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
        make_request(
            provider_name="claude",
            model_name="claude-3-7-sonnet",
            strategy_name="mcp",
            params={
                "mcp_server": {
                    "server_url": "https://mcp.example.test",
                    "server_label": "lattes",
                    "allowed_tools": ["listPublications"],
                    "auth_token": "Bearer secret",
                }
            },
        ),
    )

    assert captured["mcp_servers"] == [
        {
            "type": "url",
            "url": "https://mcp.example.test",
            "name": "lattes",
            "tool_configuration": {"enabled": True, "allowed_tools": ["listPublications"]},
            "authorization_token": "Bearer secret",
        }
    ]
    assert captured["betas"] == ["mcp-client-2025-04-04"]
    assert result.text == "Claude MCP answer"


def test_claude_model_maps_tools_and_tool_results():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        content=[
            SimpleNamespace(type="text", text="Checking tools"),
            SimpleNamespace(type="tool_use", id="call-1", name="linesOfResearch", input={"topic": "ai"}),
        ],
        usage=SimpleNamespace(input_tokens=7, output_tokens=0, total_tokens=7),
        model_dump=lambda mode="json": {"id": "resp-claude-tool"},
    )
    client = SimpleNamespace(
        messages=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )
    model = ClaudeModel(params={"api_key": "test-key"})
    model._create_client = lambda: client

    result = model.generate(
        ModelInput(
            system_instruction="System",
            prompt="Prompt",
            tools=[
                ToolSpec(
                    name="linesOfResearch",
                    description="Research lines",
                    input_schema={"type": "object", "properties": {"topic": {"type": "string"}}},
                )
            ],
            continuation_state={
                "assistant_content": [
                    {"type": "text", "text": "Checking tools"},
                    {"type": "tool_use", "id": "call-1", "name": "linesOfResearch", "input": {"topic": "ai"}},
                ]
            },
            tool_results=[ToolResult(name="linesOfResearch", tool_call_id="call-1", content={"items": ["AI"]})],
        ),
        make_request(provider_name="claude", model_name="claude-3-7-sonnet"),
    )

    assert captured["tools"] == [
        {
            "name": "linesOfResearch",
            "description": "Research lines",
            "input_schema": {"type": "object", "properties": {"topic": {"type": "string"}}},
        }
    ]
    assert captured["messages"][1]["role"] == "assistant"
    assert captured["messages"][1]["content"][0]["type"] == "text"
    assert captured["messages"][1]["content"][1]["type"] == "tool_use"
    assert captured["messages"][2]["content"][0]["type"] == "tool_result"
    assert json.loads(captured["messages"][2]["content"][0]["content"]) == {"items": ["AI"]}
    assert result.requested_tool_calls == [
        ToolCall(id="call-1", name="linesOfResearch", arguments={"topic": "ai"})
    ]
    assert result.continuation_state == {
        "assistant_content": [
            {"type": "text", "text": "Checking tools"},
            {"type": "tool_use", "id": "call-1", "name": "linesOfResearch", "input": {"topic": "ai"}},
        ]
    }


def test_evaluation_judge_requests_propagate_run_metadata_to_provider():
    captured: dict[str, object] = {}
    response = SimpleNamespace(
        output_text='{"extractedAnswer":"2018","isExtractable":true,"justification":"ok"}',
        usage=SimpleNamespace(input_tokens=9, output_tokens=4, total_tokens=13),
        model_dump=lambda mode="json": {"id": "resp-openai-eval"},
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: captured.update(kwargs) or response
        )
    )

    original_create_client = OpenAIModel._create_client
    OpenAIModel._create_client = lambda self: client
    try:
        experiment = make_experiment(judge={"provider": "openai", "model": "gpt-5", "temperature": 0})
        provider = ExperimentDataset(root=str((Path.cwd() / "examples" / "datasets" / "lattes").resolve()))
        result = evaluate_run_results(
            [
                execute_runspec(
                    RunSpec(
                        id="run-1",
                        runId="run-1",
                        experimentId="exp-1",
                        dataset=provider,
                        questionId="q_exact_003",
                        contextId="5660469902738038",
                        provider="mock",
                        modelName="mock",
                        strategy="inline",
                        format="json",
                        params={"model_name": "mock"},
                        repeatIndex=1,
                        outputRoot=None,
                        evaluationEnabled=True,
                        trace=ExperimentTrace(enabled=False),
                        metadata=RunMetadata(
                            canonicalId="exp-1|q_exact_003|5660469902738038|mock|mock|inline|json|1",
                            questionId="q_exact_003",
                            contextId="5660469902738038",
                            provider="mock",
                            modelName="mock",
                            strategy="inline",
                            format="json",
                            repeatIndex=1,
                        ),
                    ),
                    Engine(),
                )
            ],
            experiment=experiment,
        )
    finally:
        OpenAIModel._create_client = original_create_client

    assert result
    assert captured["metadata"] == {"runId": "run-1", "expId": "exp-1", "phase": "evaluation"}
