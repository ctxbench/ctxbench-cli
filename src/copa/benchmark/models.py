from __future__ import annotations

from pathlib import Path
from typing import Any

from copa._compat import BaseModel, Field, ValidationError


def _model_dump_value(value: Any, mode: str) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode=mode)
    if isinstance(value, list):
        return [_model_dump_value(item, mode) for item in value]
    if isinstance(value, dict):
        return {key: _model_dump_value(item, mode) for key, item in value.items()}
    return value


class ExperimentDataset(BaseModel):
    root: str

    @classmethod
    def model_validate(cls, data: Any) -> "ExperimentDataset":
        if isinstance(data, cls):
            return data
        if isinstance(data, str):
            return cls(root=data)
        if isinstance(data, dict):
            if "root" in data:
                return cls(root=str(data["root"]))
            legacy_paths = {"questions", "contexts", "question_instances"}
            if legacy_paths & set(data):
                raise ValidationError(
                    "Experiment dataset must be a dataset directory path. "
                    "Put questions.json and questions.instance.json in the dataset root "
                    "and context files in <dataset>/context."
                )
        raise ValidationError("ExperimentDataset requires a dataset directory path.")

    @property
    def questions(self) -> str:
        return str(Path(self.root) / "questions.json")

    @property
    def contexts(self) -> str:
        return str(Path(self.root) / "context")

    @property
    def question_instances(self) -> str:
        return str(Path(self.root) / "questions.instance.json")


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
        payload = {"common": _model_dump_value(self.common, mode)}
        for model_name, params in self.models.items():
            payload[model_name] = _model_dump_value(params, mode)
        return payload


class ExperimentExecution(BaseModel):
    repeats: int = 1
    output: str | None = None
    jsonl: str | None = None


class ExperimentExpansion(BaseModel):
    output: str | None = None
    jsonl: str | None = None


class EvaluationModelConfig(BaseModel):
    provider: str
    model: str
    temperature: float | int | None = None
    params: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, data: Any) -> "EvaluationModelConfig":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Evaluation model config requires an object input.")
        params = {
            key: value
            for key, value in data.items()
            if key not in {"provider", "model", "temperature"}
        }
        return cls(
            provider=str(data.get("provider", "")),
            model=str(data.get("model", "")),
            temperature=data.get("temperature"),
            params=params,
        )


class ExperimentEvaluation(BaseModel):
    enabled: bool = False
    output: str | None = None
    jsonl: str | None = None
    judge: EvaluationModelConfig | None = None
    fallback: EvaluationModelConfig | None = None
    config: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, data: Any) -> "ExperimentEvaluation":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("ExperimentEvaluation requires an object input.")
        config = {
            key: value
            for key, value in data.items()
            if key not in {"enabled", "output", "jsonl", "judge", "fallback"}
        }
        return cls(
            enabled=bool(data.get("enabled", False)),
            output=data.get("output"),
            jsonl=data.get("jsonl"),
            judge=EvaluationModelConfig.model_validate(data["judge"])
            if isinstance(data.get("judge"), dict)
            else None,
            fallback=EvaluationModelConfig.model_validate(data["fallback"])
            if isinstance(data.get("fallback"), dict)
            else None,
            config=config,
        )


class ExperimentTrace(BaseModel):
    enabled: bool = False
    save_raw_response: bool = False
    save_tool_calls: bool = False
    save_usage: bool = False
    save_errors: bool = False


