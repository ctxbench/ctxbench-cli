from __future__ import annotations

from pathlib import Path

from copa.benchmark.models import Experiment


def _resolve_path(base_dir: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base_dir / path).resolve()


def resolve_output_root(experiment: Experiment, base_dir: Path) -> Path:
    return _resolve_path(base_dir, experiment.output) / experiment.id


def _resolve_artifact_path(output_root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (output_root / path).resolve()


def resolve_manifest_path(output_root: Path) -> Path:
    return output_root / "manifest.json"


def resolve_trials_path(experiment: Experiment, base_dir: Path) -> Path:
    output_root = resolve_output_root(experiment, base_dir)
    if experiment.expansion.jsonl:
        return _resolve_artifact_path(output_root, experiment.expansion.jsonl)
    return output_root / "trials.jsonl"


def resolve_responses_path(experiment: Experiment, base_dir: Path) -> Path:
    output_root = resolve_output_root(experiment, base_dir)
    if experiment.execution.jsonl:
        return _resolve_artifact_path(output_root, experiment.execution.jsonl)
    return output_root / "responses.jsonl"


def resolve_evals_path(experiment: Experiment, base_dir: Path) -> Path:
    output_root = resolve_output_root(experiment, base_dir)
    if experiment.evaluation.jsonl:
        return _resolve_artifact_path(output_root, experiment.evaluation.jsonl)
    return output_root / "evals.jsonl"


# Aliases kept for any remaining internal references
def resolve_expand_output_dir(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_output_root(experiment, base_dir)


def resolve_expand_jsonl_path(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_trials_path(experiment, base_dir)


def resolve_run_output_dir(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_output_root(experiment, base_dir)


def resolve_run_jsonl_path(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_responses_path(experiment, base_dir)


def resolve_eval_output_dir(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_output_root(experiment, base_dir)


def resolve_eval_jsonl_path(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_evals_path(experiment, base_dir)


# Aliases kept for any remaining internal references
def resolve_queries_path(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_trials_path(experiment, base_dir)


def resolve_answers_path(experiment: Experiment, base_dir: Path) -> Path:
    return resolve_responses_path(experiment, base_dir)
