from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field


class ExperimentDataset(BaseModel):
    questions: str
    contexts: str
    question_instances: str | None = None


class ExperimentParams(BaseModel):
    common: dict[str, Any] = Field(default_factory=dict)
    provider: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ExperimentExecution(BaseModel):
    repeats: int = 1
    output: str = "outputs"


class ExperimentEvaluation(BaseModel):
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class ExperimentTrace(BaseModel):
    enabled: bool = False
    save_raw_response: bool = False
    save_tool_calls: bool = False
    save_usage: bool = False
    save_errors: bool = False


class Experiment(BaseModel):
    id: str
    name: str | None = None
    dataset: ExperimentDataset
    factors: dict[str, list[str]]
    params: ExperimentParams = Field(default_factory=ExperimentParams)
    evaluation: ExperimentEvaluation = Field(default_factory=ExperimentEvaluation)
    trace: ExperimentTrace = Field(default_factory=ExperimentTrace)
    execution: ExperimentExecution = Field(default_factory=ExperimentExecution)

    def _validate_model(self) -> None:
        required = {"provider", "strategy", "format"}
        missing = [name for name in sorted(required) if name not in self.factors]
        if missing:
            raise ValueError(f"Experiment factors missing required keys: {', '.join(missing)}")
        empty = [name for name, values in self.factors.items() if not values]
        if empty:
            raise ValueError(f"Experiment factors must not be empty: {', '.join(sorted(empty))}")
        if self.execution.repeats < 1:
            raise ValueError("Experiment execution.repeats must be >= 1.")
        model_name = self.params.common.get("model_name")
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Experiment params.common.model_name must be a non-empty string.")


class RunSpec(BaseModel):
    id: str
    experimentId: str
    dataset: ExperimentDataset
    questionId: str
    contextId: str
    provider: str
    strategy: str
    format: str
    params: dict[str, Any] = Field(default_factory=dict)
    repeatIndex: int = 1
    outputRoot: str | None = None
    evaluationEnabled: bool = False
    trace: ExperimentTrace = Field(default_factory=ExperimentTrace)


class RunTiming(BaseModel):
    startedAt: str
    finishedAt: str
    durationMs: int


class RunTrace(BaseModel):
    aiTrace: dict[str, Any] = Field(default_factory=dict)
    toolCalls: list[dict[str, Any]] = Field(default_factory=list)
    rawResponse: Any | None = None
    error: str | None = None


class EvaluationResult(BaseModel):
    status: str = "not_evaluated"
    passed: bool | None = None
    expected: Any | None = None
    acceptedAnswers: list[Any] = Field(default_factory=list)
    reason: str | None = None
    evaluator: str | None = None


class RunResult(BaseModel):
    runId: str
    experimentId: str
    dataset: ExperimentDataset
    questionId: str
    contextId: str
    provider: str
    strategy: str
    format: str
    repeatIndex: int
    outputRoot: str | None = None
    answer: str
    status: str
    timing: RunTiming
    usage: dict[str, Any] = Field(default_factory=dict)
    trace: RunTrace = Field(default_factory=RunTrace)
    evaluation: EvaluationResult = Field(default_factory=EvaluationResult)
