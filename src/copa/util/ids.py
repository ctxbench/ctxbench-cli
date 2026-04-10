from __future__ import annotations

import re

from copa.util.artifacts import canonical_run_identity


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "item"


def runspec_id(
    experiment_id: str,
    question_id: str,
    context_id: str,
    provider: str,
    model_name: str,
    strategy: str,
    format_name: str,
    repeat_index: int,
) -> str:
    return canonical_run_identity(
        experiment_id=experiment_id,
        question_id=question_id,
        instance_id=context_id,
        provider=provider,
        model_name=model_name,
        strategy=strategy,
        format_name=format_name,
        repeat_index=repeat_index,
    )
