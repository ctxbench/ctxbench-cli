from __future__ import annotations

import hashlib
import re
from typing import Protocol


class RunIdentity(Protocol):
    runId: str
    experimentId: str
    questionId: str
    contextId: str
    provider: str
    modelName: str | None
    strategy: str
    format: str
    repeatIndex: int


def sanitize_experiment_id(experiment_id: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", experiment_id).strip("_")
    return sanitized or "experiment"


def canonical_run_identity(
    experiment_id: str,
    question_id: str,
    instance_id: str,
    provider: str,
    model_name: str,
    strategy: str,
    format_name: str,
    repeat_index: int,
) -> str:
    return "|".join(
        [
            experiment_id or "",
            question_id or "",
            instance_id or "",
            provider or "",
            model_name or "",
            strategy or "",
            format_name or "",
            str(repeat_index),
        ]
    )


def canonical_identity_from_run(run: RunIdentity) -> str:
    return canonical_run_identity(
        experiment_id=run.experimentId,
        question_id=run.questionId,
        instance_id=run.contextId,
        provider=run.provider,
        model_name=run.modelName or "",
        strategy=run.strategy,
        format_name=run.format,
        repeat_index=run.repeatIndex,
    )


def build_short_ids(identities: list[str], min_length: int = 10) -> list[str]:
    if not identities:
        return []
    digests = [hashlib.sha256(identity.encode("utf-8")).hexdigest() for identity in identities]
    for length in range(min_length, len(digests[0]) + 1):
        short_ids = [digest[:length] for digest in digests]
        if len(short_ids) == len(set(short_ids)):
            return short_ids
    return digests


def run_id_from_identity(identity: str, min_length: int = 10) -> str:
    return build_short_ids([identity], min_length=min_length)[0]


def artifact_filename(prefix: str, experiment_id: str, run_id: str) -> str:
    return f"{prefix}_{sanitize_experiment_id(experiment_id)}_{run_id}.json"


def runspec_filename(experiment_id: str, run_id: str) -> str:
    return artifact_filename("rs", experiment_id, run_id)


def runresult_filename(experiment_id: str, run_id: str) -> str:
    return artifact_filename("rr", experiment_id, run_id)


def evalresult_filename(experiment_id: str, run_id: str) -> str:
    return artifact_filename("re", experiment_id, run_id)
