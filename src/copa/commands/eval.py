from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.evaluation import (
    build_evaluation_summary_rows,
    evaluate_run_results,
    evaluation_output_paths,
    export_evaluation_rows_csv,
    load_experiment_for_evaluation,
    runspec_index_for_experiment,
)
from copa.benchmark.models import RunResult
from copa.benchmark.results import append_evaluation_jsonl, write_evaluation_file
from copa.util.artifacts import evalresult_filename
from copa.util.fs import load_json, write_json
from copa.util.jsonl import append_jsonl, read_jsonl
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
    if "dataset" in payloads[0]:
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
                question=str(payload.get("question") or runspec.question),
                questionTemplate=str(payload.get("questionTemplate") or runspec.questionTemplate or ""),
                instanceId=runspec.instanceId,
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
                metricsSummary=payload.get("metricsSummary", {}),
                trace=trace_payload,
                traceRef=payload.get("traceRef"),
                metadata=runspec.metadata,
            )
        )
    return results


def _evaluation_path(target_dir: Path, result: RunResult) -> Path:
    return target_dir / evalresult_filename(result.experimentId, result.runId)


def _existing_run_ids_in_jsonl(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {
        str(item.get("runId") or "")
        for item in read_jsonl(path)
        if isinstance(item.get("runId"), str) and str(item.get("runId"))
    }


def _load_persisted_evaluation_rows(target_dir: Path) -> list[dict[str, Any]]:
    return [
        load_json(path_item)
        for path_item in sorted(target_dir.glob("re_*.json"))
        if path_item.name != "evaluation-summary.json"
    ]


def _backfill_evaluation_jsonl(results: list[RunResult], *, target_dir: Path, target_jsonl: Path | None) -> set[str]:
    existing_run_ids = _existing_run_ids_in_jsonl(target_jsonl)
    if target_jsonl is None:
        return existing_run_ids
    for result in results:
        if result.runId in existing_run_ids:
            continue
        evaluation_path = _evaluation_path(target_dir, result)
        if not evaluation_path.exists():
            continue
        payload = load_json(evaluation_path)
        _copy_trace_payload(
            payload,
            source_root=target_dir.parent,
            target_root=target_jsonl.parent,
        )
        append_jsonl(target_jsonl, [payload])
        existing_run_ids.add(result.runId)
    return existing_run_ids


def _copy_trace_payload(payload: dict[str, Any], *, source_root: Path, target_root: Path) -> None:
    trace_ref = payload.get("traceRef")
    if not isinstance(trace_ref, str) or not trace_ref:
        return
    source_trace = source_root / trace_ref
    if not source_trace.exists():
        return
    write_json(target_root / trace_ref, load_json(source_trace))


def _rewrite_jsonl_with_run_payload(
    *,
    path: Path,
    run_id: str,
    payload: dict[str, Any],
) -> None:
    from copa.util.jsonl import write_jsonl

    existing = []
    if path.exists():
        existing = [row for row in read_jsonl(path) if str(row.get("runId") or "") != run_id]
    existing.append(payload)
    write_jsonl(path, existing)


def eval_command(
    *,
    run_results_dir: str | None,
    run_results_json: str | None,
    experiment_path: str,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
    output_csv: str | None = None,
    force: bool = False,
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
    target_dir, target_jsonl = evaluation_output_paths(
        experiment,
        base_dir,
        output_dir=output_dir,
        output_jsonl=output_jsonl,
    )
    file_artifact_root = target_dir.parent
    jsonl_artifact_root = target_jsonl.parent if target_jsonl is not None else None
    progress_tracker.start()
    existing_jsonl_run_ids = _backfill_evaluation_jsonl(results, target_dir=target_dir, target_jsonl=target_jsonl)
    pending_results = results if force else [result for result in results if not _evaluation_path(target_dir, result).exists()]

    progress_tracker.total = len(pending_results)
    progress_tracker.current = 0
    progress_tracker.start()

    def _persist_evaluation(_result: RunResult, evaluated: Any) -> None:
        if evaluated is None:
            progress_tracker.advance()
            return
        evaluation_path = _evaluation_path(target_dir, evaluated)
        write_evaluation_file(evaluated, target_dir, artifact_root=file_artifact_root)
        logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=evaluation_path)
        if target_jsonl is not None:
            serialized = evaluated.model_dump(mode="json")
            if jsonl_artifact_root is not None:
                from copa.benchmark.results import serialize_evaluation_result

                serialized = serialize_evaluation_result(evaluated, artifact_root=jsonl_artifact_root)
            if force:
                _rewrite_jsonl_with_run_payload(
                    path=target_jsonl,
                    run_id=evaluated.runId,
                    payload=serialized,
                )
            else:
                append_evaluation_jsonl(evaluated, target_jsonl, artifact_root=jsonl_artifact_root)
            existing_jsonl_run_ids.add(evaluated.runId)
            logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=target_jsonl)
        summary_path = target_dir / "evaluation-summary.json"
        write_json(
            summary_path,
            build_evaluation_summary_rows(_load_persisted_evaluation_rows(target_dir)).model_dump(mode="json"),
        )
        logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=summary_path)
        progress_tracker.advance()

    evaluations = evaluate_run_results(
        pending_results,
        experiment=experiment,
        only=only,
        mode=mode,
        continue_on_error=continue_on_error,
        fail_on_missing_gold=fail_on_missing_gold,
        event_logger=event_logger,
        on_result=_persist_evaluation,
    )

    summary_path = target_dir / "evaluation-summary.json"
    write_json(
        summary_path,
        build_evaluation_summary_rows(_load_persisted_evaluation_rows(target_dir)).model_dump(mode="json"),
    )
    logger.phase("WRITE", "Artifact written", path=summary_path)
    if output_csv:
        csv_path = export_evaluation_rows_csv(_load_persisted_evaluation_rows(target_dir), output_csv)
        logger.phase("WRITE", "Artifact written", path=csv_path)

    if target_jsonl is not None:
        print(
            f"Processed {len(results)} evaluation result(s) to {target_dir} and {target_jsonl}"
            + (f" ({len(results) - len(pending_results)} resumed)" if len(results) != len(pending_results) else "")
        )
    else:
        print(
            f"Processed {len(results)} evaluation result(s) to {target_dir}"
            + (f" ({len(results) - len(pending_results)} resumed)" if len(results) != len(pending_results) else "")
        )
    return 0
