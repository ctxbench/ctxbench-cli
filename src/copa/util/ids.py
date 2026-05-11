from __future__ import annotations

import re

from copa.util.artifacts import canonical_trial_identity


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "item"


def trialspec_id(
    experiment_id: str,
    task_id: str,
    context_id: str,
    provider: str,
    model_name: str,
    strategy: str,
    format_name: str,
    repetition: int,
) -> str:
    return canonical_trial_identity(
        experiment_id=experiment_id,
        task_id=task_id,
        instance_id=context_id,
        provider=provider,
        model_name=model_name,
        strategy=strategy,
        format_name=format_name,
        repetition=repetition,
    )


runspec_id = trialspec_id
