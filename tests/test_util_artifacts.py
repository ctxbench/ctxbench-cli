from __future__ import annotations

from ctxbench.util.artifacts import (
    canonical_trial_identity,
    evaluation_filename,
    response_filename,
    trialspec_filename,
)
from ctxbench.util.ids import trialspec_id


def test_canonical_trial_identity_uses_target_task_and_repetition_terms():
    identity = canonical_trial_identity(
        experiment_id="exp-1",
        task_id="q_year",
        instance_id="cv-demo",
        provider="mock",
        model_name="mock-a",
        strategy="inline",
        format_name="json",
        repetition=2,
    )

    assert identity == "exp-1|q_year|cv-demo|mock|mock-a|inline|json|2"


def test_trialspec_id_uses_target_identity_builder():
    identity = trialspec_id(
        experiment_id="exp-1",
        task_id="q_summary",
        context_id="cv-demo",
        provider="mock",
        model_name="mock-a",
        strategy="remote_mcp",
        format_name="json",
        repetition=1,
    )

    assert identity == "exp-1|q_summary|cv-demo|mock|mock-a|remote_mcp|json|1"


def test_target_filename_helpers_preserve_existing_prefixes():
    assert trialspec_filename("exp demo", "trial-1") == "rs_exp_demo_trial-1.json"
    assert response_filename("exp demo", "trial-1") == "rr_exp_demo_trial-1.json"
    assert evaluation_filename("exp demo", "trial-1") == "re_exp_demo_trial-1.json"
