from __future__ import annotations

from typing import Any

from copa._compat import BaseModel, Field


class Question(BaseModel):
    id: str
    question: str
    classification: str | None = None
    evaluationType: str = "exact_match"
    answerability: str | None = None
    expectedAnswerType: str | None = None


class QuestionDataset(BaseModel):
    datasetId: str
    domain: str | None = None
    language: str | None = None
    questions: list[Question] = Field(default_factory=list)


class QuestionInstance(BaseModel):
    questionId: str
    cvId: str
    researcherName: str | None = None
    lattesId: str | None = None
    goldAnswer: Any | None = None
    acceptedAnswers: list[Any] = Field(default_factory=list)
    notes: str | None = None
    evaluationType: str = "exact_match"


class QuestionInstanceDataset(BaseModel):
    datasetId: str
    domain: str | None = None
    instances: list[QuestionInstance] = Field(default_factory=list)
