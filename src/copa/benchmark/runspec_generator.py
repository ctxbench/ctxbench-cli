from __future__ import annotations

from pathlib import Path
from typing import Any

from copa.benchmark.models import Experiment, RunSpec
from copa.dataset.provider import DatasetProvider
from copa.util.ids import runspec_id


def resolve_params(experiment: Experiment, model_name: str) -> dict[str, Any]:
    common = dict(experiment.params.common)
    model_specific = experiment.params.models.get(model_name, {})
    return {**common, **model_specific, "model_name": model_name}


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


def generate_runspecs(experiment: Experiment, base_dir: str | Path) -> list[RunSpec]:
    provider = DatasetProvider.from_experiment(experiment, base_dir)
    questions = provider.list_question_ids()
    models = resolve_models(experiment)
    strategies = experiment.factors.get("strategy", [])
    formats = experiment.factors.get("format", [])
    output_root = str((Path(base_dir) / experiment.execution.output).resolve())

    runspecs: list[RunSpec] = []
    for question_id in questions:
        for format_name in formats:
            for context_id in provider.list_context_ids(format_name):
                for model in models:
                    provider_name = model["provider"]
                    model_name = model["name"]
                    for strategy_name in strategies:
                        params = resolve_params(experiment, model_name)
                        for repeat_index in range(1, experiment.execution.repeats + 1):
                            runspecs.append(
                                RunSpec(
                                    id=runspec_id(
                                        experiment.id,
                                        question_id,
                                        context_id,
                                        provider_name,
                                        model_name,
                                        strategy_name,
                                        format_name,
                                        repeat_index,
                                    ),
                                    experimentId=experiment.id,
                                    dataset=provider.dataset_paths,
                                    questionId=question_id,
                                    contextId=context_id,
                                    provider=provider_name,
                                    modelName=model_name,
                                    strategy=strategy_name,
                                    format=format_name,
                                    params=params,
                                    repeatIndex=repeat_index,
                                    outputRoot=output_root,
                                    evaluationEnabled=experiment.evaluation.enabled,
                                    trace=experiment.trace,
                                )
                            )
    return runspecs
