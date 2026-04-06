from __future__ import annotations

from pathlib import Path

from copa.ai.engine import Engine
from copa.benchmark.executor import execute_runspec
from copa.benchmark.models import RunSpec
from copa.benchmark.results import write_result_files, write_results_jsonl
from copa.util.fs import load_json
from copa.util.jsonl import read_jsonl


def load_runspecs(path: str) -> list[RunSpec]:
    source = Path(path)
    if source.is_dir():
        return [RunSpec.model_validate(load_json(item)) for item in sorted(source.glob("*.json"))]
    if source.suffix == ".jsonl":
        return [RunSpec.model_validate(item) for item in read_jsonl(source)]
    return [RunSpec.model_validate(load_json(source))]


def run_command(path: str, out_dir: str | None = None, jsonl_path: str | None = None) -> int:
    runspecs = load_runspecs(path)
    engine = Engine()
    results = [execute_runspec(runspec, engine) for runspec in runspecs]

    if results:
        output_root = (
            Path(results[0].outputRoot).resolve()
            if results[0].outputRoot
            else Path(results[0].dataset.contexts).resolve().parent.parent / "outputs"
        )
        default_dir = output_root / results[0].experimentId / "results"
        target_dir = Path(out_dir).resolve() if out_dir else default_dir
        write_result_files(results, target_dir)
        if jsonl_path:
            write_results_jsonl(results, jsonl_path)
            print(f"Wrote {len(results)} result(s) to {target_dir} and {jsonl_path}")
        else:
            print(f"Wrote {len(results)} result(s) to {target_dir}")
    else:
        print("No runspecs found.")
    return 0
