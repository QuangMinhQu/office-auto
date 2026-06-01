from __future__ import annotations

from pathlib import Path


SUPPORTED_MARKITDOWN_EXTENSIONS = {
    ".csv",
    ".docx",
    ".epub",
    ".htm",
    ".html",
    ".json",
    ".md",
    ".pdf",
    ".pptx",
    ".text",
    ".txt",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


class MarkItDownDependencyError(RuntimeError):
    pass


class MarkItDownConversionError(RuntimeError):
    pass


def _load_markitdown_class():
    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise MarkItDownDependencyError(
            "Thiếu dependency markitdown. Hãy cài requirements của workspace trước khi chạy phase dùng MarkItDown."
        ) from exc
    return MarkItDown


def load_style_map(style_map_file: Path | None) -> str | None:
    if style_map_file is None or not style_map_file.exists():
        return None
    text = style_map_file.read_text(encoding="utf-8").strip()
    return text or None


def normalize_markdown_output(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized:
        return ""
    return normalized + "\n"


def normalize_source_markdown(source_file: Path, *, style_map: str | None = None) -> tuple[str, dict]:
    if not source_file.exists():
        raise FileNotFoundError(f"Không tìm thấy input file: {source_file}")

    suffix = source_file.suffix.lower()
    if suffix not in SUPPORTED_MARKITDOWN_EXTENSIONS:
        raise ValueError(f"Định dạng input chưa được hỗ trợ cho normalize: {suffix or '<không có extension>'}")

    if suffix == ".md":
        return (
            normalize_markdown_output(source_file.read_text(encoding="utf-8")),
            {
                "mode": "pass-through",
                "converter": "none",
                "source_extension": suffix,
                "style_map_used": False,
            },
        )

    MarkItDown = _load_markitdown_class()
    try:
        converter = MarkItDown(enable_plugins=False)
        convert_kwargs = {}
        if style_map and suffix == ".docx":
            convert_kwargs["style_map"] = style_map

        result = converter.convert_local(str(source_file), **convert_kwargs)
        text_content = getattr(result, "text_content", None)
        if text_content in (None, ""):
            text_content = getattr(result, "markdown", None)
        if text_content is None:
            raise RuntimeError("MarkItDown không trả về text_content hợp lệ.")
    except Exception as exc:
        raise MarkItDownConversionError(f"MarkItDown không convert được {source_file}: {exc}") from exc

    return (
        normalize_markdown_output(str(text_content)),
        {
            "mode": "markitdown",
            "converter": "MarkItDown",
            "source_extension": suffix,
            "style_map_used": bool(style_map and suffix == ".docx"),
        },
    )