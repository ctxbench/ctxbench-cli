from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO


def _format_field(value: object) -> str:
    text = str(value)
    if any(char.isspace() for char in text) or '"' in text:
        return '"' + text.replace('"', '\\"') + '"'
    return text


@dataclass
class ProgressTracker:
    total: int
    enabled: bool = False
    description: str = "Processing runs"
    stream: TextIO | None = None
    width: int = 24
    count: int = 0

    def __post_init__(self) -> None:
        self.enabled = self.enabled and self.total > 1
        if self.stream is None:
            self.stream = sys.stderr

    def start(self) -> None:
        if self.enabled:
            self._render()

    def advance(self) -> None:
        if not self.enabled:
            return
        self.count += 1
        self._render()
        if self.count >= self.total:
            self.stream.write("\n")
            self.stream.flush()

    def clear(self) -> None:
        if not self.enabled:
            return
        self.stream.write("\r" + (" " * 120) + "\r")
        self.stream.flush()

    def redraw(self) -> None:
        if self.enabled and self.count < self.total:
            self._render()

    def _render(self) -> None:
        ratio = 0 if self.total <= 0 else min(max(self.count / self.total, 0), 1)
        filled = int(self.width * ratio)
        bar = "█" * filled + " " * (self.width - filled)
        percent = int(ratio * 100)
        self.stream.write(
            f"\r{self.description}: {percent:>3}%|{bar}| {self.count}/{self.total}"
        )
        self.stream.flush()


class PhaseLogger:
    def __init__(
        self,
        *,
        verbose: bool = False,
        progress: ProgressTracker | None = None,
        stream: TextIO | None = None,
    ) -> None:
        self.verbose = verbose
        self.progress = progress
        self.stream = stream or sys.stderr

    def phase(self, label: str, message: str, **fields: object) -> None:
        if not self.verbose:
            return
        self._emit(label, message, fields)

    def error(self, message: str, **fields: object) -> None:
        self._emit("ERROR", message, fields)

    def warn(self, message: str, **fields: object) -> None:
        self._emit("WARN", message, fields)

    def _emit(self, label: str, message: str, fields: dict[str, object]) -> None:
        if self.progress is not None:
            self.progress.clear()
        context = " ".join(
            f"{key}={_format_field(value)}" for key, value in fields.items() if value is not None
        )
        suffix = f" {context}" if context else ""
        self.stream.write(f"[{label}]{suffix} {message}\n")
        self.stream.flush()
        if self.progress is not None:
            self.progress.redraw()
