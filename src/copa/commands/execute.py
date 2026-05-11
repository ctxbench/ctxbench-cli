from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.ai.engine import Engine
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.selectors import RunSelector, matches_runspec
from copa.benchmark.results import serialize_run_result
from copa.util.jsonl import append_jsonl, read_jsonl, write_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def _load_runspecs(path: Path) -> list[RunSpec]:
    if not path.exists():
        raise FileNotFoundError(f"Queries file not found: {path}. Run 'ctxbench plan' first.")
    payloads = [dict(item) for item in read_jsonl(path)]
    if not payloads:
        return []
    if "dataset" not in payloads[0]:
        raise ValueError(
            "Queries file is missing context data. Re-run 'ctxbench plan' to regenerate."
        )
    return [RunSpec.model_validate(payload) for payload in payloads]


def _load_answer_statuses(path: Path) -> dict[str, str]:
    """Returns {runId: latest status} from answers.jsonl. Handles duplicates by taking last entry."""
    if not path.exists():
        return {}
    statuses: dict[str, str] = {}
    for item in read_jsonl(path):
        run_id = str(item.get("runId", ""))
        if run_id:
            statuses[run_id] = str(item.get("status", ""))
    return statuses


def _compact_answers(path: Path) -> None:
    """Rewrite answers.jsonl keeping only the last entry per runId."""
    if not path.exists():
        return
    rows = list(read_jsonl(path))
    seen: dict[str, dict[str, Any]] = {}
    for row in rows:
        run_id = str(row.get("runId", ""))
        if run_id:
            seen[run_id] = dict(row)
    write_jsonl(path, list(seen.values()))


def execute_command(
    queries: str | None = None,
    *,
    force: bool = False,
    verbose: bool = False,
    progress: bool = False,
    selector: RunSelector | None = None,
) -> int:
    source = Path(queries).resolve() if queries else Path("queries.jsonl").resolve()
    logger = PhaseLogger(verbose=verbose)
    event_logger = lambda label, message, fields: logger.phase(label, message, **fields)

    logger.phase("LOAD", "Loading queries", path=str(source))
    runspecs = _load_runspecs(source)

    active_selector = selector or RunSelector()
    runspecs = [r for r in runspecs if matches_runspec(r, active_selector)]
    if not runspecs:
        print("No queries matched the selector.")
        return 0

    answers_path = source.parent / "answers.jsonl"
    artifact_root = source.parent
    write_traces = runspecs[0].trace.writeFiles

    answer_statuses = {} if force else _load_answer_statuses(answers_path)
    has_duplicates = False
    logger.phase(
        "LOAD",
        "Queries loaded",
        total=len(runspecs),
        answered=sum(1 for s in answer_statuses.values() if s == "success"),
    )

    progress_tracker = ProgressTracker(total=len(runspecs), enabled=progress)
    logger.progress = progress_tracker
    progress_tracker.start()

    completed = 0
    skipped = 0
    engine = Engine(event_logger=event_logger)
    try:
        for runspec in runspecs:
            existing_status = answer_statuses.get(runspec.runId)

            if existing_status == "success" and not force:
                skipped += 1
                logger.phase("SKIP", "Already answered successfully; skipping", run=runspec.runId)
                progress_tracker.advance()
                completed += 1
                continue

            logger.phase(
                "EXECUTE",
                "Generating answer",
                run=runspec.runId,
                model=runspec.modelName or "",
                question=runspec.questionId,
            )
            result = execute_runspec(runspec, engine)
            logger.phase(
                "EXECUTE",
                "Answer generated",
                run=runspec.runId,
                status=result.status,
            )
            payload = serialize_run_result(result, artifact_root=artifact_root, write_trace=write_traces)
            append_jsonl(answers_path, [payload])
            if existing_status is not None:
                # Previous entry exists (error case) — will compact at end
                has_duplicates = True
            answer_statuses[result.runId] = result.status
            logger.phase("WRITE", "Answer written", run=result.runId)
            progress_tracker.advance()
            completed += 1
    finally:
        engine.close()

    if has_duplicates or force:
        _compact_answers(answers_path)

    print(
        f"Processed {completed} query(ies) → {answers_path}"
        + (f" ({skipped} skipped)" if skipped else "")
    )
    return 0
