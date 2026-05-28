from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


INLINE_PATTERN = re.compile(r"(\*\*[^*]+\*\*|__[^_]+__|\*[^*]+\*|_[^_]+_|`[^`]+`)")
ORDERED_LIST_PATTERN = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
UNORDERED_LIST_PATTERN = re.compile(r"^(\s*)([-*])\s+(.*)$")


def parse_inline(text: str) -> list[dict]:
    runs: list[dict] = []
    cursor = 0
    for match in INLINE_PATTERN.finditer(text):
        start, end = match.span()
        if start > cursor:
            runs.append({"text": text[cursor:start]})

        token = match.group(0)
        if token.startswith("**") and token.endswith("**"):
            runs.append({"text": token[2:-2], "bold": True})
        elif token.startswith("__") and token.endswith("__"):
            runs.append({"text": token[2:-2], "bold": True})
        elif token.startswith("*") and token.endswith("*"):
            runs.append({"text": token[1:-1], "italic": True})
        elif token.startswith("_") and token.endswith("_"):
            runs.append({"text": token[1:-1], "italic": True})
        elif token.startswith("`") and token.endswith("`"):
            runs.append({"text": token[1:-1], "code": True})
        cursor = end

    if cursor < len(text):
        runs.append({"text": text[cursor:]})

    return [run for run in runs if run.get("text")]


def parse_markdown_blocks(text: str) -> tuple[list[dict], list[dict]]:
    blocks: list[dict] = []
    outline: list[dict] = []
    paragraph_buffer: list[str] = []
    code_block_buffer: list[str] = []
    in_code_block = False

    def flush_paragraph() -> None:
        if not paragraph_buffer:
            return
        content = "\n".join(paragraph_buffer).strip()
        paragraph_buffer.clear()
        if content:
            blocks.append({"type": "paragraph", "text": content, "runs": parse_inline(content)})

    def flush_code_block(line_number: int) -> None:
        nonlocal in_code_block
        if not in_code_block and not code_block_buffer:
            return
        content = "\n".join(code_block_buffer)
        code_block_buffer.clear()
        in_code_block = False
        if content:
            blocks.append({"type": "code_block", "text": content, "runs": [{"text": content, "code": True}], "line": line_number})

    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip()

        if line.strip().startswith("```"):
            flush_paragraph()
            if in_code_block:
                flush_code_block(line_number)
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_block_buffer.append(line)
            continue

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
                "runs": parse_inline(title),
                "line": line_number,
            }
            blocks.append(heading)
            outline.append({"level": level, "text": title, "line": line_number})
            continue

        ordered_match = ORDERED_LIST_PATTERN.match(line)
        if ordered_match:
            flush_paragraph()
            indent, ordinal, item_text = ordered_match.groups()
            blocks.append(
                {
                    "type": "list_item",
                    "ordered": True,
                    "ordinal": int(ordinal),
                    "level": len(indent) // 2,
                    "text": item_text.strip(),
                    "runs": parse_inline(item_text.strip()),
                    "line": line_number,
                }
            )
            continue

        unordered_match = UNORDERED_LIST_PATTERN.match(line)
        if unordered_match:
            flush_paragraph()
            indent, _, item_text = unordered_match.groups()
            blocks.append(
                {
                    "type": "list_item",
                    "ordered": False,
                    "level": len(indent) // 2,
                    "text": item_text.strip(),
                    "runs": parse_inline(item_text.strip()),
                    "line": line_number,
                }
            )
            continue

        if "|" in line and line.count("|") >= 2:
            flush_paragraph()
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            blocks.append({"type": "table_row", "cells": cells, "text": " | ".join(cells), "runs": parse_inline(" | ".join(cells)), "line": line_number})
            continue

        if line.startswith(">"):
            flush_paragraph()
            quote_text = line[1:].strip()
            blocks.append({"type": "blockquote", "text": quote_text, "runs": parse_inline(quote_text), "line": line_number})
            continue

        if re.fullmatch(r"-{3,}|\*{3,}", line.strip()):
            flush_paragraph()
            blocks.append({"type": "thematic_break", "text": "", "line": line_number})
            continue

        paragraph_buffer.append(line)

    flush_paragraph()
    if in_code_block or code_block_buffer:
        flush_code_block(len(text.splitlines()) + 1)
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