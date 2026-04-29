from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from copa.benchmark.checkpoints import (
    checkpoint_path,
    load_completed_run_ids,
    write_completed_run_ids,
)
from copa.benchmark.evaluation import (
    build_evaluation_jobs,
    build_evaluation_summary_rows,
    evaluate_run_results,
    export_evaluation_rows_csv,
)
from copa.benchmark.evaluation_batch import (
    DEFAULT_BATCH_POLL_INTERVAL_SECONDS,
    load_batch_id_from_manifest,
    retrieve_evaluation_batch,
    submit_evaluation_batch,
)
from copa.benchmark.models import EvaluationModelConfig, ExperimentArtifacts, ExperimentTrace, RunResult
from copa.benchmark.selectors import RunSelector, matches_run_result
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


def _filter_judges(
    judges: list[EvaluationModelConfig],
    *,
    judge: tuple[str, ...] = (),
    exclude_judge: tuple[str, ...] = (),
) -> list[EvaluationModelConfig]:
    include = _normalize_selector_values(judge)
    exclude = _normalize_selector_values(exclude_judge)
    filtered = list(judges)
    if include:
        filtered = [item for item in filtered if _judge_matches(item, include)]
    if exclude:
        filtered = [item for item in filtered if not _judge_matches(item, exclude)]
    return filtered


def _normalize_selector_values(values: tuple[str, ...]) -> set[str]:
    return {str(value).strip() for value in values if isinstance(value, str) and str(value).strip()}


def _judge_matches(config: EvaluationModelConfig, selectors: set[str]) -> bool:
    if not selectors:
        return True
    identifiers = _judge_identifiers(config)
    return bool(identifiers & selectors)


def _judge_identifiers(config: EvaluationModelConfig) -> set[str]:
    identifiers: set[str] = set()
    for value in (config.provider, config.model):
        if isinstance(value, str) and value.strip():
            identifiers.add(value.strip())
    identifiers.update(_collect_identifier_strings(config.params))
    return identifiers


def _collect_identifier_strings(value: Any) -> set[str]:
    identifiers: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in {"id", "judgeId", "judge_id", "name", "model", "provider"} and isinstance(nested, str) and nested.strip():
                identifiers.add(nested.strip())
            identifiers.update(_collect_identifier_strings(nested))
        return identifiers
    if isinstance(value, list):
        for item in value:
            identifiers.update(_collect_identifier_strings(item))
    return identifiers


def _load_artifacts_from_manifest(source_root: Path) -> ExperimentArtifacts:
    payload = _load_evaluation_manifest(source_root)
    evaluation = payload.get("evaluation", {}) if isinstance(payload, dict) else {}
    artifacts = payload.get("artifacts")
    if isinstance(evaluation, dict) and isinstance(evaluation.get("artifacts"), dict):
        artifacts = evaluation.get("artifacts")
    return ExperimentArtifacts.model_validate(artifacts) if isinstance(artifacts, dict) else ExperimentArtifacts()


