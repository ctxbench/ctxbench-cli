from __future__ import annotations

from pathlib import Path
from typing import Iterable

from copa.benchmark.models import RunResult
from copa.util.fs import write_json
from copa.util.jsonl import write_jsonl


def write_result_files(results: Iterable[RunResult], out_dir: str | Path) -> list[Path]:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for result in results:
        path = target / f"{result.runId}.json"
        write_json(path, result.model_dump(mode="json"))
        paths.append(path)
    return paths


def write_results_jsonl(results: Iterable[RunResult], path: str | Path) -> Path:
    result_list = list(results)
    write_jsonl(path, [result.model_dump(mode="json") for result in result_list])
    return Path(path)
