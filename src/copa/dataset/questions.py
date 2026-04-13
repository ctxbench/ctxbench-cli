from __future__ import annotations

from typing import Any
import warnings

from copa._compat import BaseModel, Field, ValidationError


class EvaluationRubricCriterion(BaseModel):
    id: str
    description: str
    weight: float = 1.0
    keywords: list[str] = Field(default_factory=list)


class QuestionEvaluation(BaseModel):
    mode: str
    answerType: str | None = None
    kind: str | None = None
    expected: Any | None = None
    rubric: list[EvaluationRubricCriterion] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionEvaluation":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question evaluation requires an object input.")
        return cls(
            mode=str(data.get("mode", "")),
            answerType=data.get("answerType"),
            kind=data.get("kind"),
            expected=data.get("expected"),
            rubric=[
                EvaluationRubricCriterion.model_validate(item)
                for item in data.get("rubric", [])
                if isinstance(item, dict)
            ],
        )


class Question(BaseModel):
    id: str
    question: str
    classification: str | None = None
    evaluationType: str = "exact_match"
    answerability: str | None = None
    expectedAnswerType: str | None = None
    evaluation: QuestionEvaluation | None = None

    @classmethod
    def model_validate(cls, data: Any) -> "Question":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Question requires an object input.")
        evaluation_payload = data.get("evaluation")
        if not isinstance(evaluation_payload, dict):
            warnings.warn(
                (
                    f"Question '{data.get('id', '')}' uses legacy evaluation metadata. "
                    "Prefer an explicit question.evaluation block."
                ),
                stacklevel=2,
            )
            evaluation_payload = {
                "mode": cls._legacy_mode(data),
                "answerType": data.get("expectedAnswerType"),
            }
        return cls(
            id=str(data.get("id", "")),
            question=str(data.get("question", "")),
            classification=data.get("classification"),
            evaluationType=str(data.get("evaluationType", "exact_match")),
            answerability=data.get("answerability"),
            expectedAnswerType=data.get("expectedAnswerType"),
            evaluation=QuestionEvaluation.model_validate(evaluation_payload),
        )

    @staticmethod
    def _legacy_mode(raw: dict[str, Any]) -> str:
        evaluation_type = str(raw.get("evaluationType", "")).strip().lower()
        classification = str(raw.get("classification", "")).strip().lower()
        answerability = str(raw.get("answerability", "")).strip().lower()
        if evaluation_type == "unanswerable" or answerability == "unanswerable":
            return "unanswerable"
        if evaluation_type in {"judge", "semantic_match"} or classification in {
            "analytical_interpretative",
            "retrieval_recommendation",
            "judgment_evaluation",
            "summarization",
        }:
            return "analytical"
        return "exact"


class QuestionDataset(BaseModel):
    datasetId: str
    domain: str | None = None
    language: str | None = None
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
            questions=[
                Question.model_validate(item)
                for item in data.get("questions", [])
                if isinstance(item, dict)
            ],
        )


class QuestionInstance(BaseModel):
    questionId: str
    cvId: str
    researcherName: str | None = None
    lattesId: str | None = None
    goldAnswer: Any | None = None
    acceptedAnswers: list[Any] = Field(default_factory=list)
    notes: str | None = None
    evaluationType: str = "exact_match"
    judgeReference: dict[str, Any] | None = None
    evaluationContext: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionInstanceDataset(BaseModel):
    datasetId: str
    domain: str | None = None
    instances: list[QuestionInstance] = Field(default_factory=list)
