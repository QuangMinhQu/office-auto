from __future__ import annotations

import subprocess
from pathlib import Path


SUPPORTED_PANDOC_INPUT_EXTENSIONS = {
    ".docx",
    ".md",
    ".markdown",
    ".txt",
    ".text",
}


class PandocDependencyError(RuntimeError):
    pass


class PandocConversionError(RuntimeError):
    pass


def _ensure_pandoc_binary() -> None:
    result = subprocess.run(["pandoc", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "Không gọi được pandoc --version."
        raise PandocDependencyError(
            "Thiếu dependency pandoc CLI hoặc pandoc chưa có trong PATH. "
            f"Chi tiết: {message}"
        )


def normalize_markdown_output(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    if not normalized:
        return ""
    return normalized + "\n"


def _pandoc_from_format(source_file: Path) -> str:
    suffix = source_file.suffix.lower()
    if suffix == ".docx":
        # Keep custom style metadata in markdown via Div/Span custom-style attributes.
        return "docx+styles"
    if suffix in {".md", ".markdown"}:
        return "markdown"
    if suffix in {".txt", ".text"}:
        return "markdown"
    raise ValueError(f"Định dạng input chưa được hỗ trợ cho Pandoc normalize: {suffix or '<không có extension>'}")


def load_style_spec(style_spec_file: Path | None) -> dict:
    if style_spec_file is None or not style_spec_file.exists():
        return {}
    import json

    payload = json.loads(style_spec_file.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def normalize_source_markdown(source_file: Path, *, style_spec: dict | None = None) -> tuple[str, dict]:
    if not source_file.exists():
        raise FileNotFoundError(f"Không tìm thấy input file: {source_file}")

    suffix = source_file.suffix.lower()
    if suffix not in SUPPORTED_PANDOC_INPUT_EXTENSIONS:
        raise ValueError(f"Định dạng input chưa được hỗ trợ cho normalize: {suffix or '<không có extension>'}")

    if suffix in {".md", ".markdown", ".txt", ".text"}:
        return (
            normalize_markdown_output(source_file.read_text(encoding="utf-8")),
            {
                "mode": "pass-through",
                "converter": "none",
                "source_extension": suffix,
                "style_spec_used": False,
            },
        )

    _ensure_pandoc_binary()

    try:
        command = [
            "pandoc",
            str(source_file),
            "-f",
            _pandoc_from_format(source_file),
            "-t",
            "markdown",
            "--wrap=none",
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise PandocConversionError(
                f"Pandoc không convert được {source_file}: {result.stderr.strip() or result.stdout.strip()}"
            )
        markdown_output = result.stdout
    except PandocDependencyError:
        raise
    except PandocConversionError:
        raise
    except Exception as exc:
        raise PandocConversionError(f"Pandoc không convert được {source_file}: {exc}") from exc

    return (
        normalize_markdown_output(markdown_output),
        {
            "mode": "pandoc",
            "converter": "Pandoc",
            "source_extension": suffix,
            "style_spec_used": bool(style_spec),
        },
    )
