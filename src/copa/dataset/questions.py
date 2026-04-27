from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field, ValidationError


class QuestionValidation(BaseModel):
    type: str
    schemaDefinition: dict[str, Any] | None = None

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionValidation":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question validation requires an object input.")
        validation_type = str(data.get("type", "")).strip()
        if validation_type not in {"heuristic", "judge"}:
            raise ValidationError("Question validation.type must be 'heuristic' or 'judge'.")
        schema = data.get("schema")
        if schema is not None and not isinstance(schema, dict):
            raise ValidationError("Question validation.schema must be an object when provided.")
        return cls(type=validation_type, schemaDefinition=schema)

    @property
    def schema(self) -> dict[str, Any] | None:
        return self.schemaDefinition


class Question(BaseModel):
    id: str
    question: str
    tags: list[str] = Field(default_factory=list)
    validation: QuestionValidation

    @classmethod
    def model_validate(cls, data: Any) -> "Question":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question requires an object input.")
        return cls(
            id=str(data.get("id", "")).strip(),
            question=str(data.get("question", "")),
            tags=[str(item) for item in data.get("tags", []) if isinstance(item, str)],
            validation=QuestionValidation.model_validate(data.get("validation", {})),
        )


class QuestionDataset(BaseModel):
    datasetId: str = ""
    domain: str | None = None
    language: str | None = None
    version: str | None = None
    description: str | None = None
    questions: list[Question] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionDataset":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("QuestionDataset requires an object input.")
        return cls(
            datasetId=str(data.get("datasetId", "")),
            domain=data.get("domain"),
            language=data.get("language"),
            version=data.get("version"),
            description=data.get("description"),
            questions=[
                Question.model_validate(item)
                for item in data.get("questions", [])
                if isinstance(item, dict)
            ],
        )


class QuestionInstanceEntry(BaseModel):
    id: str
    acceptedAnswers: list[Any] = Field(default_factory=list)
    groundTruth: str | None = None
    contextRefs: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    templateParameters: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionInstanceEntry":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question instance question entry must be an object.")
        return cls(
            id=str(data.get("id", "")).strip(),
            acceptedAnswers=list(data.get("acceptedAnswers", []))
            if isinstance(data.get("acceptedAnswers", []), list)
            else [],
            groundTruth=str(data.get("ground_truth", "")).strip() or None,
            contextRefs=[str(item) for item in data.get("contextRefs", []) if isinstance(item, str)],
            themes=[str(item) for item in data.get("themes", []) if isinstance(item, str)],
            templateParameters={
                str(key): str(value)
                for key, value in data.get("template_parameters", {}).items()
                if isinstance(key, str)
            }
            if isinstance(data.get("template_parameters"), dict)
            else {},
        )


class QuestionInstance(BaseModel):
    instanceId: str
    contextBlocks: str
    questions: list[QuestionInstanceEntry] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionInstance":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("QuestionInstance requires an object input.")
        return cls(
            instanceId=str(data.get("instanceId", "")).strip(),
            contextBlocks=str(data.get("contextBlocks", "")).strip(),
            questions=[
                QuestionInstanceEntry.model_validate(item)
                for item in data.get("questions", [])
                if isinstance(item, dict)
            ],
        )

    def get_question(self, question_id: str) -> QuestionInstanceEntry | None:
        for item in self.questions:
            if item.id == question_id:
                return item
        return None


class QuestionInstanceDataset(BaseModel):
    datasetId: str = ""
    domain: str | None = None
    version: str | None = None
    instances: list[QuestionInstance] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionInstanceDataset":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("QuestionInstanceDataset requires an object input.")
        return cls(
            datasetId=str(data.get("datasetId", "")),
            domain=data.get("domain"),
            version=data.get("version"),
            instances=[
                QuestionInstance.model_validate(item)
                for item in data.get("instances", [])
                if isinstance(item, dict)
            ],
        )
