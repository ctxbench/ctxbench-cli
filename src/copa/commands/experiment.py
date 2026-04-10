from __future__ import annotations

from pathlib import Path

from copa.benchmark.experiment_loader import load_experiment
from copa.benchmark.runspec_generator import generate_runspecs
from copa.dataset.provider import DatasetProvider
from copa.util.artifacts import build_short_ids, canonical_identity_from_run, runspec_filename
from copa.util.fs import ensure_dir, write_json
from copa.util.jsonl import write_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


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
        instances=len(provider._question_instances.instances),
    )
    runspecs = generate_runspecs(experiment, base_dir)
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(runspecs))
    payloads = [runspec.model_dump(mode="json") for runspec in runspecs]
    identities = [canonical_identity_from_run(runspec) for runspec in runspecs]
    short_ids = build_short_ids(identities)

    output_root = Path(experiment.execution.output)
    default_dir = (base_dir / output_root / experiment.id / "runspecs").resolve()
    target_dir = Path(out_dir).resolve() if out_dir else default_dir
    ensure_dir(target_dir)
    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()

    for runspec, short_id in zip(runspecs, short_ids):
        artifact_path = target_dir / runspec_filename(runspec.experimentId, short_id)
        logger.phase("WRITE", "Writing artifact", run=short_id, path=artifact_path)
        write_json(artifact_path, runspec.model_dump(mode="json"))
        logger.phase("WRITE", "Artifact written", run=short_id, path=artifact_path)
        logger.phase("DONE", "Completed successfully", run=short_id)
        progress_tracker.advance()

    if jsonl_path:
        write_jsonl(jsonl_path, payloads)
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir} and {jsonl_path}")
    else:
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir}")
    return 0
