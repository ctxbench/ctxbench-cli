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
    question_id: str,
    context: str,
    question: str,
) -> str:
    digest = hashlib.sha256(
        f"{model_name}|{instance_id}|{question_id}|{context_fingerprint(context)}|{context_fingerprint(question)}".encode(
            "utf-8"
        )
    ).hexdigest()[:32]
    return f"jud:{question_id[:8]}:{digest}"
