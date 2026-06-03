from __future__ import annotations

from pathlib import Path

from pandoc_support import (
    PandocConversionError,
    PandocDependencyError,
    load_style_spec,
    normalize_markdown_output,
    normalize_source_markdown as normalize_source_markdown_pandoc,
)


class MarkItDownDependencyError(PandocDependencyError):
    pass


class MarkItDownConversionError(PandocConversionError):
    pass


def _load_markitdown_class():
    raise MarkItDownDependencyError("MarkItDown đã được thay bằng Pandoc trong pipeline này.")


def load_style_map(style_map_file: Path | None) -> str | None:
    if style_map_file is None or not style_map_file.exists():
        return None
    text = style_map_file.read_text(encoding="utf-8").strip()
    return text or None


def normalize_source_markdown(source_file: Path, *, style_map: str | None = None) -> tuple[str, dict]:
    _ = style_map
    style_spec = {}
    markdown, summary = normalize_source_markdown_pandoc(source_file, style_spec=style_spec)
    # Compatibility fields for callers still expecting the old summary contract.
    summary["style_map_used"] = False
    if summary.get("mode") == "pandoc":
        summary["mode"] = "pandoc"
    return markdown, summary


__all__ = [
    "MarkItDownDependencyError",
    "MarkItDownConversionError",
    "load_style_map",
    "load_style_spec",
    "normalize_markdown_output",
    "normalize_source_markdown",
]