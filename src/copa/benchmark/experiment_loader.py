from __future__ import annotations

from pathlib import Path

from copa._compat import ValidationError
from copa.benchmark.models import Experiment
from copa.util.fs import load_json


def load_experiment(path: str | Path) -> Experiment:
    try:
        experiment = Experiment.model_validate(load_json(path))
        validator = getattr(experiment, "_validate_model", None)
        if validator:
            validator()
        return experiment
    except (ValidationError, ValueError) as exc:
        raise ValueError(f"Invalid experiment at {path}: {exc}") from exc
