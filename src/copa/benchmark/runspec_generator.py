from __future__ import annotations

from pathlib import Path

from copa.benchmark.models import Experiment, RunSpec
from copa.dataset.provider import DatasetProvider
from copa.util.ids import runspec_id


def resolve_params(experiment: Experiment, model_name: str) -> dict:
    common = dict(experiment.params.common)
    model_specific = experiment.params.model.get(model_name, {})
    return {**common, **model_specific}


def generate_runspecs(experiment: Experiment, base_dir: str | Path) -> list[RunSpec]:
    provider = DatasetProvider.from_experiment(experiment, base_dir)
    questions = provider.list_question_ids()
    models = experiment.factors.get("model", [])
    strategies = experiment.factors.get("strategy", [])
    formats = experiment.factors.get("format", [])
    output_root = str((Path(base_dir) / experiment.execution.output).resolve())

    runspecs: list[RunSpec] = []
    for question_id in questions:
        for format_name in formats:
            for context_id in provider.list_context_ids(format_name):
                for model_name in models:
                    for strategy_name in strategies:
                        params = resolve_params(experiment, model_name)
                        for repeat_index in range(1, experiment.execution.repeats + 1):
                            runspecs.append(
                                RunSpec(
                                    id=runspec_id(
                                        experiment.id,
                                        question_id,
                                        context_id,
                                        model_name,
                                        strategy_name,
                                        format_name,
                                        repeat_index,
                                    ),
                                    experimentId=experiment.id,
                                    dataset=provider.dataset_paths,
                                    questionId=question_id,
                                    contextId=context_id,
                                    model=model_name,
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
