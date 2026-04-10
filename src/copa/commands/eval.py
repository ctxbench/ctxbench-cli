from __future__ import annotations

from pathlib import Path

from copa.benchmark.evaluation import evaluate_result
from copa.benchmark.models import RunResult
from copa.benchmark.results import write_result_files, write_results_jsonl
from copa.dataset.provider import DatasetProvider
from copa.util.artifacts import build_short_ids, canonical_identity_from_run, evalresult_filename
from copa.util.fs import load_json
from copa.util.jsonl import read_jsonl
from copa.util.logging import PhaseLogger, ProgressTracker


def load_results(path: str) -> list[RunResult]:
    source = Path(path)
    if source.is_dir():
        return [RunResult.model_validate(load_json(item)) for item in sorted(source.glob("*.json"))]
    if source.suffix == ".jsonl":
        return [RunResult.model_validate(item) for item in read_jsonl(source)]
    return [RunResult.model_validate(load_json(source))]


def eval_command(
    path: str,
    out_dir: str | None = None,
    jsonl_path: str | None = None,
    *,
    verbose: bool = False,
    progress: bool = False,
) -> int:
    logger = PhaseLogger(verbose=verbose)
    logger.phase("LOAD", "Loading run results", path=path)
    results = load_results(path)
    progress_tracker = ProgressTracker(total=len(results), enabled=progress)
    logger.progress = progress_tracker
    logger.phase("LOAD", "Run result loading completed", runs=len(results))
    logger.phase("PLAN", "Starting batch processing", input=path, discoveredRuns=len(results))
    short_ids = build_short_ids([canonical_identity_from_run(result) for result in results])
    progress_tracker.start()
    for result, short_id in zip(results, short_ids):
        provider = DatasetProvider.from_dataset(result.dataset)
        evaluation_type = provider.get_question(result.questionId).evaluationType
        logger.phase(
            "EVALUATE",
            "Starting evaluation",
            run=short_id,
            question=result.questionId,
            evaluation=evaluation_type,
        )
        result.evaluation = evaluate_result(result, provider)
        logger.phase(
            "EVALUATE",
            "Evaluation completed",
            run=short_id,
            question=result.questionId,
            evaluation=result.evaluation.evaluator or evaluation_type,
            score=result.evaluation.passed,
        )
        progress_tracker.advance()

    if results:
        output_root = (
            Path(results[0].outputRoot).resolve()
            if results[0].outputRoot
            else Path(results[0].dataset.contexts).resolve().parent.parent / "outputs"
        )
        default_dir = output_root / results[0].experimentId / "eval"
        target_dir = Path(out_dir).resolve() if out_dir else default_dir
        for result, short_id in zip(results, short_ids):
            logger.phase(
                "WRITE",
                "Writing artifact",
                run=short_id,
                path=target_dir / evalresult_filename(result.experimentId, short_id),
            )
        result_paths = write_result_files(results, target_dir, artifact_kind="evaluation")
        for path_item, short_id in zip(result_paths, short_ids):
            logger.phase("WRITE", "Artifact written", run=short_id, path=path_item)
            logger.phase("DONE", "Completed successfully", run=short_id)
        if jsonl_path:
            write_results_jsonl(results, jsonl_path)
            print(f"Wrote {len(results)} evaluated result(s) to {target_dir} and {jsonl_path}")
        else:
            print(f"Wrote {len(results)} evaluated result(s) to {target_dir}")
    else:
        print("No results found.")
    return 0