class Experiment(BaseModel):
    id: str
    name: str | None = None
    output: str = "outputs"
    dataset: ExperimentDataset
    factors: dict[str, list[Any]]
    params: ExperimentParams = Field(default_factory=ExperimentParams)
    expansion: ExperimentExpansion = Field(default_factory=ExperimentExpansion)
    evaluation: ExperimentEvaluation = Field(default_factory=ExperimentEvaluation)
    trace: ExperimentTrace = Field(default_factory=ExperimentTrace)
    execution: ExperimentExecution = Field(default_factory=ExperimentExecution)

    @classmethod
    def model_validate(cls, data: Any) -> "Experiment":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Experiment requires an object input.")
        payload = dict(data)
        if "dataset" in payload:
            payload["dataset"] = ExperimentDataset.model_validate(payload["dataset"])
        if "params" in payload:
            payload["params"] = ExperimentParams.model_validate(payload["params"])
        if "expansion" in payload and isinstance(payload["expansion"], dict):
            payload["expansion"] = ExperimentExpansion.model_validate(payload["expansion"])
        if "evaluation" in payload and isinstance(payload["evaluation"], dict):
            payload["evaluation"] = ExperimentEvaluation.model_validate(payload["evaluation"])
        if "trace" in payload and isinstance(payload["trace"], dict):
            payload["trace"] = ExperimentTrace.model_validate(payload["trace"])
        if "execution" in payload and isinstance(payload["execution"], dict):
            payload["execution"] = ExperimentExecution.model_validate(payload["execution"])
        execution = payload.get("execution")
        execution_output = execution.output if isinstance(execution, ExperimentExecution) else execution.get("output") if isinstance(execution, dict) else None
        if not payload.get("output") and execution_output:
            payload["output"] = execution_output
        return super().model_validate(payload)

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


class RunMetadata(BaseModel):
    canonicalId: str
    questionId: str
    contextId: str
    provider: str
    modelName: str | None = None
    strategy: str
    format: str
    repeatIndex: int


class RunSpec(BaseModel):
    id: str
    runId: str
    experimentId: str
    dataset: ExperimentDataset
    experimentPath: str | None = None
    questionId: str
    contextId: str
    provider: str
    modelName: str | None = None
    strategy: str
    format: str
    params: dict[str, Any] = Field(default_factory=dict)
    repeatIndex: int = 1
    outputRoot: str | None = None
    evaluationEnabled: bool = False
    trace: ExperimentTrace = Field(default_factory=ExperimentTrace)
    metadata: RunMetadata

    @classmethod
    def model_validate(cls, data: Any) -> "RunSpec":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("RunSpec requires an object input.")
        payload = dict(data)
        if "modelName" not in payload and "model" in payload:
            payload["modelName"] = payload.get("model")
        original_id = str(payload.get("id") or "")
        run_id = str(payload.get("runId") or payload.get("id") or "")
        payload["runId"] = run_id
        payload["id"] = run_id
        if "metadata" not in payload:
            payload["metadata"] = {
                "canonicalId": original_id or run_id,
                "questionId": payload.get("questionId", ""),
                "contextId": payload.get("contextId", ""),
                "provider": payload.get("provider", ""),
                "modelName": payload.get("modelName"),
                "strategy": payload.get("strategy", ""),
                "format": payload.get("format", ""),
                "repeatIndex": payload.get("repeatIndex", 1),
            }
        return super().model_validate(payload)

    def to_persisted_artifact(self) -> dict[str, Any]:
        return {
            "runId": self.runId,
            "experimentId": self.experimentId,
            "questionId": self.questionId,
            "contextId": self.contextId,
            "model": self.modelName,
            "provider": self.provider,
            "strategy": self.strategy,
            "format": self.format,
            "repeatIndex": self.repeatIndex,
        }


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
    modelName: str | None = None
    strategy: str
    format: str
    repeatIndex: int
    outputRoot: str | None = None
    answer: str
    status: str
    errorMessage: str | None = None
    timing: RunTiming
    usage: dict[str, Any] = Field(default_factory=dict)
    trace: RunTrace = Field(default_factory=RunTrace)
    traceRef: str | None = None
    evaluation: EvaluationResult = Field(default_factory=EvaluationResult)
    metadata: RunMetadata

    @classmethod
    def model_validate(cls, data: Any) -> "RunResult":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("RunResult requires an object input.")
        payload = dict(data)
        if "modelName" not in payload and "model" in payload:
            payload["modelName"] = payload.get("model")
        original_id = str(payload.get("id") or "")
        run_id = str(payload.get("runId") or payload.get("id") or "")
        payload["runId"] = run_id
        if "metadata" not in payload:
            payload["metadata"] = {
                "canonicalId": original_id or run_id,
                "questionId": payload.get("questionId", ""),
                "contextId": payload.get("contextId", ""),
                "provider": payload.get("provider", ""),
                "modelName": payload.get("modelName"),
                "strategy": payload.get("strategy", ""),
                "format": payload.get("format", ""),
                "repeatIndex": payload.get("repeatIndex", 1),
            }
        return super().model_validate(payload)

    def to_persisted_artifact(self, *, trace_ref: str | None = None) -> dict[str, Any]:
        return {
            "runId": self.runId,
            "status": self.status,
            "answer": self.answer,
            "errorMessage": self.errorMessage,
            "timing": self.timing.model_dump(mode="json"),
            "usage": self.usage,
            "traceRef": trace_ref,
        }


