from __future__ import annotations

from pathlib import Path

from ctxbench.benchmark.experiment_loader import load_experiment
from ctxbench.benchmark.paths import resolve_output_root, resolve_trials_path
from ctxbench.benchmark.runspec_generator import generate_runspecs
from ctxbench.dataset.provider import DatasetProvider
from ctxbench.util.fs import ensure_dir, write_json
from ctxbench.util.jsonl import write_jsonl
from ctxbench.util.logging import PhaseLogger, ProgressTracker


def plan_command(
    path: str,
    output: str | None = None,
    *,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    logger.phase("LOAD", "Loading experiment", path=path)
    experiment = load_experiment(path)
    base_dir = Path(path).resolve().parent
    provider = DatasetProvider.from_experiment(experiment, base_dir)
    logger.phase(
        "LOAD",
        "Dataset loaded",
        questions=len(provider.list_question_ids()),
        instances=len(provider.list_instance_ids()),
    )
    runspecs = generate_runspecs(
        experiment,
        base_dir,
        experiment_path=path,
        on_warning=lambda message, **fields: logger.warn(message, **fields),
    )
    logger.phase("PLAN", "Expanding trials", input=path, total=len(runspecs))

    output_root = Path(output).resolve() if output else resolve_output_root(experiment, base_dir)
    trials_path = resolve_trials_path(experiment, base_dir) if not output else output_root / "trials.jsonl"
    manifest_path = output_root / "manifest.json"

    ensure_dir(output_root)

    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()

    payloads = []
    for runspec in runspecs:
        payloads.append(runspec.to_persisted_artifact())
        logger.phase("PLAN", "Trial prepared", run=runspec.runId)
        progress_tracker.advance()

    write_jsonl(trials_path, payloads)
    logger.phase("WRITE", "Trials written", path=str(trials_path), total=len(payloads))

    manifest = {
        "experimentId": experiment.id,
        "experimentPath": str(Path(path).resolve()),
        "evaluation": {
            "enabled": experiment.evaluation.enabled,
            "judges": [item.model_dump(mode="json") for item in experiment.evaluation.judges],
        },
        "trace": experiment.trace.model_dump(mode="json"),
        "artifacts": experiment.artifacts.model_dump(mode="json"),
    }
    write_json(manifest_path, manifest)
    logger.phase("WRITE", "Manifest written", path=str(manifest_path))

    print(f"Planned {len(runspecs)} trials → {trials_path}")
    return 0
