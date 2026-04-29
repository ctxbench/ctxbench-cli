from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.ai.engine import Engine
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.results import (
    append_result_jsonl,
    serialize_run_result,
    write_result_file,
)
from copa.util.artifacts import runresult_filename
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


def _artifact_root(source: Path) -> Path:
    if source.is_dir():
        return source.parent
    if source.suffix == ".jsonl":
        return source.parent
    if source.parent.name == "runs":
        return source.parent.parent
    return source.parent


def load_runspecs(path: str) -> tuple[list[RunSpec], str | None]:
    payloads = _read_runspec_payloads(path)
    if not payloads:
        return [], None
    if "dataset" not in payloads[0]:
        raise ValueError(
            "RunSpec artifacts are incomplete. Re-expand the experiment to generate self-contained runspec files."
        )
    runspecs = [RunSpec.model_validate(payload) for payload in payloads]
    experiment_path = runspecs[0].experimentPath if runspecs else None
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
    source = Path(path).resolve()
    logger = PhaseLogger(verbose=verbose)
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)
    logger.phase("LOAD", "Loading run specification", path=path)
    runspecs, _experiment_path = load_runspecs(path)
    if not runspecs:
        print("No runspecs found.")
        return 0

    output_root = _artifact_root(source)
    artifacts = runspecs[0].artifacts
    default_dir = output_root / "results"
    target_dir = Path(out_dir).resolve() if out_dir else default_dir
    target_jsonl = (
        Path(jsonl_path).resolve()
        if jsonl_path
        else output_root / "results.jsonl"
        if artifacts.writeJsonl
        else None
    )
    write_individual_json = artifacts.writeIndividualJson
    write_traces = runspecs[0].trace.writeFiles
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
            if write_individual_json and result_path.exists() and not force:
                skipped_runs += 1
                logger.phase("SKIP", "Run already persisted; skipping execution", run=runspec.runId, path=result_path)
                progress_tracker.advance()
                completed_runs += 1
                continue
            if not write_individual_json and target_jsonl is not None and runspec.runId in existing_jsonl_run_ids and not force:
                skipped_runs += 1
                logger.phase("SKIP", "Run already persisted in JSONL; skipping execution", run=runspec.runId, path=target_jsonl)
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
            if write_individual_json:
                if force and result_path.exists():
                    logger.phase("WRITE", "Overwriting existing run artifact", run=result.runId, path=result_path)
                logger.phase("WRITE", "Writing artifact", run=result.runId, path=result_path)
                written_path = write_result_file(
                    result,
                    target_dir,
                    artifact_root=file_artifact_root,
                    write_trace=write_traces,
                )
                logger.phase("WRITE", "Artifact written", run=result.runId, path=written_path)
            if target_jsonl is not None:
                if force:
                    _rewrite_jsonl_with_run_payload(
                        path=target_jsonl,
                        run_id=result.runId,
                        payload=serialize_run_result(result, artifact_root=jsonl_artifact_root, write_trace=write_traces),
                    )
                else:
                    append_result_jsonl(result, target_jsonl, artifact_root=jsonl_artifact_root, write_trace=write_traces)
                existing_jsonl_run_ids.add(result.runId)
                logger.phase("WRITE", "Artifact written", run=result.runId, path=target_jsonl)
            logger.phase("DONE", "Completed successfully", run=result.runId)
            progress_tracker.advance()
            completed_runs += 1
    finally:
        engine.close()

    if skipped_runs and write_individual_json:
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
    return 0
