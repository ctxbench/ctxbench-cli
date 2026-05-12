from __future__ import annotations

from ctxbench.benchmark.evaluation import EvaluationJudgeInfo, EvaluationTrace
from ctxbench.benchmark.models import EvaluationModelConfig


class FakeJudge:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def judge_request(self, **kwargs: object) -> tuple[dict[str, object], EvaluationJudgeInfo, EvaluationTrace]:
        self.calls.append(dict(kwargs))
        config = kwargs["config"]
        assert isinstance(config, EvaluationModelConfig)
        payload = {
            "correctness": {
                "rating": "meets",
                "justification": "Answer matches the profile context.",
            },
            "completeness": {
                "rating": "meets",
                "justification": "Answer fully addresses the question.",
            },
        }
        info = EvaluationJudgeInfo(
            used=True,
            role="judge",
            provider=config.provider,
            model=config.model,
            inputTokens=9,
            outputTokens=6,
            durationMs=5,
        )
        return payload, info, EvaluationTrace()
