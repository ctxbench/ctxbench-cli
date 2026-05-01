from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.evaluation import export_evaluation_rows_csv
from copa.benchmark.selectors import RunSelector, matches_run_result
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger


_SUPPORTED_FORMATS = ("csv",)


def export_command(
    evals: str | None = None,
    *,
    format: str = "csv",
    output: str | None = None,
    verbose: bool = False,
    selector: RunSelector | None = None,
) -> int:
    if format not in _SUPPORTED_FORMATS:
        print(f"Unsupported format '{format}'. Supported: {', '.join(_SUPPORTED_FORMATS)}")
        return 1

    source = Path(evals).resolve() if evals else Path("evals.jsonl").resolve()
    logger = PhaseLogger(verbose=verbose)

    if not source.exists():
        print(f"Evaluations file not found: {source}. Run 'copa eval' first.")
        return 1

    rows: list[dict[str, Any]] = [dict(item) for item in read_jsonl(source)]

    active_selector = selector or RunSelector()
    if any([
        active_selector.model, active_selector.provider, active_selector.instance,
        active_selector.question, active_selector.strategy, active_selector.format,
        active_selector.status, active_selector.ids,
        active_selector.not_model, active_selector.not_provider,
    ]):
        rows = [r for r in rows if matches_run_result(r, active_selector)]

    logger.phase("LOAD", "Evaluations loaded", total=len(rows), path=str(source))

    if format == "csv":
        if output:
            out_path = Path(output).resolve()
        else:
            out_path = source.with_suffix(".csv")
        export_evaluation_rows_csv(rows, str(out_path))
        print(f"Exported {len(rows)} row(s) → {out_path}")

    return 0
