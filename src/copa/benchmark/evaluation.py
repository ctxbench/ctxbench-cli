from __future__ import annotations

from typing import Any

from copa.benchmark.models import EvaluationResult, RunResult
from copa.dataset.provider import DatasetProvider


def _normalize(value: Any) -> str:
    return " ".join(str(value).strip().lower().split())


def evaluate_result(result: RunResult, provider: DatasetProvider) -> EvaluationResult:
    instance = provider.get_question_instance(result.questionId, result.contextId)
    if instance is None:
        return EvaluationResult(
            status="not_evaluated",
            reason="No question instance metadata found.",
        )

    accepted = [instance.goldAnswer, *instance.acceptedAnswers]
    answer = _normalize(result.answer)
    accepted_normalized = [_normalize(item) for item in accepted]
    evaluation_type = instance.evaluationType

    if evaluation_type in {"exact_match", "accepted_answers", "semantic_match", "unanswerable"}:
        passed = any(
            candidate == answer or candidate in answer or answer in candidate
            for candidate in accepted_normalized
            if candidate
        )
        return EvaluationResult(
            status="evaluated",
            passed=passed,
            expected=instance.goldAnswer,
            acceptedAnswers=accepted,
            reason=None if passed else "Answer did not match accepted answers.",
            evaluator=evaluation_type,
        )

    return EvaluationResult(
        status="not_evaluated",
        reason=f"Unsupported evaluator: {evaluation_type}",
    )