def _load_trace_from_manifest(source_root: Path) -> ExperimentTrace:
    payload = _load_evaluation_manifest(source_root)
    evaluation = payload.get("evaluation", {}) if isinstance(payload, dict) else {}
    trace = payload.get("trace")
    if isinstance(evaluation, dict) and isinstance(evaluation.get("trace"), dict):
        trace = evaluation.get("trace")
    return ExperimentTrace.model_validate(trace) if isinstance(trace, dict) else ExperimentTrace()


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
    artifacts = _load_artifacts_from_manifest(source_root)
    target_jsonl = (
        Path(output_jsonl).resolve()
        if output_jsonl
        else (source_root / str(configured_jsonl or "evaluation.jsonl")).resolve()
        if artifacts.writeJsonl
        else None
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


def _existing_run_ids_in_evaluation_dir(path: Path) -> set[str]:
    if not path.exists():
        return set()
    run_ids: set[str] = set()
    for item in sorted(path.glob("re_*.json")):
        if item.name == "evaluation-summary.json":
            continue
        try:
            payload = load_json(item)
        except Exception:
            continue
        run_id = payload.get("runId")
        if isinstance(run_id, str) and run_id:
            run_ids.add(run_id)
    return run_ids


def _load_persisted_evaluation_rows(target_dir: Path, target_jsonl: Path | None) -> list[dict[str, Any]]:
    if target_jsonl is not None and target_jsonl.exists():
        return [dict(row) for row in read_jsonl(target_jsonl)]
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
    judge: tuple[str, ...] = (),
    exclude_judge: tuple[str, ...] = (),
    batch: bool = False,
    batch_id: str | None = None,
    wait: bool = False,
    poll_interval: int = DEFAULT_BATCH_POLL_INTERVAL_SECONDS,
    continue_on_error: bool = False,
    verbose: bool = False,
    progress: bool = False,
    selector: RunSelector | None = None,
) -> int:
    if not batch and wait:
        raise ValueError("--wait can only be used with --batch.")
    if not batch and batch_id:
        raise ValueError("--batch-id can only be used with --batch.")
    if not batch and poll_interval != DEFAULT_BATCH_POLL_INTERVAL_SECONDS:
        raise ValueError("--poll-interval can only be used with --batch.")
    if poll_interval < 1:
        raise ValueError("--poll-interval must be >= 1.")

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
    active_selector = selector or RunSelector()
    if only:
        active_selector = replace(active_selector, question=only)
    results = [result for result in results if matches_run_result(result, active_selector)]
    question_filter = only or (active_selector.question if active_selector else None)
    judges = _filter_judges(
        _load_judges_from_manifest(source_root),
        judge=judge,
        exclude_judge=exclude_judge,
    )
    if not judges:
        selected = ", ".join(list(judge) or ["<all>"])
        raise ValueError(f"No judges matched the requested selector(s): {selected}.")
    artifacts = _load_artifacts_from_manifest(source_root)
    trace_config = _load_trace_from_manifest(source_root)
    write_individual_json = artifacts.writeIndividualJson
    write_traces = trace_config.writeFiles
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
    checkpoint_file = checkpoint_path(target_jsonl.parent if target_jsonl is not None else target_dir.parent, "evaluation")
    experiment_id = results[0].experimentId
    if force:
        completed_run_ids: set[str] = set()
        write_completed_run_ids(
            checkpoint_file,
            experiment_id=experiment_id,
            kind="evaluation",
            completed_run_ids=completed_run_ids,
        )
    else:
        completed_run_ids = load_completed_run_ids(
            checkpoint_file,
            experiment_id=experiment_id,
            kind="evaluation",
        )
        completed_run_ids.update(_existing_run_ids_in_jsonl(target_jsonl))
        if write_individual_json:
            completed_run_ids.update(_existing_run_ids_in_evaluation_dir(target_dir))
        if completed_run_ids:
            write_completed_run_ids(
                checkpoint_file,
                experiment_id=experiment_id,
                kind="evaluation",
                completed_run_ids=completed_run_ids,
            )
    _backfill_evaluation_jsonl(results, target_dir=target_dir, target_jsonl=target_jsonl)
    pending_results = results if force else [result for result in results if result.runId not in completed_run_ids]

    progress_tracker.total = len(pending_results)
    progress_tracker.current = 0
    progress_tracker.start()

    def _persist_evaluation(_result: RunResult, evaluated: Any) -> None:
        if evaluated is None:
            progress_tracker.advance()
            return
        evaluation_path = _evaluation_path(target_dir, evaluated)
        if write_individual_json:
            write_evaluation_file(
                evaluated,
                target_dir,
                artifact_root=file_artifact_root,
                write_trace=write_traces,
            )
            logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=evaluation_path)
        if target_jsonl is not None:
            serialized = evaluated.model_dump(mode="json")
            if jsonl_artifact_root is not None:
                from copa.benchmark.results import serialize_evaluation_result

                serialized = serialize_evaluation_result(
                    evaluated,
                    artifact_root=jsonl_artifact_root,
                    write_trace=write_traces,
                )
            if force:
                _rewrite_jsonl_with_run_payload(
                    path=target_jsonl,
                    run_id=evaluated.runId,
                    payload=serialized,
                )
            else:
                append_evaluation_jsonl(
                    evaluated,
                    target_jsonl,
                    artifact_root=jsonl_artifact_root,
                    write_trace=write_traces,
                )
            completed_run_ids.add(evaluated.runId)
            write_completed_run_ids(
                checkpoint_file,
                experiment_id=experiment_id,
                kind="evaluation",
                completed_run_ids=completed_run_ids,
            )
            logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=target_jsonl)
        else:
            completed_run_ids.add(evaluated.runId)
            write_completed_run_ids(
                checkpoint_file,
                experiment_id=experiment_id,
                kind="evaluation",
                completed_run_ids=completed_run_ids,
            )
        summary_path = target_dir / "evaluation-summary.json"
        write_json(
            summary_path,
            build_evaluation_summary_rows(_load_persisted_evaluation_rows(target_dir, target_jsonl)).model_dump(mode="json"),
        )
        logger.phase("WRITE", "Artifact written", run=evaluated.runId, path=summary_path)
        progress_tracker.advance()

    if batch:
        if len(judges) != 1:
            raise ValueError("--batch currently requires exactly one selected judge. Use --judge to choose one.")
        jobs = build_evaluation_jobs(
            pending_results,
            judges=judges,
            only=question_filter,
            mode=mode,
            event_logger=event_logger,
        )
        if not jobs:
            print(f"No pending evaluation job(s) for {input_path}.")
            return 0
        resolved_batch_id = batch_id or (None if force else load_batch_id_from_manifest(source_root))
        if resolved_batch_id is None:
            manifest = submit_evaluation_batch(jobs=jobs, source_root=source_root)
            resolved_batch_id = str(manifest.get("batchId") or "")
            print(f"Submitted evaluation batch {resolved_batch_id} with {len(jobs)} request(s).")
            if not wait:
                return 0

        manifest, batch_evaluations = retrieve_evaluation_batch(
            batch_id=resolved_batch_id,
            jobs=jobs,
            source_root=source_root,
            wait=wait,
            poll_interval=poll_interval,
        )
        if not batch_evaluations:
            print(
                f"Evaluation batch {resolved_batch_id} status: "
                f"{manifest.get('processingStatus') or manifest.get('status') or 'unknown'}"
            )
            return 0
        progress_tracker.total = len(batch_evaluations)
        progress_tracker.current = 0
        progress_tracker.start()
        results_by_run_id = {result.runId: result for result in pending_results}
        for evaluated in batch_evaluations:
            source_result = results_by_run_id.get(evaluated.runId)
            if source_result is None:
                continue
            _persist_evaluation(source_result, evaluated)
        summary_path = target_dir / "evaluation-summary.json"
        write_json(
            summary_path,
            build_evaluation_summary_rows(_load_persisted_evaluation_rows(target_dir, target_jsonl)).model_dump(mode="json"),
        )
        logger.phase("WRITE", "Artifact written", path=summary_path)
        if output_csv:
            csv_path = export_evaluation_rows_csv(_load_persisted_evaluation_rows(target_dir, target_jsonl), output_csv)
            logger.phase("WRITE", "Artifact written", path=csv_path)
        print(f"Collected evaluation batch {resolved_batch_id} with {len(batch_evaluations)} result(s).")
        return 0

    evaluations = evaluate_run_results(
        pending_results,
        judges=judges,
        only=question_filter,
        mode=mode,
        continue_on_error=continue_on_error,
        event_logger=event_logger,
        on_result=_persist_evaluation,
    )

    summary_path = target_dir / "evaluation-summary.json"
    write_json(
        summary_path,
        build_evaluation_summary_rows(_load_persisted_evaluation_rows(target_dir, target_jsonl)).model_dump(mode="json"),
    )
    logger.phase("WRITE", "Artifact written", path=summary_path)
    if output_csv:
        csv_path = export_evaluation_rows_csv(_load_persisted_evaluation_rows(target_dir, target_jsonl), output_csv)
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
