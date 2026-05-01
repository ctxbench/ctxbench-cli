from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.evaluation import (
    build_evaluation_jobs,
    build_evaluation_summary_rows,
    evaluate_run_results,
)
from copa.benchmark.evaluation_batch import (
    DEFAULT_BATCH_POLL_INTERVAL_SECONDS,
    load_batch_id_from_manifest,
    retrieve_evaluation_batch,
    submit_evaluation_batch,
)
from copa.benchmark.models import EvaluationModelConfig, ExperimentTrace, RunResult
from copa.benchmark.selectors import RunSelector, matches_run_result
from copa.benchmark.results import serialize_evaluation_result, append_evaluation_jsonl
from copa.util.fs import load_json, write_json
from copa.util.jsonl import append_jsonl, read_jsonl, write_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


# ---------------------------------------------------------------------------
# Input loading
# ---------------------------------------------------------------------------

def _load_answers(path: Path) -> list[RunResult]:
    if not path.exists():
        raise FileNotFoundError(f"Answers file not found: {path}. Run 'copa query' first.")
    payloads = [dict(item) for item in read_jsonl(path)]
    if not payloads:
        return []
    required = {"answer", "status", "timing"}
    missing = sorted(required - set(payloads[0]))
    if missing:
        raise ValueError(
            f"Input looks like queries, not answers (missing: {', '.join(missing)}). "
            "Pass answers.jsonl, not queries.jsonl."
        )
    if "dataset" not in payloads[0]:
        raise ValueError(
            "Answers file is missing context data. Re-run 'copa query' to regenerate."
        )
    return [RunResult.model_validate(item) for item in payloads]


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _load_manifest(source_root: Path) -> dict[str, Any]:
    path = source_root / "manifest.json"
    if not path.exists():
        raise ValueError(
            f"Missing manifest: {path}. Re-run 'copa plan' to regenerate."
        )
    payload = load_json(path)
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid manifest: {path}")
    return payload


def _load_judges(source_root: Path) -> list[EvaluationModelConfig]:
    manifest = _load_manifest(source_root)
    evaluation = manifest.get("evaluation", {})
    judges_payload = evaluation.get("judges", []) if isinstance(evaluation, dict) else []
    return [
        EvaluationModelConfig.model_validate(item)
        for item in judges_payload
        if isinstance(item, dict)
    ]


def _load_trace_config(source_root: Path) -> ExperimentTrace:
    manifest = _load_manifest(source_root)
    trace = manifest.get("trace")
    return ExperimentTrace.model_validate(trace) if isinstance(trace, dict) else ExperimentTrace()


def _filter_judges(
    judges: list[EvaluationModelConfig],
    *,
    judge: tuple[str, ...] = (),
    not_judge: tuple[str, ...] = (),
) -> list[EvaluationModelConfig]:
    include = set(judge)
    exclude = set(not_judge)
    filtered = list(judges)
    if include:
        filtered = [j for j in filtered if _judge_matches(j, include)]
    if exclude:
        filtered = [j for j in filtered if not _judge_matches(j, exclude)]
    return filtered


def _judge_matches(config: EvaluationModelConfig, selectors: set[str]) -> bool:
    return bool(_judge_identifiers(config) & selectors)


def _judge_identifiers(config: EvaluationModelConfig) -> set[str]:
    ids: set[str] = set()
    for value in (config.provider, config.model):
        if isinstance(value, str) and value.strip():
            ids.add(value.strip())
    judge_id = config.params.get("id") if isinstance(config.params, dict) else None
    if isinstance(judge_id, str) and judge_id.strip():
        ids.add(judge_id.strip())
    return ids


# ---------------------------------------------------------------------------
# Eval status tracking (replaces checkpoint)
# ---------------------------------------------------------------------------

def _load_eval_statuses(path: Path) -> dict[str, str]:
    """Returns {runId: latest status} from evals.jsonl."""
    if not path.exists():
        return {}
    statuses: dict[str, str] = {}
    for item in read_jsonl(path):
        run_id = str(item.get("runId", ""))
        if run_id:
            statuses[run_id] = str(item.get("status", ""))
    return statuses


def _compact_evals(path: Path) -> None:
    """Rewrite evals.jsonl keeping only the last entry per runId."""
    if not path.exists():
        return
    rows = list(read_jsonl(path))
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = str(row.get("runId", ""))
        if run_id:
            seen[run_id] = dict(row)
    write_jsonl(path, list(seen.values()))


# ---------------------------------------------------------------------------
# eval command
# ---------------------------------------------------------------------------

