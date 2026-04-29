from __future__ import annotations

from pathlib import Path

from copa.benchmark.experiment_loader import load_experiment
from copa.benchmark.paths import resolve_expand_jsonl_path, resolve_expand_output_dir
from copa.benchmark.runspec_generator import generate_runspecs
from copa.dataset.provider import DatasetProvider
from copa.util.artifacts import runspec_filename
from copa.util.fs import ensure_dir, write_json
from copa.util.jsonl import write_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def _runs_manifest_targets(target_dir: Path, target_jsonl: Path | None) -> list[Path]:
    candidates = {target_dir / "runs.manifest.json"}
    if target_jsonl is not None:
        candidates.add(target_jsonl.parent / "runs.manifest.json")
    return sorted(candidates)


def _evaluation_manifest_targets(target_dir: Path, target_jsonl: Path | None) -> list[Path]:
    candidates = {target_dir.parent / "evaluation.manifest.json"}
    if target_jsonl is not None:
        candidates.add(target_jsonl.parent / "evaluation.manifest.json")
    return sorted(candidates)


def validate_experiment(path: str) -> int:
    load_experiment(path)
    print(f"{path}: valid experiment")
    return 0


def expand_experiment(
    path: str,
    out_dir: str | None = None,
    jsonl_path: str | None = None,
    *,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    progress_tracker = ProgressTracker(total=0, enabled=False)
    logger = PhaseLogger(verbose=verbose, progress=progress_tracker)
    logger.phase("LOAD", "Loading experiment", path=path)
    experiment = load_experiment(path)
    base_dir = Path(path).resolve().parent
    provider = DatasetProvider.from_experiment(experiment, base_dir)
    logger.phase(
        "LOAD",
        "Dataset loading completed",
        questions=len(provider.list_question_ids()),
        instances=len(provider.list_instance_ids()),
    )
    runspecs = generate_runspecs(
        experiment,
        base_dir,
        experiment_path=path,
        on_warning=lambda message, **fields: logger.warn(message, **fields),
    )
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(runspecs))
    payloads = [runspec.to_persisted_artifact() for runspec in runspecs]
    default_dir = resolve_expand_output_dir(experiment, base_dir)
    target_dir = Path(out_dir).resolve() if out_dir else default_dir
    target_jsonl = Path(jsonl_path).resolve() if jsonl_path else resolve_expand_jsonl_path(experiment, base_dir)
    ensure_dir(target_dir)
    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()

    for runspec in runspecs:
        artifact_path = target_dir / runspec_filename(runspec.experimentId, runspec.runId)
        logger.phase("WRITE", "Writing artifact", run=runspec.runId, path=artifact_path)
        write_json(artifact_path, runspec.to_persisted_artifact())
        logger.phase("WRITE", "Artifact written", run=runspec.runId, path=artifact_path)
        logger.phase("DONE", "Completed successfully", run=runspec.runId)
        progress_tracker.advance()

    if target_jsonl is not None:
        write_jsonl(target_jsonl, payloads)
    runs_manifest_payload = {
        "experimentId": experiment.id,
        "experimentPath": str(Path(path).resolve()),
    }
    evaluation_manifest_payload = {
        "experimentId": experiment.id,
        "evaluation": {
            "enabled": experiment.evaluation.enabled,
            "output": experiment.evaluation.output or "evaluation",
            "jsonl": experiment.evaluation.jsonl or "evaluation.jsonl",
            "judges": [
                item.model_dump(mode="json")
                for item in experiment.evaluation.judges
            ],
        },
    }
    for manifest_path in _runs_manifest_targets(target_dir, target_jsonl):
        write_json(manifest_path, runs_manifest_payload)
        logger.phase("WRITE", "Artifact written", path=manifest_path)
    for manifest_path in _evaluation_manifest_targets(target_dir, target_jsonl):
        write_json(manifest_path, evaluation_manifest_payload)
        logger.phase("WRITE", "Artifact written", path=manifest_path)

    if target_jsonl is not None:
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir} and {target_jsonl}")
    else:
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir}")
    return 0
