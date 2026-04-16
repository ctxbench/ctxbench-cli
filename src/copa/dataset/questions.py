from __future__ import annotations

from typing import Any
import warnings

from copa._compat import BaseModel, Field, ValidationError


class EvaluationRubricCriterion(BaseModel):
    id: str
    description: str
    weight: float = 1.0
    keywords: list[str] = Field(default_factory=list)


class EvaluationDimensionCatalogEntry(BaseModel):
    description: str | None = None
    defaultScale: list[str] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "EvaluationDimensionCatalogEntry":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Evaluation dimension catalog entry requires an object input.")
        return cls(
            description=data.get("description"),
            defaultScale=[str(item) for item in data.get("defaultScale", [])],
        )


class EvaluationDimension(BaseModel):
    id: str
    weight: float = 1.0
    description: str | None = None
    defaultScale: list[str] = Field(default_factory=list)
    normalization: list[str] = Field(default_factory=list)
    criteria: list[str] = Field(default_factory=list)
    judgingNotes: list[str] = Field(default_factory=list)
    requiredFields: list[str] = Field(default_factory=list)
    basedOn: str | None = None
    minRelevantThemesForPresent: int | None = None

    @classmethod
    def model_validate(
        cls,
        data: Any,
        catalog_entry: EvaluationDimensionCatalogEntry | None = None,
    ) -> "EvaluationDimension":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("Evaluation dimension requires an object input.")
        return cls(
            id=str(data.get("id", "")),
            weight=float(data.get("weight", 1.0)),
            description=(
                data.get("description")
                if data.get("description") is not None
                else catalog_entry.description if catalog_entry is not None else None
            ),
            defaultScale=(
                [str(item) for item in data.get("defaultScale", [])]
                if data.get("defaultScale") is not None
                else list(catalog_entry.defaultScale) if catalog_entry is not None else []
            ),
            normalization=[str(item) for item in data.get("normalization", [])],
            criteria=[str(item) for item in data.get("criteria", [])],
            judgingNotes=[str(item) for item in data.get("judgingNotes", [])],
            requiredFields=[str(item) for item in data.get("requiredFields", [])],
            basedOn=str(data["basedOn"]) if data.get("basedOn") is not None else None,
            minRelevantThemesForPresent=(
                int(data["minRelevantThemesForPresent"])
                if data.get("minRelevantThemesForPresent") is not None
                else None
            ),
        )


class QuestionEvaluation(BaseModel):
    mode: str
    answerType: str | None = None
    kind: str | None = None
    expected: Any | None = None
    rubric: list[EvaluationRubricCriterion] = Field(default_factory=list)
    dimensions: list[EvaluationDimension] = Field(default_factory=list)

    @classmethod
    def model_validate(
        cls,
        data: Any,
        dimensions_catalog: dict[str, EvaluationDimensionCatalogEntry] | None = None,
    ) -> "QuestionEvaluation":
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
            dimensions=[
                EvaluationDimension.model_validate(
                    item,
                    dimensions_catalog.get(str(item.get("id", ""))) if dimensions_catalog else None,
                )
                for item in data.get("dimensions", [])
                if isinstance(item, dict)
            ],
        )


class Question(BaseModel):
    id: str
    question: str
    questionType: str | None = None
    cognitiveType: str | None = None
    difficulty: str | None = None
    classification: str | None = None
    evaluationType: str = "exact_match"
    answerability: str | None = None
    expectedAnswerType: str | None = None
    evaluation: QuestionEvaluation | None = None

    @classmethod
    def model_validate(
        cls,
        data: Any,
        dimensions_catalog: dict[str, EvaluationDimensionCatalogEntry] | None = None,
    ) -> "Question":
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
            questionType=data.get("questionType"),
            cognitiveType=data.get("cognitiveType"),
            difficulty=data.get("difficulty"),
            classification=data.get("classification"),
            evaluationType=str(data.get("evaluationType", "exact_match")),
            answerability=data.get("answerability"),
            expectedAnswerType=data.get("expectedAnswerType"),
            evaluation=QuestionEvaluation.model_validate(evaluation_payload, dimensions_catalog),
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
    version: str | None = None
    description: str | None = None
    dimensionsCatalog: dict[str, EvaluationDimensionCatalogEntry] = Field(default_factory=dict)
    questions: list[Question] = Field(default_factory=list)

    @classmethod
    def model_validate(cls, data: Any) -> "QuestionDataset":
        if isinstance(data, cls):
            return data
        if not isinstance(data, dict):
            raise ValidationError("QuestionDataset requires an object input.")
        raw_catalog = data.get("dimensionsCatalog", {})
        dimensions_catalog = {
            str(key): EvaluationDimensionCatalogEntry.model_validate(value)
            for key, value in raw_catalog.items()
            if isinstance(key, str) and isinstance(value, dict)
        } if isinstance(raw_catalog, dict) else {}
        return cls(
            datasetId=str(data.get("datasetId", "")),
            domain=data.get("domain"),
            language=data.get("language"),
            version=data.get("version"),
            description=data.get("description"),
            dimensionsCatalog=dimensions_catalog,
            questions=[
                Question.model_validate(item, dimensions_catalog)
                for item in data.get("questions", [])
                if isinstance(item, dict)
            ],
        )


class QuestionInstance(BaseModel):
    questionId: str
    instanceId: str | None = None
    cvId: str
    researcherName: str | None = None
    lattesId: str | None = None
    goldAnswer: Any | None = None
    acceptedAnswers: list[Any] = Field(default_factory=list)
    notes: str | None = None
    evaluationType: str = "exact_match"
    judgeReference: dict[str, Any] | None = None
    evaluationContext: dict[str, Any] | None = None
    evaluationContextByDimension: dict[str, dict[str, Any]] = Field(default_factory=dict)
    normalizationHints: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionInstanceDataset(BaseModel):
    datasetId: str
    domain: str | None = None
    version: str | None = None
    instances: list[QuestionInstance] = Field(default_factory=list)
