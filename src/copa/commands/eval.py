from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.evaluation import (
    build_evaluation_summary,
    evaluate_run_results,
    evaluation_output_paths,
    load_experiment_for_evaluation,
    runspec_index_for_experiment,
    write_evaluation_files,
    write_evaluation_jsonl,
)
from copa.benchmark.models import RunResult
from copa.util.fs import load_json, write_json
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def _read_result_payloads(
    *,
    run_results_dir: str | None = None,
    run_results_json: str | None = None,
) -> tuple[list[dict[str, Any]], Path]:
    if bool(run_results_dir) == bool(run_results_json):
        raise ValueError("Provide exactly one of --run-results-dir or --run-results-json.")
    if run_results_dir:
        source = Path(run_results_dir)
        payloads = [load_json(item) for item in sorted(source.glob("*.json"))]
        return payloads, source
    source = Path(run_results_json or "")
    if source.suffix == ".jsonl":
        return [dict(item) for item in read_jsonl(source)], source
    return [load_json(source)], source


def _load_trace_payload(source_root: Path, trace_ref: str | None) -> dict[str, Any]:
    if not trace_ref:
        return {}
    trace_path = source_root / trace_ref
    if not trace_path.exists():
        return {}
    payload = load_json(trace_path)
    trace = payload.get("trace", {})
    return trace if isinstance(trace, dict) else {}


def load_results_from_input(
    *,
    run_results_dir: str | None = None,
    run_results_json: str | None = None,
    experiment_path: str,
) -> list[RunResult]:
    payloads, source = _read_result_payloads(
        run_results_dir=run_results_dir,
        run_results_json=run_results_json,
    )
    if not payloads:
        return []
    if "questionId" in payloads[0]:
        return [RunResult.model_validate(item) for item in payloads]

    experiment, base_dir = load_experiment_for_evaluation(experiment_path)
    runspecs_by_id = runspec_index_for_experiment(experiment, base_dir, experiment_path=experiment_path)
    source_root = source if source.is_dir() else source.parent
    results: list[RunResult] = []
    for payload in payloads:
        run_id = str(payload.get("runId") or "")
        runspec = runspecs_by_id.get(run_id)
        if runspec is None:
            raise ValueError(f"Run '{run_id}' not found when regenerating execution context from experiment.")
        trace_payload = _load_trace_payload(source_root, payload.get("traceRef"))
        results.append(
            RunResult(
                runId=runspec.runId,
                experimentId=runspec.experimentId,
                dataset=runspec.dataset,
                questionId=runspec.questionId,
                contextId=runspec.contextId,
                provider=runspec.provider,
                modelName=runspec.modelName,
                strategy=runspec.strategy,
                format=runspec.format,
                repeatIndex=runspec.repeatIndex,
                outputRoot=runspec.outputRoot,
                answer=str(payload.get("answer", "")),
                status=str(payload.get("status", "")),
                errorMessage=payload.get("errorMessage"),
                timing=payload.get("timing", {}),
                usage=payload.get("usage", {}),
                trace=trace_payload,
                traceRef=payload.get("traceRef"),
                metadata=runspec.metadata,
            )
        )
    return results


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
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)
    logger.phase("LOAD", "Loading experiment", path=experiment_path)
    experiment, base_dir = load_experiment_for_evaluation(experiment_path)
    input_path = run_results_dir or run_results_json or ""
    logger.phase("LOAD", "Loading run results", path=input_path)
    results = load_results_from_input(
        run_results_dir=run_results_dir,
        run_results_json=run_results_json,
        experiment_path=experiment_path,
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
        event_logger=event_logger,
        on_result=lambda _result, _evaluated: progress_tracker.advance(),
    )

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
