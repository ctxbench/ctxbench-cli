from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RunSelector:
    provider: str | None = None
    model: str | None = None
    instance: str | None = None
    question: str | None = None
    strategy: str | None = None
    format: str | None = None
    repeat: int | None = None
    status: str | None = None
    exclude_provider: tuple[str, ...] = ()
    exclude_model: tuple[str, ...] = ()
    exclude_instance: tuple[str, ...] = ()
    exclude_question: tuple[str, ...] = ()
    exclude_strategy: tuple[str, ...] = ()
    exclude_format: tuple[str, ...] = ()
    exclude_repeat: tuple[int, ...] = ()
    exclude_status: tuple[str, ...] = ()


def matches_runspec(item: Any, selector: RunSelector) -> bool:
    return _matches_common(item, selector)


def matches_run_result(item: Any, selector: RunSelector) -> bool:
    if selector.status is not None and _field(item, "status") != selector.status:
        return False
    return _matches_common(item, selector)


def _matches_common(item: Any, selector: RunSelector) -> bool:
    if selector.provider is not None and _field(item, "provider") != selector.provider:
        return False
    if selector.model is not None and selector.model not in {_field(item, "modelId"), _field(item, "modelName")}:
        return False
    if selector.instance is not None and _field(item, "instanceId") != selector.instance:
        return False
    if selector.question is not None and _field(item, "questionId") != selector.question:
        return False
    if selector.strategy is not None and _field(item, "strategy") != selector.strategy:
        return False
    if selector.format is not None and _field(item, "format") != selector.format:
        return False
    if selector.repeat is not None and _field(item, "repeatIndex") != selector.repeat:
        return False
    if selector.exclude_provider and _field(item, "provider") in selector.exclude_provider:
        return False
    if selector.exclude_model and _field(item, "modelId") in selector.exclude_model:
        return False
    if selector.exclude_model and _field(item, "modelName") in selector.exclude_model:
        return False
    if selector.exclude_instance and _field(item, "instanceId") in selector.exclude_instance:
        return False
    if selector.exclude_question and _field(item, "questionId") in selector.exclude_question:
        return False
    if selector.exclude_strategy and _field(item, "strategy") in selector.exclude_strategy:
        return False
    if selector.exclude_format and _field(item, "format") in selector.exclude_format:
        return False
    if selector.exclude_repeat and _field(item, "repeatIndex") in selector.exclude_repeat:
        return False
    if selector.exclude_status and _field(item, "status") in selector.exclude_status:
        return False
    return True


def _field(item: Any, name: str) -> Any:
    if isinstance(item, dict):
        if name == "modelName" and "modelName" not in item:
            return item.get("model")
        return item.get(name)
    return getattr(item, name, None)
