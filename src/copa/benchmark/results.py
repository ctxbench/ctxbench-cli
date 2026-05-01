from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from copa.benchmark.models import EvaluationRunResult, EvaluationTrace, RunResult, RunTrace
from copa.util.fs import write_json
from copa.util.jsonl import append_jsonl, write_jsonl


def _has_trace_payload(trace: RunTrace) -> bool:
    return bool(
        trace.aiTrace
        or trace.toolCalls
        or trace.nativeMcp
        or trace.serverMcp
        or trace.rawResponse is not None
        or trace.error is not None
    )


def _has_evaluation_trace_payload(trace: EvaluationTrace) -> bool:
    return bool(
        trace.aiTrace
        or trace.rawResponse is not None
        or trace.error is not None
    )


def _write_trace_payload(
    *,
    artifact_root: str | Path,
    task: str,
    run_id: str,
    payload: dict[str, Any],
) -> str:
    root = Path(artifact_root)
    relative_path = Path("traces") / task / f"{run_id}.json"
    write_json(root / relative_path, payload)
    return relative_path.as_posix()


def write_trace_file(result: RunResult, artifact_root: str | Path) -> str | None:
    if not _has_trace_payload(result.trace):
        return None
    payload = {
        "experimentId": result.experimentId,
        "runId": result.runId,
        "task": "queries",
        "trace": result.trace.model_dump(mode="json"),
    }
    return _write_trace_payload(
        artifact_root=artifact_root,
        task="queries",
        run_id=result.runId,
        payload=payload,
    )


def write_evaluation_trace_file(result: EvaluationRunResult, artifact_root: str | Path) -> str | None:
    item = result.items[0] if result.items else None
    if item is None or not _has_evaluation_trace_payload(item.evaluationTrace):
        return None
    payload = {
        "experimentId": result.experimentId,
        "runId": result.runId,
        "task": "evals",
        "trace": item.evaluationTrace.model_dump(mode="json"),
    }
    return _write_trace_payload(
        artifact_root=artifact_root,
        task="evals",
        run_id=result.runId,
        payload=payload,
    )


def serialize_run_result(
    result: RunResult,
    *,
    artifact_root: str | Path,
    write_trace: bool = True,
) -> dict[str, Any]:
    trace_ref = write_trace_file(result, artifact_root) if write_trace else None
    result.traceRef = trace_ref
    return result.to_persisted_artifact(trace_ref=trace_ref)


def serialize_evaluation_result(
    result: EvaluationRunResult,
    *,
    artifact_root: str | Path | None = None,
    write_trace: bool = True,
) -> dict[str, Any]:
    item = result.items[0] if result.items else None
    trace_ref = write_evaluation_trace_file(result, artifact_root) if artifact_root is not None and write_trace else None
    if item is None:
        return {
            "experimentId": result.experimentId,
            "runId": result.runId,
            "repeatIndex": result.metadata.repeatIndex,
            "questionId": result.questionId,
            "status": "not_evaluated",
            "evaluationMethod": None,
            "details": {},
            "traceRef": trace_ref,
        }
    payload = item.to_persisted_artifact()
    payload["repeatIndex"] = result.metadata.repeatIndex
    payload["traceRef"] = trace_ref
    return payload


def append_result_jsonl(
    result: RunResult,
    path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    write_trace: bool = True,
) -> Path:
    target_path = Path(path)
    root = Path(artifact_root) if artifact_root is not None else target_path.parent
    append_jsonl(target_path, [serialize_run_result(result, artifact_root=root, write_trace=write_trace)])
    return target_path


def write_results_jsonl(
    results: Iterable[RunResult],
    path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    write_trace: bool = True,
) -> Path:
    target_path = Path(path)
    root = Path(artifact_root) if artifact_root is not None else target_path.parent
    result_list = list(results)
    write_jsonl(target_path, [serialize_run_result(r, artifact_root=root, write_trace=write_trace) for r in result_list])
    return target_path


def append_evaluation_jsonl(
    evaluation: EvaluationRunResult,
    path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    write_trace: bool = True,
) -> Path:
    target_path = Path(path)
    root = Path(artifact_root) if artifact_root is not None else target_path.parent
    append_jsonl(target_path, [serialize_evaluation_result(evaluation, artifact_root=root, write_trace=write_trace)])
    return target_path


def write_evaluation_jsonl(
    evaluations: Iterable[EvaluationRunResult],
    path: str | Path,
    *,
    artifact_root: str | Path | None = None,
    write_trace: bool = True,
) -> Path:
    target_path = Path(path)
    root = Path(artifact_root) if artifact_root is not None else target_path.parent
    evaluation_list = list(evaluations)
    write_jsonl(target_path, [serialize_evaluation_result(e, artifact_root=root, write_trace=write_trace) for e in evaluation_list])
    return Path(path)
