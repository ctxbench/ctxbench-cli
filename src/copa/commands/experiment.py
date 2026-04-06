from __future__ import annotations

from pathlib import Path

from copa.benchmark.experiment_loader import load_experiment
from copa.benchmark.runspec_generator import generate_runspecs
from copa.util.fs import ensure_dir, write_json
from copa.util.jsonl import write_jsonl


def validate_experiment(path: str) -> int:
    load_experiment(path)
    print(f"{path}: valid experiment")
    return 0


def expand_experiment(path: str, out_dir: str | None = None, jsonl_path: str | None = None) -> int:
    experiment = load_experiment(path)
    base_dir = Path(path).resolve().parent
    runspecs = generate_runspecs(experiment, base_dir)
    payloads = [runspec.model_dump(mode="json") for runspec in runspecs]

    output_root = Path(experiment.execution.output)
    default_dir = (base_dir / output_root / experiment.id / "runspecs").resolve()
    target_dir = Path(out_dir).resolve() if out_dir else default_dir
    ensure_dir(target_dir)

    for runspec in runspecs:
        write_json(target_dir / f"{runspec.id}.json", runspec.model_dump(mode="json"))

    if jsonl_path:
        write_jsonl(jsonl_path, payloads)
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir} and {jsonl_path}")
    else:
        print(f"Wrote {len(runspecs)} runspec(s) to {target_dir}")
    return 0
