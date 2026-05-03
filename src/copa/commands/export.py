from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from copa.benchmark.selectors import RunSelector, matches_run_result
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger


_SUPPORTED_FORMATS = ("csv",)

# ---------------------------------------------------------------------------
# Field extraction helpers
# ---------------------------------------------------------------------------

def _ans(row: dict[str, Any], key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _metrics(row: dict[str, Any], key: str) -> Any:
    return (row.get("metricsSummary") or {}).get(key)


def _usage(row: dict[str, Any], key: str) -> Any:
    return (row.get("usage") or {}).get(key)


def _params(row: dict[str, Any], key: str) -> Any:
    return (row.get("parameters") or {}).get(key)


def _first_vote(votes: list[dict[str, Any]]) -> dict[str, Any]:
    for v in votes:
        if isinstance(v, dict) and not v.get("error"):
            return v
    return votes[0] if votes and isinstance(votes[0], dict) else {}


def _merge_row(
    ans: dict[str, Any],
    ev: dict[str, Any] | None,
    votes: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    ev = ev or {}
    votes = votes or []
    vote = _first_vote(votes)
    criterias = vote.get("criterias") or {}
    completeness_crit = criterias.get("completeness") or {}
    correctness_crit = criterias.get("correctness") or {}
    outcome = ev.get("outcome")
    outcome = outcome if isinstance(outcome, dict) else {}
    correctness_outcome = outcome.get("correctness") or {}
    completeness_outcome = outcome.get("completeness") or {}
    context_blocks = ev.get("contextBlocks")
    return {
        # ── from answers ────────────────────────────────────────────────────
        "experimentId": _ans(ans, "experimentId"),
        "runId": _ans(ans, "runId"),
        "instanceId": _ans(ans, "instanceId"),
        "format": _ans(ans, "format"),
        "questionId": _ans(ans, "questionId"),
        "modelId": _ans(ans, "modelId"),
        "modelName": _ans(ans, "model") or _ans(ans, "modelName"),
        "tags": ",".join(_ans(ans, "questionTags") or []),
        "index": _ans(ans, "repeatIndex"),
        "strategy": _ans(ans, "strategy"),
        "temperature": _params(ans, "temperature"),
        "inputTokens": _usage(ans, "inputTokens"),
        "outputTokens": _usage(ans, "outputTokens"),
        "totalTokens": _usage(ans, "totalTokens"),
        "cachedInputTokens": _usage(ans, "cachedInputTokens"),
        "cachedReadTokens": _usage(ans, "cacheReadInputTokens"),
        "status": _ans(ans, "status"),
        "modelCalls": _metrics(ans, "modelCalls"),
        "toolCalls": _metrics(ans, "toolCalls"),
        "mcpToolCalls": _metrics(ans, "mcpToolCalls"),
        "answer": _ans(ans, "answer"),
        "errorMessage": _ans(ans, "errorMessage"),
        "modelDuration": _metrics(ans, "modelDurationMs"),
        "reservedTokens": _metrics(ans, "reservedTokens"),
        "toolDurationMs": _metrics(ans, "toolDurationMs"),
        "totalDurationMs": _metrics(ans, "totalDurationMs"),
        # ── from evals ──────────────────────────────────────────────────────
        "completeness": completeness_outcome.get("rating"),
        "completeness_agreement": completeness_outcome.get("agreement"),
        "correctness": correctness_outcome.get("rating"),
        "correctness_agreement": correctness_outcome.get("agreement"),
        "evaluationDurationMs": ev.get("evaluationDurationMs"),
        "evaluationInputTokens": ev.get("evaluationInputTokens"),
        "evaluationOutputTokens": ev.get("evaluationOutputTokens"),
        "evaluationMethod": ev.get("evaluationMethod"),
        "judgeCount": ev.get("judgeCount"),
        "evaluationStatus": ev.get("status"),
        "contextBlocks": (
            ",".join(context_blocks) if isinstance(context_blocks, list) else context_blocks
        ),
        # ── from judge_votes (first non-error judge) ─────────────────────────
        "judge": (
            f"{vote.get('provider')}/{vote.get('model')}"
            if vote.get("provider") or vote.get("model")
            else None
        ),
        "judgeId": vote.get("judgeId"),
        "judgeModel": vote.get("model"),
        "completeness_justification": completeness_crit.get("justification"),
        "correctness_justification": correctness_crit.get("justification"),
    }


_CSV_FIELDS = [
    "experimentId", "runId", "instanceId", "format", "questionId",
    "modelId", "modelName", "tags", "index", "strategy", "temperature",
    "inputTokens", "outputTokens", "totalTokens", "cachedInputTokens", "cachedReadTokens",
    "status", "modelCalls", "toolCalls", "mcpToolCalls",
    "answer", "errorMessage", "modelDuration", "reservedTokens", "toolDurationMs", "totalDurationMs",
    "completeness", "completeness_agreement", "correctness", "correctness_agreement",
    "completeness_justification", "correctness_justification",
    "judge", "judgeId", "judgeModel",
    "evaluationDurationMs", "evaluationInputTokens", "evaluationOutputTokens",
    "evaluationMethod", "judgeCount", "evaluationStatus", "contextBlocks",
]


# ---------------------------------------------------------------------------
# --by filter parsing
# ---------------------------------------------------------------------------

_BY_KEY_MAP = {
    "model": "model",
    "strategy": "strategy",
    "format": "format",
    "instance": "instance",
}


def _apply_by_filters(
    rows: list[dict[str, Any]],
    by: list[str],
) -> list[dict[str, Any]]:
    if not by:
        return rows
    filters: dict[str, set[str]] = {}
    for token in by:
        if "=" not in token:
            raise ValueError(
                f"Invalid --by value '{token}'. Expected format: key=value "
                f"(valid keys: {', '.join(_BY_KEY_MAP)})"
            )
        key, _, value = token.partition("=")
        key = key.strip().lower()
        if key not in _BY_KEY_MAP:
            raise ValueError(
                f"Unknown --by key '{key}'. Valid keys: {', '.join(_BY_KEY_MAP)}"
            )
        filters.setdefault(key, set()).add(value.strip())

    result = []
    for row in rows:
        if "model" in filters:
            model_id = row.get("modelId") or ""
            model_name = row.get("model") or row.get("modelName") or ""
            if not (filters["model"] & {model_id, model_name}):
                continue
        if "strategy" in filters and row.get("strategy") not in filters["strategy"]:
            continue
        if "format" in filters and row.get("format") not in filters["format"]:
            continue
        if "instance" in filters and row.get("instanceId") not in filters["instance"]:
            continue
        result.append(row)
    return result


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [dict(item) for item in read_jsonl(path)]


def _build_eval_index(evals: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for ev in evals:
        run_id = str(ev.get("runId") or "")
        if run_id:
            index[run_id] = ev
    return index


def _build_votes_index(votes: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = {}
    for v in votes:
        run_id = str(v.get("runId") or "")
        if run_id:
            index.setdefault(run_id, []).append(v)
    return index


# ---------------------------------------------------------------------------
# Detail view (--id)
# ---------------------------------------------------------------------------

def _print_run_detail(
    run_id: str,
    answers: list[dict[str, Any]],
    evals_index: dict[str, dict[str, Any]],
    votes_index: dict[str, list[dict[str, Any]]],
) -> int:
    ans = next((r for r in answers if str(r.get("runId") or "") == run_id), None)
    if ans is None:
        print(f"Run '{run_id}' not found in answers.")
        return 1

    ev = evals_index.get(run_id)
    votes = votes_index.get(run_id, [])
    merged = _merge_row(ans, ev, votes)

    metadata = ans.get("metadata") or {}
    parameters = ans.get("parameters") or {}
    metrics = ans.get("metricsSummary") or {}
    timing = ans.get("timing") or {}

    detail: dict[str, Any] = {
        "runId": merged["runId"],
        "experimentId": merged["experimentId"],
        "questionId": merged["questionId"],
        "instanceId": merged["instanceId"],
        "model": {"id": merged["modelId"], "name": merged["modelName"]},
        "strategy": merged["strategy"],
        "format": merged["format"],
        "index": merged["index"],
        "tags": (ans.get("questionTags") or []),
        "status": merged["status"],
        "errorMessage": merged["errorMessage"],
        "answer": merged["answer"],
        "timing": timing,
        "usage": ans.get("usage") or {},
        "metrics": metrics,
        "parameters": parameters,
        "metadata": metadata,
        "evaluation": ev if ev is not None else None,
        "judgeVotes": votes if votes else None,
    }
    print(json.dumps(detail, indent=2, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({f: row.get(f) for f in _CSV_FIELDS})


# ---------------------------------------------------------------------------
# export command
# ---------------------------------------------------------------------------

def export_command(
    evals: str | None = None,
    *,
    format: str = "csv",
    output: str | None = None,
    verbose: bool = False,
    selector: RunSelector | None = None,
    by: list[str] | None = None,
    run_id: str | None = None,
) -> int:
    if format not in _SUPPORTED_FORMATS:
        print(f"Unsupported format '{format}'. Supported: {', '.join(_SUPPORTED_FORMATS)}")
        return 1

    source = Path(evals).resolve() if evals else Path("evals.jsonl").resolve()
    source_root = source.parent
    logger = PhaseLogger(verbose=verbose)

    answers_path = source_root / "answers.jsonl"
    if not answers_path.exists():
        print(f"Answers file not found: {answers_path}. Run 'copa query' first.")
        return 1

    answers = _load_jsonl(answers_path)

    evals_list = _load_jsonl(source) if source.exists() else []
    evals_index = _build_eval_index(evals_list)

    votes_path = source_root / "judge_votes.jsonl"
    votes_list = _load_jsonl(votes_path)
    votes_index = _build_votes_index(votes_list)

    logger.phase(
        "LOAD", "Files loaded",
        answers=len(answers), evals=len(evals_list), votes=len(votes_list),
    )

    if run_id is not None:
        return _print_run_detail(run_id, answers, evals_index, votes_index)

    active_selector = selector or RunSelector()
    answers = [r for r in answers if matches_run_result(r, active_selector)]

    try:
        answers = _apply_by_filters(answers, by or [])
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    run_id_key = lambda ans: str(ans.get("runId") or "")
    merged = [
        _merge_row(ans, evals_index.get(run_id_key(ans)), votes_index.get(run_id_key(ans)))
        for ans in answers
    ]

    if format == "csv":
        out_path = Path(output).resolve() if output else source_root / "results.csv"
        _write_csv(merged, out_path)
        print(f"Exported {len(merged)} row(s) → {out_path}")

    return 0
