from __future__ import annotations

import pytest

from ctxbench.benchmark import evaluation as evaluation_module
from ctxbench.benchmark import executor as executor_module

from .fake_judge import FakeJudge
from .fake_responder import FakeResponder


@pytest.fixture
def provider_free_lattes_runtime(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    responder = FakeResponder()
    judge = FakeJudge()
    
    def fake_execute(engine: object, request: object) -> object:
        return responder.execute(engine, request)

    monkeypatch.setattr(executor_module.Engine, "execute", fake_execute)
    monkeypatch.setattr(evaluation_module, "_judge_request", judge.judge_request)
    return {
        "responder": responder,
        "judge": judge,
    }
