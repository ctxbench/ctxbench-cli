from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.ai.engine import Engine
from copa.benchmark.evaluation import build_evaluation_summary_rows
from copa.benchmark.evaluation import (
    evaluate_run_results,
    evaluation_output_paths,
    load_experiment_for_evaluation,
    runspec_index_for_experiment,
)
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.paths import resolve_run_jsonl_path, resolve_run_output_dir
from copa.benchmark.results import (
    append_evaluation_jsonl,
    append_result_jsonl,
    serialize_evaluation_result,
    serialize_run_result,
    write_evaluation_file,
    write_result_file,
)
from copa.util.artifacts import evalresult_filename, runresult_filename
from copa.util.fs import load_json, write_json
from copa.util.jsonl import append_jsonl, read_jsonl, write_jsonl
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


def _existing_run_ids_in_jsonl(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    return {
        str(item.get("runId") or "")
        for item in read_jsonl(path)
        if isinstance(item.get("runId"), str) and str(item.get("runId"))
    }


def _result_path(target_dir: Path, runspec: RunSpec) -> Path:
    return target_dir / runresult_filename(runspec.experimentId, runspec.runId)


def _evaluation_path(target_dir: Path, runspec: RunSpec) -> Path:
    return target_dir / evalresult_filename(runspec.experimentId, runspec.runId)


def _load_persisted_evaluation_rows(target_dir: Path) -> list[dict[str, Any]]:
    return [
        load_json(path_item)
        for path_item in sorted(target_dir.glob("re_*.json"))
        if path_item.name != "evaluation-summary.json"
    ]


def _backfill_result_jsonl(
    runspecs: list[RunSpec],
    *,
    target_dir: Path,
    target_jsonl: Path | None,
    existing_run_ids: set[str],
) -> None:
    if target_jsonl is None:
        return
    for runspec in runspecs:
        if runspec.runId in existing_run_ids:
            continue
        result_path = _result_path(target_dir, runspec)
        if not result_path.exists():
            continue
        payload = load_json(result_path)
        _copy_trace_payload(
            payload,
            source_root=target_dir.parent,
            target_root=target_jsonl.parent,
        )
        append_jsonl(target_jsonl, [payload])
        existing_run_ids.add(runspec.runId)


def _backfill_evaluation_jsonl(
    runspecs: list[RunSpec],
    *,
    target_dir: Path,
    target_jsonl: Path | None,
    existing_run_ids: set[str],
) -> None:
    if target_jsonl is None:
        return
    for runspec in runspecs:
        if runspec.runId in existing_run_ids:
            continue
        evaluation_path = _evaluation_path(target_dir, runspec)
        if not evaluation_path.exists():
            continue
        payload = load_json(evaluation_path)
        _copy_trace_payload(
            payload,
            source_root=target_dir.parent,
            target_root=target_jsonl.parent,
        )
        append_jsonl(target_jsonl, [payload])
        existing_run_ids.add(runspec.runId)


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
    existing = []
    if path.exists():
        existing = [row for row in read_jsonl(path) if str(row.get("runId") or "") != run_id]
    existing.append(payload)
    write_jsonl(path, existing)


def run_command(
    path: str,
    out_dir: str | None = None,
    jsonl_path: str | None = None,
    *,
    force: bool = False,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)
    logger.phase("LOAD", "Loading run specification", path=path)
    runspecs, experiment_path = load_runspecs(path)
    if not runspecs:
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
    file_artifact_root = target_dir.parent
    jsonl_artifact_root = target_jsonl.parent if target_jsonl is not None else None
    logger.phase("LOAD", "Run specification loading completed", runs=len(runspecs))
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(runspecs))
    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()
    existing_jsonl_run_ids = _existing_run_ids_in_jsonl(target_jsonl)
    completed_runs = 0
    skipped_runs = 0
    engine = Engine(event_logger=event_logger)
    try:
        for runspec in runspecs:
            result_path = _result_path(target_dir, runspec)
            if result_path.exists() and not force:
                skipped_runs += 1
                logger.phase("SKIP", "Run already persisted; skipping execution", run=runspec.runId, path=result_path)
                progress_tracker.advance()
                completed_runs += 1
                continue
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
            if force and result_path.exists():
                logger.phase("WRITE", "Overwriting existing run artifact", run=result.runId, path=result_path)
            logger.phase("WRITE", "Writing artifact", run=result.runId, path=result_path)
            written_path = write_result_file(result, target_dir, artifact_root=file_artifact_root)
            logger.phase("WRITE", "Artifact written", run=result.runId, path=written_path)
            if target_jsonl is not None:
                if force:
                    _rewrite_jsonl_with_run_payload(
                        path=target_jsonl,
                        run_id=result.runId,
                        payload=serialize_run_result(result, artifact_root=jsonl_artifact_root),
                    )
                else:
                    append_result_jsonl(result, target_jsonl, artifact_root=jsonl_artifact_root)
                existing_jsonl_run_ids.add(result.runId)
                logger.phase("WRITE", "Artifact written", run=result.runId, path=target_jsonl)
            logger.phase("DONE", "Completed successfully", run=result.runId)
            progress_tracker.advance()
            completed_runs += 1
    finally:
        engine.close()

    if skipped_runs:
        _backfill_result_jsonl(
            runspecs,
            target_dir=target_dir,
            target_jsonl=target_jsonl,
            existing_run_ids=existing_jsonl_run_ids,
        )

    if target_jsonl is not None:
        print(
            f"Processed {completed_runs} run(s) to {target_dir} and {target_jsonl}"
            + (f" ({skipped_runs} resumed)" if skipped_runs else "")
        )
    else:
        print(
            f"Processed {completed_runs} run(s) to {target_dir}"
            + (f" ({skipped_runs} resumed)" if skipped_runs else "")
        )

    if experiment_path and runspecs[0].evaluationEnabled:
        from copa.commands.eval import load_results_from_input

        logger.phase("EVALUATE", "Starting evaluation batch", experiment=experiment_path)
        experiment, base_dir = load_experiment_for_evaluation(experiment_path)
        results = load_results_from_input(
            run_results_dir=str(target_dir),
            run_results_json=None,
            experiment_path=experiment_path,
        )
        eval_dir, eval_jsonl = evaluation_output_paths(experiment, base_dir)
        existing_eval_jsonl_ids = _existing_run_ids_in_jsonl(eval_jsonl)
        _backfill_evaluation_jsonl(
            runspecs,
            target_dir=eval_dir,
            target_jsonl=eval_jsonl,
            existing_run_ids=existing_eval_jsonl_ids,
        )

        def _persist_evaluation(_result: Any, evaluated: Any) -> None:
            if evaluated is None:
                progress_tracker.advance()
                return
            eval_path = _evaluation_path(eval_dir, evaluated)
            if eval_path.exists() and not force:
                if eval_jsonl is not None and evaluated.runId not in existing_eval_jsonl_ids:
                    append_evaluation_jsonl(evaluated, eval_jsonl, artifact_root=eval_jsonl.parent)
                    existing_eval_jsonl_ids.add(evaluated.runId)
                    logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=eval_jsonl)
                progress_tracker.advance()
                return
            if force and eval_path.exists():
                logger.phase("WRITE", "Overwriting existing evaluation artifact", run=evaluated.runId, path=eval_path)
            write_evaluation_file(evaluated, eval_dir, artifact_root=eval_dir.parent)
            logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=eval_path)
            if eval_jsonl is not None:
                if force:
                    _rewrite_jsonl_with_run_payload(
                        path=eval_jsonl,
                        run_id=evaluated.runId,
                        payload=serialize_evaluation_result(evaluated, artifact_root=eval_jsonl.parent),
                    )
                else:
                    append_evaluation_jsonl(evaluated, eval_jsonl, artifact_root=eval_jsonl.parent)
                existing_eval_jsonl_ids.add(evaluated.runId)
                logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=eval_jsonl)
            summary_path = eval_dir / "evaluation-summary.json"
            write_json(
                summary_path,
                build_evaluation_summary_rows(_load_persisted_evaluation_rows(eval_dir)).model_dump(mode="json"),
            )
            logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=summary_path)
            progress_tracker.advance()

        pending_results = [
            result
            for result in results
            if force or not _evaluation_path(eval_dir, result).exists()
        ]
        if pending_results:
            progress_tracker.total = len(pending_results)
            progress_tracker.current = 0
            progress_tracker.start()
        evaluations = evaluate_run_results(
            pending_results,
            experiment=experiment,
            event_logger=event_logger,
            on_result=_persist_evaluation,
        )
        summary_path = eval_dir / "evaluation-summary.json"
        write_json(
            summary_path,
            build_evaluation_summary_rows(_load_persisted_evaluation_rows(eval_dir)).model_dump(mode="json"),
        )
        logger.phase("WRITE", "Artifact written", path=summary_path)
        logger.phase("EVALUATE", "Evaluation completed", runs=len(evaluations), output=eval_dir)
    return 0
