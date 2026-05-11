from __future__ import annotations

from pathlib import Path


FORMAT_ARTIFACTS = {
    "html": "clean.html",
    "raw_html": "raw.html",
    "cleaned_html": "clean.html",
    "clean_html": "clean.html",
    "json": "parsed.json",
    "parsed_json": "parsed.json",
    "blocks": "blocks.json",
}


def artifact_name_for_format(format_name: str) -> str:
    return FORMAT_ARTIFACTS.get(format_name, format_name)


def context_path(context_dir: str | Path, context_id: str, format_name: str) -> Path:
    return Path(context_dir) / context_id / artifact_name_for_format(format_name)