def eval_command(
    answers: str | None = None,
    *,
    force: bool = False,
    judge: tuple[str, ...] = (),
    not_judge: tuple[str, ...] = (),
    batch: bool = False,
    batch_id: str | None = None,
    wait: bool = False,
    poll_interval: int = DEFAULT_BATCH_POLL_INTERVAL_SECONDS,
    continue_on_error: bool = False,
    verbose: bool = False,
    progress: bool = False,
    selector: RunSelector | None = None,
) -> int:
    # --batch-id implies --batch
    if batch_id:
        batch = True
    if not batch and wait:
        raise ValueError("--wait requires --batch.")
    if not batch and poll_interval != DEFAULT_BATCH_POLL_INTERVAL_SECONDS:
        raise ValueError("--poll-interval requires --batch.")
    if poll_interval < 1:
        raise ValueError("--poll-interval must be >= 1.")

    logger = PhaseLogger(verbose=verbose)
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)

    source = Path(answers).resolve() if answers else Path("answers.jsonl").resolve()
    source_root = source.parent

    logger.phase("LOAD", "Loading answers", path=str(source))
    results = _load_answers(source)

    active_selector = selector or RunSelector()
    results = [r for r in results if matches_run_result(r, active_selector)]
    if not results:
        print("No answers matched the selector.")
        return 0

    judges = _filter_judges(
        _load_judges(source_root),
        judge=judge,
        not_judge=not_judge,
    )
    if not judges:
        selected = ", ".join(list(judge) or ["<all>"])
        raise ValueError(f"No judges matched the selector(s): {selected}.")

    trace_config = _load_trace_config(source_root)
    write_traces = trace_config.writeFiles

    evals_path = source_root / "evals.jsonl"
    artifact_root = source_root

    eval_statuses = {} if force else _load_eval_statuses(evals_path)
    has_duplicates = False

    pending = [r for r in results if force or eval_statuses.get(r.runId) != "evaluated"]
    logger.phase(
        "LOAD",
        "Answers loaded",
        total=len(results),
        evaluated=len(results) - len(pending),
        pending=len(pending),
    )

    progress_tracker = ProgressTracker(total=len(pending), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()

    def _persist(result: RunResult, evaluated: Any) -> None:
        if evaluated is None:
            progress_tracker.advance()
            return
        payload = serialize_evaluation_result(evaluated, artifact_root=artifact_root, write_trace=write_traces)
        append_jsonl(evals_path, [payload])
        if eval_statuses.get(evaluated.runId) is not None:
            nonlocal has_duplicates
            has_duplicates = True
        eval_statuses[evaluated.runId] = str(payload.get("status", ""))
        logger.phase("WRITE", "Evaluation written", run=evaluated.runId)
        progress_tracker.advance()

    if batch:
        if len(judges) != 1:
            raise ValueError("--batch requires exactly one judge. Use --judge to select one.")
        jobs = build_evaluation_jobs(
            pending,
            judges=judges,
            only=None,
            mode=None,
            event_logger=event_logger,
        )
        if not jobs:
            print("No pending evaluation jobs.")
            return 0
        resolved_batch_id = batch_id or (None if force else load_batch_id_from_manifest(source_root))
        if resolved_batch_id is None:
            manifest = submit_evaluation_batch(jobs=jobs, source_root=source_root)
            resolved_batch_id = str(manifest.get("batchId") or "")
            print(f"Submitted batch {resolved_batch_id} ({len(jobs)} request(s)).")
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
                f"Batch {resolved_batch_id} status: "
                f"{manifest.get('processingStatus') or manifest.get('status') or 'unknown'}"
            )
            return 0

        progress_tracker.total = len(batch_evaluations)
        progress_tracker.current = 0
        progress_tracker.start()
        results_by_run_id = {r.runId: r for r in pending}
        for evaluated in batch_evaluations:
            source_result = results_by_run_id.get(evaluated.runId)
            if source_result is not None:
                _persist(source_result, evaluated)

        if has_duplicates:
            _compact_evals(evals_path)
        _write_summary(evals_path, source_root)
        print(f"Collected batch {resolved_batch_id} ({len(batch_evaluations)} result(s)).")
        return 0

    evaluate_run_results(
        pending,
        judges=judges,
        only=None,
        mode=None,
        continue_on_error=continue_on_error,
        event_logger=event_logger,
        on_result=_persist,
    )

    if has_duplicates or force:
        _compact_evals(evals_path)
    _write_summary(evals_path, source_root)

    skipped = len(results) - len(pending)
    print(
        f"Evaluated {len(pending)} answer(s) → {evals_path}"
        + (f" ({skipped} skipped)" if skipped else "")
    )
    return 0


def _write_summary(evals_path: Path, source_root: Path) -> None:
    if not evals_path.exists():
        return
    rows = [dict(item) for item in read_jsonl(evals_path)]
    summary_path = source_root / "evals-summary.json"
    write_json(summary_path, build_evaluation_summary_rows(rows).model_dump(mode="json"))
