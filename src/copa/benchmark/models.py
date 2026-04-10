from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field, ValidationError


class ExperimentDataset(BaseModel):
    questions: str
    contexts: str
    question_instances: str | None = None


class ExperimentParams(BaseModel):
    common: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, data: Any) -> "ExperimentParams":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("ExperimentParams requires an object input.")
        common = data.get("common", {})
        if not isinstance(common, dict):
            raise ValidationError("Experiment params.common must be an object.")
        models = {key: value for key, value in data.items() if key != "common"}
        for model_name, params in models.items():
            if not isinstance(params, dict):
                raise ValidationError(f"Experiment params.{model_name} must be an object.")
        return cls(common=common, models=models)

    def model_dump(self, mode: str = "python") -> dict[str, Any]:
        payload = {"common": self._dump(self.common, mode)}
        for model_name, params in self.models.items():
            payload[model_name] = self._dump(params, mode)
        return payload


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
    factors: dict[str, list[Any]]
    params: ExperimentParams = Field(default_factory=ExperimentParams)
    evaluation: ExperimentEvaluation = Field(default_factory=ExperimentEvaluation)
    trace: ExperimentTrace = Field(default_factory=ExperimentTrace)
    execution: ExperimentExecution = Field(default_factory=ExperimentExecution)

    def _validate_model(self) -> None:
        required = {"model", "strategy", "format"}
        missing = [name for name in sorted(required) if name not in self.factors]
        if missing:
            raise ValueError(f"Experiment factors missing required keys: {', '.join(missing)}")
        empty = [name for name, values in self.factors.items() if not values]
        if empty:
            raise ValueError(f"Experiment factors must not be empty: {', '.join(sorted(empty))}")
        if self.execution.repeats < 1:
            raise ValueError("Experiment execution.repeats must be >= 1.")
        for model in self.factors.get("model", []):
            if not isinstance(model, dict):
                raise ValueError("Experiment factors.model entries must be objects.")
            provider = model.get("provider")
            name = model.get("name")
            if not isinstance(provider, str) or not provider.strip():
                raise ValueError("Experiment factors.model[].provider must be a non-empty string.")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Experiment factors.model[].name must be a non-empty string.")
        for factor_name in ("strategy", "format"):
            invalid = [value for value in self.factors.get(factor_name, []) if not isinstance(value, str) or not value.strip()]
            if invalid:
                raise ValueError(f"Experiment factors.{factor_name} entries must be non-empty strings.")


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
