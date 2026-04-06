from __future__ import annotations

import re


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return normalized or "item"


def runspec_id(
    experiment_id: str,
    question_id: str,
    context_id: str,
    model: str,
    strategy: str,
    format_name: str,
    repeat_index: int,
) -> str:
    return "_".join(
        [
            "run",
            slugify(experiment_id),
            slugify(question_id),
            slugify(context_id),
            slugify(model),
            slugify(strategy),
            slugify(format_name),
            f"r{repeat_index}",
        ]
    )
