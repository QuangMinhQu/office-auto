from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_markdown_blocks(text: str) -> tuple[list[dict], list[dict]]:
    blocks: list[dict] = []
    outline: list[dict] = []
    paragraph_buffer: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        content = "\n".join(paragraph_buffer).strip()
        paragraph_buffer.clear()
        if content:
            blocks.append({"type": "paragraph", "text": content})

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()

        if not line.strip():
            flush_paragraph()
            continue

        if line.lstrip().startswith("#"):
            flush_paragraph()
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            heading = {
                "type": "heading",
                "level": level,
                "text": title,
                "line": line_number,
            }
            blocks.append(heading)
            outline.append({"level": level, "text": title, "line": line_number})
            continue

        if line.startswith("- ") or line.startswith("* "):
            flush_paragraph()
            blocks.append({"type": "list_item", "text": line[2:].strip(), "line": line_number})
            continue

        if "|" in line and line.count("|") >= 2:
            flush_paragraph()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            blocks.append({"type": "table_row", "cells": cells, "line": line_number})
            continue

        paragraph_buffer.append(line)

    flush_paragraph()
    return blocks, outline


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phân tích Markdown thành AST và outline JSON.")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    source_file = Path(args.source_file)
    run_dir = Path(args.run_dir)

    text = source_file.read_text(encoding="utf-8")
    blocks, outline = parse_markdown_blocks(text)

    ast_payload = {
        "source_file": str(source_file),
        "block_count": len(blocks),
        "blocks": blocks,
    }
    outline_payload = {
        "source_file": str(source_file),
        "heading_count": len(outline),
        "outline": outline,
    }

    write_json(run_dir / "content_ast.json", ast_payload)
    write_json(run_dir / "content_outline.json", outline_payload)


if __name__ == "__main__":
    main()