from __future__ import annotations

from typing import Any

from ctxbench._compat import BaseModel, Field, ValidationError


class QuestionValidation(BaseModel):
    type: str

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionValidation":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question validation requires an object input.")
        validation_type = str(data.get("type", "")).strip()
        if validation_type != "judge":
            raise ValidationError("Question validation.type must be 'judge'.")
        return cls(type=validation_type)


class Question(BaseModel):
    id: str
    question: str
    tags: list[str] = Field(default_factory=list)
    validation: QuestionValidation
    contextBlock: list[str] = Field(default_factory=list)

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
            contextBlock=[str(item) for item in data.get("contextBlock", []) if isinstance(item, str)],
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
    parameters: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionInstanceEntry":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question instance question entry must be an object.")
        return cls(
            id=str(data.get("id", "")).strip(),
            parameters={
                str(key): value
                for key, value in data.get("parameters", {}).items()
                if isinstance(key, str)
            }
            if isinstance(data.get("parameters"), dict)
            else {},
        )


class QuestionInstance(BaseModel):
    instanceId: str
    contextBlocks: str = ""
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
