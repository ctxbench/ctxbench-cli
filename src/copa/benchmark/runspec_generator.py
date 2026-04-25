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
    scoped_questions = set(experiment.scope.questions)
    scoped_instances = set(experiment.scope.instances)
    questions = [
        question_id for question_id in provider.list_question_ids()
        if not scoped_questions or question_id in scoped_questions
    ]
    instance_ids = [
        instance_id for instance_id in provider.list_instance_ids()
        if not scoped_instances or instance_id in scoped_instances
    ]
    models = resolve_models(experiment)
    strategies = experiment.factors.get("strategy", [])
    formats = experiment.factors.get("format", [])
    output_root = str((Path(base_dir) / experiment.output).resolve())
    draft_specs: list[dict[str, Any]] = []
    for instance_id in instance_ids:
        available_questions = set(provider.list_question_ids_for_instance(instance_id))
        for question_id in questions:
            if question_id not in available_questions:
                continue
            question = provider.get_question(question_id)
            for format_name in formats:
                for model in models:
                    provider_name = model["provider"]
                    model_name = model["name"]
                    for strategy_name in strategies:
                        params = resolve_params(experiment, model_name)
                        for repeat_index in range(1, experiment.execution.repeats + 1):
                            canonical_id = canonical_run_identity(
                                experiment.id,
                                question_id,
                                instance_id,
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
                                    "instanceId": instance_id,
                                    "provider": provider_name,
                                    "modelName": model_name,
                                    "strategy": strategy_name,
                                    "format": format_name,
                                    "params": params,
                                    "repeatIndex": repeat_index,
                                    "outputRoot": output_root,
                                    "evaluationEnabled": experiment.evaluation.enabled,
                                    "trace": experiment.trace,
                                    "questionTags": list(question.tags),
                                    "validationType": question.validation.type,
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
                instanceId=item["instanceId"],
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
                    instanceId=item["instanceId"],
                    provider=item["provider"],
                    modelName=item["modelName"],
                    strategy=item["strategy"],
                    format=item["format"],
                    repeatIndex=item["repeatIndex"],
                    questionTags=item["questionTags"],
                    validationType=item["validationType"],
                ),
            )
        )
    return runspecs