class EvaluationTrace(BaseModel):
    aiTrace: dict[str, Any] = Field(default_factory=dict)
    rawResponse: Any | None = None
    error: str | None = None


class EvaluationJudgeInfo(BaseModel):
    used: bool = False
    role: str | None = None
    provider: str | None = None
    model: str | None = None
    inputTokens: int | None = None
    outputTokens: int | None = None
    durationMs: int | None = None
    fallbackUsed: bool = False


class EvaluationItemResult(BaseModel):
    experimentId: str
    runId: str
    questionId: str
    question: str
    evaluationMode: str
    status: str = "evaluated"
    evaluationMethod: str | None = None
    score: float | None = None
    label: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    executionModel: str | None = None
    executionStrategy: str | None = None
    executionFormat: str | None = None
    executionInputTokens: int | None = None
    executionOutputTokens: int | None = None
    executionDurationMs: int | None = None
    executionToolCalls: int | None = None
    evaluationJudgeUsed: bool = False
    evaluationJudgeRole: str | None = None
    evaluationJudgeProvider: str | None = None
    evaluationJudgeModel: str | None = None
    evaluationInputTokens: int | None = None
    evaluationOutputTokens: int | None = None
    evaluationDurationMs: int | None = None
    evaluationTrace: EvaluationTrace = Field(default_factory=EvaluationTrace)

    def to_persisted_artifact(self) -> dict[str, Any]:
        return {
            "experimentId": self.experimentId,
            "runId": self.runId,
            "questionId": self.questionId,
            "status": self.status,
            "evaluationMethod": self.evaluationMethod,
            "score": self.score,
            "label": self.label,
            "details": self.details,
        }


class EvaluationRunSummary(BaseModel):
    itemCount: int = 0
    meanScore: float | None = 0.0
    labels: dict[str, int] = Field(default_factory=dict)


class EvaluationRunResult(BaseModel):
    experimentId: str
    runId: str
    questionId: str
    items: list[EvaluationItemResult] = Field(default_factory=list)
    summary: EvaluationRunSummary = Field(default_factory=EvaluationRunSummary)
    metadata: RunMetadata

    @classmethod
    def model_validate(cls, data: Any) -> "EvaluationRunResult":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("EvaluationRunResult requires an object input.")
        payload = dict(data)
        if "metadata" not in payload:
            payload["metadata"] = {
                "canonicalId": str(payload.get("runId", "")),
                "questionId": payload.get("questionId", ""),
                "contextId": "",
                "provider": "",
                "modelName": None,
                "strategy": "",
                "format": "",
                "repeatIndex": 1,
            }
        return super().model_validate(payload)


class EvaluationBatchSummary(BaseModel):
    experimentId: str
    runCount: int = 0
    itemCount: int = 0
    meanScore: float | None = 0.0
    labels: dict[str, int] = Field(default_factory=dict)
