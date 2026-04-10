from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.ai.engine import Engine
from copa.benchmark.evaluation import (
    build_evaluation_summary,
    evaluate_run_results,
    evaluation_output_paths,
    load_experiment_for_evaluation,
    runspec_index_for_experiment,
    write_evaluation_files,
    write_evaluation_jsonl,
)
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.paths import resolve_run_jsonl_path, resolve_run_output_dir
from copa.benchmark.results import write_result_files, write_results_jsonl
from copa.util.artifacts import runresult_filename
from copa.util.fs import load_json, write_json
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def _read_runspec_payloads(path: str) -> list[dict[str, Any]]:
    source = Path(path)
    if source.is_dir():
        return [load_json(item) for item in sorted(source.glob("*.json")) if item.name != "runs.manifest.json"]
    if source.suffix == ".jsonl":
        return [dict(item) for item in read_jsonl(source)]
    return [load_json(source)]


def _find_runs_manifest(source: Path) -> Path | None:
    candidates: list[Path] = []
    if source.is_dir():
        candidates.append(source / "runs.manifest.json")
        candidates.append(source.parent / "runs.manifest.json")
    else:
        candidates.append(source.parent / "runs.manifest.json")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def load_runspecs(path: str) -> tuple[list[RunSpec], str | None]:
    source = Path(path)
    payloads = _read_runspec_payloads(path)
    if not payloads:
        return [], None
    if "dataset" in payloads[0]:
        runspecs = [RunSpec.model_validate(payload) for payload in payloads]
        experiment_path = runspecs[0].experimentPath if runspecs else None
        return runspecs, experiment_path

    manifest_path = _find_runs_manifest(source)
    if manifest_path is None:
        raise ValueError(
            "Minimal runspec artifacts require runs.manifest.json with an experimentPath."
        )
    manifest = load_json(manifest_path)
    experiment_path = str(manifest.get("experimentPath") or "")
    if not experiment_path:
        raise ValueError("runs.manifest.json must contain experimentPath.")
    experiment, base_dir = load_experiment_for_evaluation(experiment_path)
    runspecs_by_id = runspec_index_for_experiment(experiment, base_dir, experiment_path=experiment_path)
    runspecs: list[RunSpec] = []
    for payload in payloads:
        run_id = str(payload.get("runId") or "")
        if run_id not in runspecs_by_id:
            raise ValueError(f"Run '{run_id}' not found when regenerating runspecs from experiment.")
        runspecs.append(runspecs_by_id[run_id])
    return runspecs, experiment_path


def _artifact_root(target_dir: Path, target_jsonl: Path | None) -> Path:
    if target_jsonl is not None:
        return target_jsonl.parent
    return target_dir.parent


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
    runspecs, experiment_path = load_runspecs(path)
    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    logger.phase("LOAD", "Run specification loading completed", runs=len(runspecs))
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(runspecs))
    engine = Engine()
    progress_tracker.start()
    results = []
    try:
        for runspec in runspecs:
            model_name = runspec.modelName or ""
            logger.phase(
                "EXECUTE",
                "Starting answer generation",
                run=runspec.runId,
                model=model_name,
                question=runspec.questionId,
            )
            result = execute_runspec(runspec, engine)
            logger.phase(
                "EXECUTE",
                "Answer generation completed",
                run=runspec.runId,
                model=model_name,
                question=runspec.questionId,
            )
            results.append(result)
            progress_tracker.advance()
    finally:
        engine.close()

    if not results:
        print("No runspecs found.")
        return 0

    experiment = None
    base_dir = Path.cwd()
    if experiment_path:
        experiment, base_dir = load_experiment_for_evaluation(experiment_path)
    default_dir = resolve_run_output_dir(experiment, base_dir) if experiment is not None else Path.cwd() / "results"
    target_dir = Path(out_dir).resolve() if out_dir else default_dir
    target_jsonl = (
        Path(jsonl_path).resolve()
        if jsonl_path
        else (resolve_run_jsonl_path(experiment, base_dir) if experiment is not None else None)
    )
    artifact_root = _artifact_root(target_dir, target_jsonl)
    for result in results:
        logger.phase(
            "WRITE",
            "Writing artifact",
            run=result.runId,
            path=target_dir / runresult_filename(result.experimentId, result.runId),
        )
    result_paths = write_result_files(results, target_dir, artifact_root=artifact_root)
    for path_item, result in zip(result_paths, results):
        logger.phase("WRITE", "Artifact written", run=result.runId, path=path_item)
        logger.phase("DONE", "Completed successfully", run=result.runId)
    if target_jsonl is not None:
        write_results_jsonl(results, target_jsonl, artifact_root=artifact_root)
        print(f"Wrote {len(results)} result(s) to {target_dir} and {target_jsonl}")
    else:
        print(f"Wrote {len(results)} result(s) to {target_dir}")

    if experiment_path and runspecs[0].evaluationEnabled:
        logger.phase("EVALUATE", "Starting evaluation batch", experiment=experiment_path)
        experiment, base_dir = load_experiment_for_evaluation(experiment_path)
        evaluations = evaluate_run_results(results, experiment=experiment)
        eval_dir, eval_jsonl = evaluation_output_paths(experiment, base_dir)
        write_evaluation_files(evaluations, eval_dir)
        summary_path = eval_dir / "evaluation-summary.json"
        write_json(summary_path, build_evaluation_summary(evaluations).model_dump(mode="json"))
        if eval_jsonl is not None:
            write_evaluation_jsonl(evaluations, eval_jsonl)
        logger.phase("EVALUATE", "Evaluation completed", runs=len(evaluations), output=eval_dir)
    return 0
