from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from copa.benchmark.models import EvaluationRunResult, RunResult, RunTrace
from copa.util.artifacts import evalresult_filename, runresult_filename
from copa.util.fs import write_json
from copa.util.jsonl import write_jsonl


def _has_trace_payload(trace: RunTrace) -> bool:
    return bool(trace.aiTrace or trace.toolCalls or trace.rawResponse is not None or trace.error is not None)


def write_trace_file(result: RunResult, artifact_root: str | Path) -> str | None:
    if not _has_trace_payload(result.trace):
        return None
    root = Path(artifact_root)
    relative_path = Path("traces") / result.experimentId / f"{result.runId}.json"
    payload = {
        "experimentId": result.experimentId,
        "runId": result.runId,
        "trace": result.trace.model_dump(mode="json"),
    }
    write_json(root / relative_path, payload)
    return relative_path.as_posix()


def serialize_run_result(result: RunResult, *, artifact_root: str | Path) -> dict[str, Any]:
    trace_ref = write_trace_file(result, artifact_root)
    result.traceRef = trace_ref
    return result.to_persisted_artifact(trace_ref=trace_ref)


def serialize_evaluation_result(result: EvaluationRunResult) -> dict[str, Any]:
    item = result.items[0] if result.items else None
    if item is None:
        return {
            "runId": result.runId,
            "questionId": result.questionId,
            "score": 0.0,
            "label": "not_evaluated",
            "details": {},
        }
    return item.to_persisted_artifact()


def write_result_files(
    results: Iterable[RunResult],
    out_dir: str | Path,
    *,
    artifact_root: str | Path | None = None,
) -> list[Path]:
    result_list = list(results)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    root = Path(artifact_root) if artifact_root is not None else target.parent
    paths: list[Path] = []
    for result in result_list:
        path = target / runresult_filename(result.experimentId, result.runId)
        write_json(path, serialize_run_result(result, artifact_root=root))
        paths.append(path)
    return paths


def write_results_jsonl(
    results: Iterable[RunResult],
    path: str | Path,
    *,
    artifact_root: str | Path | None = None,
) -> Path:
    target_path = Path(path)
    root = Path(artifact_root) if artifact_root is not None else target_path.parent
    result_list = list(results)
    write_jsonl(target_path, [serialize_run_result(result, artifact_root=root) for result in result_list])
    return target_path


def write_evaluation_files(
    evaluations: Iterable[EvaluationRunResult],
    out_dir: str | Path,
) -> list[Path]:
    evaluation_list = list(evaluations)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for item in evaluation_list:
        path = target / evalresult_filename(item.experimentId, item.runId)
        write_json(path, serialize_evaluation_result(item))
        paths.append(path)
    return paths


def write_evaluation_jsonl(evaluations: Iterable[EvaluationRunResult], path: str | Path) -> Path:
    evaluation_list = list(evaluations)
    write_jsonl(path, [serialize_evaluation_result(item) for item in evaluation_list])
    return Path(path)
