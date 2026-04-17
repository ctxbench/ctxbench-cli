from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.models import Experiment, RunMetadata, RunSpec
from copa.dataset.provider import DatasetProvider
from copa.util.artifacts import build_short_ids, canonical_run_identity
from copa.util.env import apply_lattes_mcp_env_overrides, resolve_env_placeholders


def resolve_params(experiment: Experiment, model_name: str) -> dict[str, Any]:
    common = dict(experiment.params.common)
    model_specific = experiment.params.models.get(model_name, {})
    params = resolve_env_placeholders({**common, **model_specific, "model_name": model_name})
    return apply_lattes_mcp_env_overrides(params)


def resolve_models(experiment: Experiment) -> list[dict[str, str]]:
    models: list[dict[str, str]] = []
    for item in experiment.factors.get("model", []):
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        name = item.get("name")
        if isinstance(provider, str) and isinstance(name, str):
            models.append({"provider": provider, "name": name})
    return models


def generate_runspecs(
    experiment: Experiment,
    base_dir: str | Path,
    *,
    experiment_path: str | Path | None = None,
) -> list[RunSpec]:
    provider = DatasetProvider.from_experiment(experiment, base_dir)
    questions = provider.list_question_ids()
    models = resolve_models(experiment)
    strategies = experiment.factors.get("strategy", [])
    formats = experiment.factors.get("format", [])
    output_root = str((Path(base_dir) / experiment.output).resolve())
    draft_specs: list[dict[str, Any]] = []
    for question_id in questions:
        for format_name in formats:
            for context_id in provider.list_context_ids(format_name):
                for model in models:
                    provider_name = model["provider"]
                    model_name = model["name"]
                    for strategy_name in strategies:
                        params = resolve_params(experiment, model_name)
                        for repeat_index in range(1, experiment.execution.repeats + 1):
                            canonical_id = canonical_run_identity(
                                experiment.id,
                                question_id,
                                context_id,
                                provider_name,
                                model_name,
                                strategy_name,
                                format_name,
                                repeat_index,
                            )
                            draft_specs.append(
                                {
                                    "canonical_id": canonical_id,
                                    "experimentId": experiment.id,
                                    "dataset": provider.dataset_paths,
                                    "experimentPath": str(Path(experiment_path).resolve())
                                    if experiment_path
                                    else None,
                                    "questionId": question_id,
                                    "contextId": context_id,
                                    "provider": provider_name,
                                    "modelName": model_name,
                                    "strategy": strategy_name,
                                    "format": format_name,
                                    "params": params,
                                    "repeatIndex": repeat_index,
                                    "outputRoot": output_root,
                                    "evaluationEnabled": experiment.evaluation.enabled,
                                    "trace": experiment.trace,
                                }
                            )

    run_ids = build_short_ids([item["canonical_id"] for item in draft_specs])
    runspecs: list[RunSpec] = []
    for item, run_id in zip(draft_specs, run_ids):
        runspecs.append(
            RunSpec(
                id=run_id,
                runId=run_id,
                experimentId=item["experimentId"],
                dataset=item["dataset"],
                experimentPath=item["experimentPath"],
                questionId=item["questionId"],
                contextId=item["contextId"],
                provider=item["provider"],
                modelName=item["modelName"],
                strategy=item["strategy"],
                format=item["format"],
                params=item["params"],
                repeatIndex=item["repeatIndex"],
                outputRoot=item["outputRoot"],
                evaluationEnabled=item["evaluationEnabled"],
                trace=item["trace"],
                metadata=RunMetadata(
                    canonicalId=item["canonical_id"],
                    questionId=item["questionId"],
                    contextId=item["contextId"],
                    provider=item["provider"],
                    modelName=item["modelName"],
                    strategy=item["strategy"],
                    format=item["format"],
                    repeatIndex=item["repeatIndex"],
                ),
            )
        )
    return runspecs
