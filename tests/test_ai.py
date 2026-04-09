from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from copa.ai.engine import Engine
from copa.ai.models.base import AIRequest, ModelAdapter, ModelInput, ModelResponse, ToolCall, ToolResult, ToolSpec
from copa.ai.mcp.runtime import MCPRuntime
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


class ScriptedMCPModel(ModelAdapter):
    def __init__(self, responses: list[ModelResponse]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.inputs: list[ModelInput] = []

    def generate(self, model_input: ModelInput, request: AIRequest) -> ModelResponse:
        self.inputs.append(model_input)
        if not self.responses:
            raise AssertionError("No scripted response left.")
        return self.responses.pop(0)


class FakeMCPServer:
    def __init__(self, result_prefix: str = "ctx") -> None:
        self.result_prefix = result_prefix
        self.bound_context_ids: list[str] = []
        self.closed = False

    def bind(self, request: AIRequest) -> None:
        self.bound_context_ids.append(str(request.metadata.get("context_id", "missing")))

    def list_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="basicInformation",
                description="Return basic information.",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            )
        ]

    def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
        if name == "explode":
            raise RuntimeError("tool exploded")
        context_id = self.bound_context_ids[-1]
        return ToolResult(name=name, content={"contextId": context_id, "value": f"{self.result_prefix}:{context_id}"})

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


def test_engine_mcp_executes_tool_loop_and_records_trace():
    runtime = MCPRuntime(FakeMCPServer())
    engine = Engine(mcp_runtime=runtime)
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(
                requested_tool_calls=[ToolCall(name="basicInformation", arguments={})],
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

    result = engine.execute(make_request(provider_name="scripted", strategy_name="mcp"))

    assert result.answer == "Researcher found"
    assert result.error is None
    assert len(model.inputs) == 2
    assert len(model.inputs[0].tools) == 1
    assert model.inputs[0].tool_results == []
    assert model.inputs[1].tool_results[0].content["contextId"] == "missing"
    assert result.tool_calls[0]["name"] == "basicInformation"
    assert result.tool_calls[0]["result"]["value"] == "ctx:missing"
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
        "strategy.mcp.execute",
        "engine.execute",
    ]


def test_engine_mcp_binding_isolated_per_run():
    server = FakeMCPServer()
    engine = Engine(mcp_runtime=MCPRuntime(server))
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={})]),
            ModelResponse(text="first"),
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={})]),
            ModelResponse(text="second"),
        ]
    )
    engine._models["scripted"] = model

    first = engine.execute(
        make_request(provider_name="scripted", strategy_name="mcp", metadata={"context_id": "cv-a"})
    )
    second = engine.execute(
        make_request(provider_name="scripted", strategy_name="mcp", metadata={"context_id": "cv-b"})
    )

    assert first.tool_calls[0]["result"]["contextId"] == "cv-a"
    assert second.tool_calls[0]["result"]["contextId"] == "cv-b"
    assert server.bound_context_ids == ["cv-a", "cv-b"]


def test_engine_mcp_returns_error_when_max_steps_exceeded():
    model = ScriptedMCPModel(
        responses=[
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={})]),
            ModelResponse(requested_tool_calls=[ToolCall(name="basicInformation", arguments={})]),
        ]
    )
    engine = Engine(mcp_runtime=MCPRuntime(FakeMCPServer()))
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="mcp", params={"max_steps": 2}))

    assert result.answer == ""
    assert result.error == "MCP strategy exceeded max_steps=2."
    assert result.trace["metrics"]["mcp_tool_calls"] == 2
    assert "error" in [event["name"] for event in result.trace["events"]]


def test_engine_mcp_closes_injected_runtime_via_engine_close():
    server = FakeMCPServer()
    engine = Engine(mcp_runtime=MCPRuntime(server))

    engine.close()

    assert server.closed is True


def test_engine_mcp_requires_explicit_runtime_injection():
    engine = Engine()

    result = engine.execute(make_request(strategy_name="mcp"))

    assert result.answer == ""
    assert result.error == "MCP strategy requires an injected MCP runtime."
    assert result.trace["events"][-1]["metadata"]["error"] == "MCP strategy requires an injected MCP runtime."


def test_engine_mcp_preserves_trace_on_tool_error():
    class ExplodingRuntime(MCPRuntime):
        def __init__(self) -> None:
            super().__init__(FakeMCPServer())

        def call_tool(self, name: str, arguments: dict[str, object]) -> ToolResult:
            raise RuntimeError("tool exploded")

    model = ScriptedMCPModel(
        responses=[ModelResponse(requested_tool_calls=[ToolCall(name="explode", arguments={})])]
    )
    engine = Engine(mcp_runtime=ExplodingRuntime())
    engine._models["scripted"] = model

    result = engine.execute(make_request(provider_name="scripted", strategy_name="mcp"))

    assert result.answer == ""
    assert result.error == "tool exploded"
    assert result.trace["metrics"]["mcp_tool_calls"] == 1
    assert result.trace["events"][-1]["metadata"]["error"] == "tool exploded"


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


def test_execute_runspec_injects_runtime_for_mcp_strategy():
    runspec = RunSpec(
        id="run-mcp-1",
        experimentId="exp-mcp-1",
        dataset=ExperimentDataset(
            questions=str((Path.cwd() / "datasets" / "lattes" / "questions.json").resolve()),
            contexts=str((Path.cwd() / "datasets" / "lattes" / "cvs").resolve()),
            question_instances=str((Path.cwd() / "datasets" / "lattes" / "questions.instance.json").resolve()),
        ),
        questionId="q_exact_001",
        contextId="nabor",
        provider="scripted",
        strategy="mcp",
        format="json",
        repeatIndex=1,
        outputRoot=None,
        evaluationEnabled=False,
        params={"model_name": "mock"},
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
                requested_tool_calls=[ToolCall(name="listPublications", arguments={"startYear": 2026, "endYear": 2026})]
            ),
            ModelResponse(text="3"),
        ]
    )

    result = execute_runspec(runspec, engine)

    assert result.status == "success"
    assert result.answer == "3"
    assert len(result.trace.toolCalls) == 1
    assert len(result.trace.toolCalls[0]["result"]) == 3
    assert result.trace.aiTrace["metrics"]["mcp_tool_calls"] == 1


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
        make_request(provider_name="gemini", model_name="gemini-2.5"),
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
