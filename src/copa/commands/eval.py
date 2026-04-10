from __future__ import annotations

from pathlib import Path

from copa.benchmark.evaluation import (
    build_evaluation_summary,
    evaluate_run_results,
    evaluation_output_paths,
    load_experiment_for_evaluation,
    write_evaluation_files,
    write_evaluation_jsonl,
)
from copa.benchmark.models import RunResult
from copa.util.fs import load_json, write_json
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def load_results_from_input(
    *,
    run_results_dir: str | None = None,
    run_results_json: str | None = None,
) -> list[RunResult]:
    if bool(run_results_dir) == bool(run_results_json):
        raise ValueError("Provide exactly one of --run-results-dir or --run-results-json.")
    if run_results_dir:
        source = Path(run_results_dir)
        return [RunResult.model_validate(load_json(item)) for item in sorted(source.glob("*.json"))]
    source = Path(run_results_json or "")
    if source.suffix == ".jsonl":
        return [RunResult.model_validate(item) for item in read_jsonl(source)]
    return [RunResult.model_validate(load_json(source))]


def eval_command(
    *,
    run_results_dir: str | None,
    run_results_json: str | None,
    experiment_path: str,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
    only: str | None = None,
    mode: str | None = None,
    continue_on_error: bool = False,
    fail_on_missing_gold: bool = False,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    logger.phase("LOAD", "Loading experiment", path=experiment_path)
    experiment, base_dir = load_experiment_for_evaluation(experiment_path)
    input_path = run_results_dir or run_results_json or ""
    logger.phase("LOAD", "Loading run results", path=input_path)
    results = load_results_from_input(
        run_results_dir=run_results_dir,
        run_results_json=run_results_json,
    )
    progress_tracker = ProgressTracker(total=len(results), enabled=progress)
    logger.progress = progress_tracker
    logger.phase("PLAN", "Starting evaluation batch", input=input_path, discoveredRuns=len(results))
    progress_tracker.start()

    evaluations = evaluate_run_results(
        results,
        experiment=experiment,
        only=only,
        mode=mode,
        continue_on_error=continue_on_error,
        fail_on_missing_gold=fail_on_missing_gold,
    )
    for _ in evaluations:
        progress_tracker.advance()

    target_dir, target_jsonl = evaluation_output_paths(
        experiment,
        base_dir,
        output_dir=output_dir,
        output_jsonl=output_jsonl,
    )
    written_files = write_evaluation_files(evaluations, target_dir)
    for path_item in written_files:
        logger.phase("WRITE", "Artifact written", path=path_item)

    summary = build_evaluation_summary(evaluations)
    summary_path = target_dir / "evaluation-summary.json"
    write_json(summary_path, summary.model_dump(mode="json"))
    logger.phase("WRITE", "Artifact written", path=summary_path)

    if target_jsonl is not None:
        write_evaluation_jsonl(evaluations, target_jsonl)
        logger.phase("WRITE", "Artifact written", path=target_jsonl)
        print(f"Wrote {len(evaluations)} evaluation result(s) to {target_dir} and {target_jsonl}")
    else:
        print(f"Wrote {len(evaluations)} evaluation result(s) to {target_dir}")
    return 0
