from __future__ import annotations

from pathlib import Path


FORMAT_EXTENSIONS = {
    "json": ".json",
    "html": ".html",
    "xml": ".xml",
    "text": ".txt",
    "plain": ".txt",
    "txt": ".txt",
}


def extension_for_format(format_name: str) -> str:
    return FORMAT_EXTENSIONS.get(format_name, f".{format_name}")


def context_path(context_dir: str | Path, context_id: str, format_name: str) -> Path:
    return Path(context_dir) / f"{context_id}{extension_for_format(format_name)}"
