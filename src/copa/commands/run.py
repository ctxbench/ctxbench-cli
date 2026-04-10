from __future__ import annotations

from pathlib import Path

from copa.ai.engine import Engine
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.results import write_result_files, write_results_jsonl
from copa.util.artifacts import build_short_ids, canonical_identity_from_run, runresult_filename
from copa.util.fs import load_json
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def load_runspecs(path: str) -> list[RunSpec]:
    source = Path(path)
    if source.is_dir():
        return [RunSpec.model_validate(load_json(item)) for item in sorted(source.glob("*.json"))]
    if source.suffix == ".jsonl":
        return [RunSpec.model_validate(item) for item in read_jsonl(source)]
    return [RunSpec.model_validate(load_json(source))]


def run_command(
    path: str,
    out_dir: str | None = None,
    jsonl_path: str | None = None,
    *,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    logger.phase("LOAD", "Loading run specification", path=path)
    runspecs = load_runspecs(path)
    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    logger.phase("LOAD", "Run specification loading completed", runs=len(runspecs))
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(runspecs))
    engine = Engine()
    short_ids = build_short_ids([canonical_identity_from_run(runspec) for runspec in runspecs])
    progress_tracker.start()
    results = []
    for runspec, short_id in zip(runspecs, short_ids):
        model_name = runspec.modelName or ""
        logger.phase(
            "EXECUTE",
            "Starting answer generation",
            run=short_id,
            model=model_name,
            question=runspec.questionId,
        )
        result = execute_runspec(runspec, engine)
        logger.phase(
            "EXECUTE",
            "Answer generation completed",
            run=short_id,
            model=model_name,
            question=runspec.questionId,
        )
        if result.evaluation.status == "evaluated":
            logger.phase(
                "EVALUATE",
                "Starting evaluation",
                run=short_id,
                question=result.questionId,
                evaluation=result.evaluation.evaluator or "unknown",
            )
            logger.phase(
                "EVALUATE",
                "Evaluation completed",
                run=short_id,
                question=result.questionId,
                evaluation=result.evaluation.evaluator or "unknown",
                score=result.evaluation.passed,
            )
        results.append(result)
        progress_tracker.advance()

    if results:
        output_root = (
            Path(results[0].outputRoot).resolve()
            if results[0].outputRoot
            else Path(results[0].dataset.contexts).resolve().parent.parent / "outputs"
        )
        default_dir = output_root / results[0].experimentId / "results"
        target_dir = Path(out_dir).resolve() if out_dir else default_dir
        for result, short_id in zip(results, short_ids):
            logger.phase(
                "WRITE",
                "Writing artifact",
                run=short_id,
                path=target_dir / runresult_filename(result.experimentId, short_id),
            )
        result_paths = write_result_files(results, target_dir, artifact_kind="result")
        for path_item, short_id in zip(result_paths, short_ids):
            logger.phase("WRITE", "Artifact written", run=short_id, path=path_item)
            logger.phase("DONE", "Completed successfully", run=short_id)
        if jsonl_path:
            write_results_jsonl(results, jsonl_path)
            print(f"Wrote {len(results)} result(s) to {target_dir} and {jsonl_path}")
        else:
            print(f"Wrote {len(results)} result(s) to {target_dir}")
    else:
        print("No runspecs found.")
    return 0
