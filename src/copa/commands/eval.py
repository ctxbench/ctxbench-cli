from __future__ import annotations

from pathlib import Path

from copa.benchmark.evaluation import evaluate_result
from copa.benchmark.models import RunResult
from copa.benchmark.results import write_result_files, write_results_jsonl
from copa.dataset.provider import DatasetProvider
from copa.util.fs import load_json
from copa.util.jsonl import read_jsonl


def load_results(path: str) -> list[RunResult]:
    source = Path(path)
    if source.is_dir():
        return [RunResult.model_validate(load_json(item)) for item in sorted(source.glob("*.json"))]
    if source.suffix == ".jsonl":
        return [RunResult.model_validate(item) for item in read_jsonl(source)]
    return [RunResult.model_validate(load_json(source))]


def eval_command(path: str, out_dir: str | None = None, jsonl_path: str | None = None) -> int:
    results = load_results(path)
    for result in results:
        provider = DatasetProvider.from_dataset(result.dataset)
        result.evaluation = evaluate_result(result, provider)

    if results:
        output_root = (
            Path(results[0].outputRoot).resolve()
            if results[0].outputRoot
            else Path(results[0].dataset.contexts).resolve().parent.parent / "outputs"
        )
        default_dir = output_root / results[0].experimentId / "eval"
        target_dir = Path(out_dir).resolve() if out_dir else default_dir
        write_result_files(results, target_dir)
        if jsonl_path:
            write_results_jsonl(results, jsonl_path)
            print(f"Wrote {len(results)} evaluated result(s) to {target_dir} and {jsonl_path}")
        else:
            print(f"Wrote {len(results)} evaluated result(s) to {target_dir}")
    else:
        print("No results found.")
    return 0
