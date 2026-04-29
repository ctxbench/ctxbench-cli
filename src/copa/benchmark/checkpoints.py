from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from copa.util.clock import utc_now_iso
from copa.util.fs import load_json, write_json

RUNS_CHECKPOINT_FILENAME = "runs.checkpoint.json"
EVALUATION_CHECKPOINT_FILENAME = "evaluation.checkpoint.json"


def checkpoint_path(root: str | Path, kind: str) -> Path:
    filename = {
        "runs": RUNS_CHECKPOINT_FILENAME,
        "evaluation": EVALUATION_CHECKPOINT_FILENAME,
    }.get(kind)
    if filename is None:
        raise ValueError(f"Unknown checkpoint kind: {kind}")
    return Path(root) / filename


def load_completed_run_ids(path: str | Path | None, *, experiment_id: str, kind: str) -> set[str]:
    if path is None:
        return set()
    target = Path(path)
    if not target.exists():
        return set()
    payload = load_json(target)
    if not isinstance(payload, dict):
        return set()
    if str(payload.get("kind") or "") != kind:
        return set()
    if str(payload.get("experimentId") or "") not in {"", experiment_id}:
        return set()
    completed = payload.get("completedRunIds", [])
    if not isinstance(completed, list):
        return set()
    return {str(item) for item in completed if isinstance(item, str) and item}


def write_completed_run_ids(
    path: str | Path,
    *,
    experiment_id: str,
    kind: str,
    completed_run_ids: Iterable[str],
) -> None:
    normalized = sorted({run_id for run_id in completed_run_ids if isinstance(run_id, str) and run_id})
    payload = {
        "experimentId": experiment_id,
        "kind": kind,
        "completedCount": len(normalized),
        "completedRunIds": normalized,
        "updatedAt": utc_now_iso(),
    }
    write_json(path, payload)
