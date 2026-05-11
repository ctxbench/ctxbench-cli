from __future__ import annotations

from pathlib import Path

from ctxbench._compat import ValidationError
from ctxbench.benchmark.models import Experiment
from ctxbench.util.fs import load_json


def load_experiment(path: str | Path) -> Experiment:
    try:
        experiment = Experiment.model_validate(load_json(path))
        validator = getattr(experiment, "_validate_model", None)
        if validator:
            validator()
        return experiment
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"Invalid experiment at {path}: {exc}") from exc
