from __future__ import annotations

import hashlib


def context_fingerprint(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def build_inline_prompt_cache_key(
    *,
    model_name: str,
    instance_id: str,
    format_name: str,
    context: str,
) -> str:
    digest = hashlib.sha256(
        f"{model_name}|{instance_id}|{format_name}|{context_fingerprint(context)}".encode("utf-8")
    ).hexdigest()[:32]
    return f"inl:{format_name}:{digest}"


def build_judge_prompt_cache_key(
    *,
    model_name: str,
    instance_id: str,
    context: str,
) -> str:
    digest = hashlib.sha256(
        f"{model_name}|{instance_id}|{context_fingerprint(context)}".encode("utf-8")
    ).hexdigest()[:32]
    return f"jud:ctx:{digest}"
