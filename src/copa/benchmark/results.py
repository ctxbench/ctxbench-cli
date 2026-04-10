from __future__ import annotations

from pathlib import Path
from typing import Iterable

from copa.benchmark.models import RunResult
from copa.util.artifacts import (
    build_short_ids,
    canonical_identity_from_run,
    evalresult_filename,
    runresult_filename,
)
from copa.util.fs import write_json
from copa.util.jsonl import write_jsonl


def write_result_files(
    results: Iterable[RunResult],
    out_dir: str | Path,
    *,
    artifact_kind: str = "result",
) -> list[Path]:
    result_list = list(results)
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    identities = [canonical_identity_from_run(result) for result in result_list]
    short_ids = build_short_ids(identities)
    paths: list[Path] = []
    for result, short_id in zip(result_list, short_ids):
        filename = (
            evalresult_filename(result.experimentId, short_id)
            if artifact_kind == "evaluation"
            else runresult_filename(result.experimentId, short_id)
        )
        path = target / filename
        write_json(path, result.model_dump(mode="json"))
        paths.append(path)
    return paths


def write_results_jsonl(results: Iterable[RunResult], path: str | Path) -> Path:
    result_list = list(results)
    write_jsonl(path, [result.model_dump(mode="json") for result in result_list])
    return Path(path)
