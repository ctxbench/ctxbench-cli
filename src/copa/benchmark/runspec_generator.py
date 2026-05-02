from __future__ import annotations

from pathlib import Path
import re
from typing import Any, Callable

from copa.benchmark.models import Experiment, MODEL_ID_PATTERN, RunMetadata, RunSpec
from copa.dataset.provider import DatasetProvider
from copa.util.artifacts import build_short_ids, canonical_run_identity
from copa.util.env import apply_lattes_mcp_env_overrides, resolve_env_placeholders

QUESTION_TEMPLATE_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def resolve_params(experiment: Experiment, model_name: str, model_id: str | None = None) -> dict[str, Any]:
    common = dict(experiment.params.common)
    if model_id and experiment.models and model_id in experiment.models:
        model_specific = dict(experiment.models[model_id].params)
    else:
        model_specific = experiment.params.models.get(model_name, {})
    params = resolve_env_placeholders({**common, **model_specific, "model_name": model_name})
    return apply_lattes_mcp_env_overrides(params)


def resolve_models(experiment: Experiment) -> list[dict[str, str]]:
    if experiment.models:
        # New format: factors.model is a list of string IDs referencing experiment.models
        models: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for model_id in experiment.factors.get("model", []):
            if not isinstance(model_id, str):
                continue
            if model_id in seen_ids:
                raise ValueError(f"Duplicate model id in experiment factors.model: {model_id}")
            seen_ids.add(model_id)
            entry = experiment.models[model_id]
            models.append({"id": model_id, "provider": entry.provider, "name": entry.name})
        return models

    # Old format: factors.model is a list of objects with provider/name
    old_models: list[dict[str, str]] = []
    seen_ids_old: set[str] = set()
    for item in experiment.factors.get("model", []):
        if not isinstance(item, dict):
            continue
        provider = item.get("provider")
        name = item.get("name")
        if isinstance(provider, str) and isinstance(name, str):
            raw_model_id = item.get("id")
            model_id = raw_model_id if raw_model_id is not None else name
            if not isinstance(model_id, str) or not model_id.strip():
                raise ValueError("Experiment factors.model[].id must be a non-empty string when provided.")
            if raw_model_id is not None and not MODEL_ID_PATTERN.match(model_id):
                raise ValueError("Experiment factors.model[].id must contain only letters, numbers, underscore, dot, or hyphen.")
            if model_id in seen_ids_old:
                raise ValueError(f"Duplicate model id in experiment factors.model: {model_id}")
            seen_ids_old.add(model_id)
            old_models.append({"id": model_id, "provider": provider, "name": name})
    return old_models


def effective_formats_for_strategy(strategy_name: str, formats: list[Any]) -> list[str]:
    resolved_formats = [str(item) for item in formats if isinstance(item, str) and item.strip()]
    if strategy_name in {"local_function", "local_mcp", "mcp"}:
        return ["json"]
    return resolved_formats


def generate_runspecs(
    experiment: Experiment,
    base_dir: str | Path,
    *,
    experiment_path: str | Path | None = None,
    on_warning: Callable[..., None] | None = None,
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
        for question_id in questions:
            question = provider.get_question(question_id)
            question_instance = provider.get_question_instance(question_id, instance_id)
            parameters = dict(question_instance.parameters) if question_instance is not None else {}
            rendered_question = render_question_template(
                question.question,
                parameters,
                on_warning=on_warning,
                question_id=question_id,
                instance_id=instance_id,
            )
            for model in models:
                provider_name = model["provider"]
                model_id = model["id"]
                model_name = model["name"]
                for strategy_name in strategies:
                    for format_name in effective_formats_for_strategy(strategy_name, formats):
                        params = resolve_params(experiment, model_name, model_id=model_id)
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
                                    "question": rendered_question,
                                    "questionTemplate": question.question,
                                    "instanceId": instance_id,
                                    "provider": provider_name,
                                    "modelId": model_id,
                                    "modelName": model_name,
                                    "strategy": strategy_name,
                                    "format": format_name,
                                    "params": params,
                                    "repeatIndex": repeat_index,
                                    "outputRoot": output_root,
                                    "evaluationEnabled": experiment.evaluation.enabled,
                                    "trace": experiment.trace,
                                    "artifacts": experiment.artifacts,
                                    "questionTags": list(question.tags),
                                    "validationType": question.validation.type,
                                    "contextBlock": list(question.contextBlock),
                                    "parameters": parameters,
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
                question=item["question"],
                questionTemplate=item["questionTemplate"],
                questionTags=item["questionTags"],
                validationType=item["validationType"],
                contextBlock=item["contextBlock"],
                parameters=item["parameters"],
                instanceId=item["instanceId"],
                provider=item["provider"],
                modelId=item["modelId"],
                modelName=item["modelName"],
                strategy=item["strategy"],
                format=item["format"],
                params=item["params"],
                repeatIndex=item["repeatIndex"],
                outputRoot=item["outputRoot"],
                evaluationEnabled=item["evaluationEnabled"],
                trace=item["trace"],
                artifacts=item["artifacts"],
                metadata=RunMetadata(
                    canonicalId=item["canonical_id"],
                    questionId=item["questionId"],
                    instanceId=item["instanceId"],
                    provider=item["provider"],
                    modelId=item["modelId"],
                    modelName=item["modelName"],
                    strategy=item["strategy"],
                    format=item["format"],
                    repeatIndex=item["repeatIndex"],
                    questionTags=item["questionTags"],
                    validationType=item["validationType"],
                    parameters=item["parameters"],
                ),
            )
        )
    return runspecs


def render_question_template(
    question_template: str,
    parameters: dict[str, Any],
    *,
    on_warning: Callable[..., None] | None = None,
    question_id: str,
    instance_id: str,
) -> str:
    placeholders = QUESTION_TEMPLATE_PATTERN.findall(question_template)
    if not placeholders:
        if parameters and on_warning is not None:
            for key in sorted(parameters):
                on_warning(
                    "Unused question parameter; ignoring",
                    questionId=question_id,
                    instanceId=instance_id,
                    parameter=key,
                )
        return question_template

    rendered = question_template
    for placeholder in placeholders:
        if placeholder not in parameters and on_warning is not None:
            on_warning(
                "Missing question parameter; substituting empty string",
                questionId=question_id,
                instanceId=instance_id,
                parameter=placeholder,
            )
        rendered = rendered.replace("{" + placeholder + "}", str(parameters.get(placeholder, "")))

    if on_warning is not None:
        for key in sorted(parameters):
            if key not in placeholders:
                on_warning(
                    "Unused question parameter; ignoring",
                    questionId=question_id,
                    instanceId=instance_id,
                    parameter=key,
                )
    return rendered
