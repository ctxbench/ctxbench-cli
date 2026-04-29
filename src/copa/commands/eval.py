from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.evaluation import (
    build_evaluation_summary_rows,
    evaluate_run_results,
    export_evaluation_rows_csv,
)
from copa.benchmark.models import EvaluationModelConfig, RunResult
from copa.benchmark.results import append_evaluation_jsonl, write_evaluation_file
from copa.util.artifacts import evalresult_filename
from copa.util.fs import load_json, write_json
from copa.util.jsonl import append_jsonl, read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def _read_result_payloads(
    *,
    run_dir: str | None = None,
    run_jsonl: str | None = None,
) -> tuple[list[dict[str, Any]], Path]:
    if bool(run_dir) == bool(run_jsonl):
        raise ValueError("Provide exactly one of --run-dir or --run-jsonl.")
    if run_dir:
        source = Path(run_dir)
        payloads = [load_json(item) for item in sorted(source.glob("*.json"))]
        return payloads, source
    source = Path(run_jsonl or "")
    if source.suffix == ".jsonl":
        return [dict(item) for item in read_jsonl(source)], source
    return [load_json(source)], source


def _artifact_root(source: Path) -> Path:
    if source.is_dir():
        return source.parent
    if source.suffix == ".jsonl":
        return source.parent
    if source.parent.name == "results":
        return source.parent.parent
    return source.parent


def _evaluation_manifest_path(source_root: Path) -> Path:
    return source_root / "evaluation.manifest.json"


def _load_evaluation_manifest(source_root: Path) -> dict[str, Any]:
    manifest_path = _evaluation_manifest_path(source_root)
    if not manifest_path.exists():
        raise ValueError(
            f"Missing evaluation manifest: {manifest_path}. Re-expand the experiment to generate self-contained evaluation metadata."
        )
    payload = load_json(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid evaluation manifest: {manifest_path}")
    return payload


def _load_judges_from_manifest(source_root: Path) -> list[EvaluationModelConfig]:
    payload = _load_evaluation_manifest(source_root)
    evaluation = payload.get("evaluation", {})
    judges_payload = evaluation.get("judges", []) if isinstance(evaluation, dict) else []
    return [
        EvaluationModelConfig.model_validate(item)
        for item in judges_payload
        if isinstance(item, dict)
    ]


def _evaluation_output_paths(
    source_root: Path,
    *,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
) -> tuple[Path, Path | None]:
    manifest = _load_evaluation_manifest(source_root)
    evaluation = manifest.get("evaluation", {}) if isinstance(manifest, dict) else {}
    configured_dir = evaluation.get("output") if isinstance(evaluation, dict) else None
    configured_jsonl = evaluation.get("jsonl") if isinstance(evaluation, dict) else None
    target_dir = Path(output_dir).resolve() if output_dir else (source_root / str(configured_dir or "evaluation")).resolve()
    target_jsonl = (
        Path(output_jsonl).resolve()
        if output_jsonl
        else (source_root / str(configured_jsonl or "evaluation.jsonl")).resolve()
    )
    return target_dir, target_jsonl


def load_results_from_input(
    *,
    run_dir: str | None = None,
    run_jsonl: str | None = None,
) -> list[RunResult]:
    payloads, _source = _read_result_payloads(
        run_dir=run_dir,
        run_jsonl=run_jsonl,
    )
    if not payloads:
        return []
    if "dataset" not in payloads[0]:
        raise ValueError(
            "Run result artifacts are incomplete. Re-run execution with self-contained run results before evaluating."
        )
    required_result_fields = {"answer", "status", "timing"}
    missing = sorted(field for field in required_result_fields if field not in payloads[0])
    if missing:
        raise ValueError(
            "Input artifacts look like run specifications, not run results. "
            f"Missing result fields: {', '.join(missing)}. "
            "Use --run-jsonl with results.jsonl or --run-dir with the results directory."
        )
    return [RunResult.model_validate(item) for item in payloads]


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
    run_dir: str | None,
    run_jsonl: str | None,
    output_dir: str | None = None,
    output_jsonl: str | None = None,
    output_csv: str | None = None,
    force: bool = False,
    only: str | None = None,
    mode: str | None = None,
    continue_on_error: bool = False,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)
    input_path = run_dir or run_jsonl or ""
    source = Path(input_path).resolve()
    source_root = _artifact_root(source)
    logger.phase("LOAD", "Loading run results", path=input_path)
    results = load_results_from_input(
        run_dir=run_dir,
        run_jsonl=run_jsonl,
    )
    judges = _load_judges_from_manifest(source_root)
    progress_tracker = ProgressTracker(total=len(results), enabled=progress)
    logger.progress = progress_tracker
    logger.phase("PLAN", "Starting evaluation batch", input=input_path, discoveredRuns=len(results))
    target_dir, target_jsonl = _evaluation_output_paths(
        source_root,
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
        judges=judges,
        only=only,
        mode=mode,
        continue_on_error=continue_on_error,
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
