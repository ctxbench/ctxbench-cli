from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from ctxbench.util.fs import write_text_atomic


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        f"{json.dumps(row, sort_keys=True, ensure_ascii=False)}\n"
        for row in rows
    )
    write_text_atomic(target, text)


def append_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    existing = read_jsonl(target) if target.exists() else []
    existing.extend(dict(row) for row in rows)
    write_jsonl(target, existing)
