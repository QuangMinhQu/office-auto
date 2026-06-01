from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except ImportError as exc:
    raise SystemExit(
        "Thiếu dependency markdown-it-py. Hãy cài requirements của workspace trước khi chạy pipeline DOCX."
    ) from exc


REFERENCE_PATTERN = re.compile(r"^\[(\d+)\]\s+(.*)$")
INLINE_BREAK_TYPES = {"softbreak", "hardbreak"}
SECTION_REFERENCE = "references"


def normalize_heading_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).upper()


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def parser() -> MarkdownIt:
    return MarkdownIt("commonmark").enable("table")


def append_run(runs: list[dict[str, Any]], text: str, **flags: Any) -> None:
    if not text:
        return

    normalized_flags = {key: value for key, value in flags.items() if value not in (None, False, "")}
    if runs:
        previous = runs[-1]
        previous_flags = {key: value for key, value in previous.items() if key != "text"}
        if previous_flags == normalized_flags:
            previous["text"] = f"{previous['text']}{text}"
            return

    run = {"text": text}
    run.update(normalized_flags)
    runs.append(run)


def inline_runs(children: list[Token] | None) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    bold_depth = 0
    italic_depth = 0
    current_link: str | None = None

    for child in children or []:
        token_type = child.type
        if token_type == "text":
            append_run(runs, child.content, bold=bold_depth > 0, italic=italic_depth > 0, link=current_link)
            continue

        if token_type == "code_inline":
            append_run(runs, child.content, code=True, link=current_link)
            continue

        if token_type == "strong_open":
            bold_depth += 1
            continue
        if token_type == "strong_close":
            bold_depth = max(0, bold_depth - 1)
            continue
        if token_type == "em_open":
            italic_depth += 1
            continue
        if token_type == "em_close":
            italic_depth = max(0, italic_depth - 1)
            continue
        if token_type == "link_open":
            current_link = child.attrGet("href")
            continue
        if token_type == "link_close":
            current_link = None
            continue
        if token_type in INLINE_BREAK_TYPES:
            append_run(runs, "\n", bold=bold_depth > 0, italic=italic_depth > 0, link=current_link)
            continue
        if token_type == "html_inline":
            append_run(runs, child.content, bold=bold_depth > 0, italic=italic_depth > 0, link=current_link)

    return [run for run in runs if run.get("text")]


def runs_to_text(runs: list[dict[str, Any]]) -> str:
    return "".join(str(run.get("text") or "") for run in runs)


def parse_reference_line(text: str) -> dict[str, Any] | None:
    match = REFERENCE_PATTERN.match(text.strip())
    if match is None:
        return None
    ordinal = int(match.group(1))
    content = match.group(2).strip()
    return {
        "type": "reference",
        "ordinal": ordinal,
        "text": content,
        "runs": [{"text": content}],
    }


def line_number(token: Token) -> int | None:
    if not token.map:
        return None
    return int(token.map[0]) + 1


def parse_table(tokens: list[Token], start_index: int) -> tuple[dict[str, Any], int]:
    rows: list[dict[str, Any]] = []
    header_mode = False
    current_row: dict[str, Any] | None = None
    current_cell: dict[str, Any] | None = None
    index = start_index + 1

    while index < len(tokens):
        token = tokens[index]
        if token.type == "table_close":
            break
        if token.type == "thead_open":
            header_mode = True
        elif token.type == "tbody_open":
            header_mode = False
        elif token.type == "tr_open":
            current_row = {"header": header_mode, "cells": []}
        elif token.type == "tr_close":
            if current_row is not None:
                rows.append(current_row)
            current_row = None
        elif token.type in {"th_open", "td_open"}:
            current_cell = {"text": "", "runs": []}
        elif token.type == "inline" and current_cell is not None:
            cell_runs = inline_runs(token.children)
            current_cell["runs"] = cell_runs
            current_cell["text"] = runs_to_text(cell_runs).strip()
        elif token.type in {"th_close", "td_close"}:
            if current_row is not None and current_cell is not None:
                current_row["cells"].append(current_cell)
            current_cell = None
        index += 1

    block = {
        "type": "table",
        "rows": rows,
        "column_count": max((len(row.get("cells", [])) for row in rows), default=0),
        "text": "\n".join(" | ".join(cell.get("text", "") for cell in row.get("cells", [])) for row in rows),
        "line": line_number(tokens[start_index]),
    }
    return block, index + 1


def make_paragraph_block(
    *,
    block_type: str,
    inline_token: Token,
    line: int | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    runs = inline_runs(inline_token.children)
    block = {
        "type": block_type,
        "text": runs_to_text(runs).strip(),
        "runs": runs,
        "line": line,
    }
    if extra:
        block.update(extra)
    return block


def parse_list_item(
    tokens: list[Token],
    start_index: int,
    *,
    ordered: bool,
    ordinal: int,
    level: int,
    current_section: str | None,
) -> tuple[list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    index = start_index + 1
    emitted_primary = False

    while index < len(tokens):
        token = tokens[index]
        if token.type == "list_item_close":
            return blocks, index + 1

        if token.type == "paragraph_open":
            inline_token = tokens[index + 1]
            paragraph_line = line_number(token)
            paragraph_runs = inline_runs(inline_token.children)
            paragraph_text = runs_to_text(paragraph_runs).strip()

            if current_section == SECTION_REFERENCE:
                reference_block = parse_reference_line(paragraph_text)
                if reference_block is not None:
                    reference_block["runs"] = paragraph_runs
                    reference_block["line"] = paragraph_line
                    blocks.append(reference_block)
                    emitted_primary = True
                    index += 3
                    continue

            block_type = "list_item" if not emitted_primary else "paragraph"
            extra = {
                "ordered": ordered,
                "ordinal": ordinal,
                "level": level,
            } if block_type == "list_item" else {"list_parent_level": level}
            blocks.append(
                {
                    "type": block_type,
                    "text": paragraph_text,
                    "runs": paragraph_runs,
                    "line": paragraph_line,
                    **extra,
                }
            )
            emitted_primary = True
            index += 3
            continue

        if token.type in {"bullet_list_open", "ordered_list_open"}:
            nested_blocks, index = parse_list(
                tokens,
                index,
                level=level + 1,
                current_section=current_section,
            )
            blocks.extend(nested_blocks)
            continue

        if token.type == "blockquote_open":
            quote_blocks, index = parse_blockquote(tokens, index, current_section=current_section)
            blocks.extend(quote_blocks)
            continue

        if token.type == "fence":
            blocks.append(
                {
                    "type": "code_block",
                    "text": token.content,
                    "runs": [{"text": token.content, "code": True}],
                    "language": token.info.strip() or None,
                    "line": line_number(token),
                }
            )
            index += 1
            continue

        if token.type == "table_open":
            table_block, index = parse_table(tokens, index)
            blocks.append(table_block)
            continue

        if token.type == "hr":
            blocks.append({"type": "thematic_break", "text": "", "line": line_number(token)})
            index += 1
            continue

        index += 1

    return blocks, index


def parse_list(
    tokens: list[Token],
    start_index: int,
    *,
    level: int,
    current_section: str | None,
) -> tuple[list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    open_token = tokens[start_index]
    close_type = "ordered_list_close" if open_token.type == "ordered_list_open" else "bullet_list_close"
    ordered = open_token.type == "ordered_list_open"
    ordinal = int(open_token.attrGet("start") or 1)
    index = start_index + 1

    while index < len(tokens):
        token = tokens[index]
        if token.type == close_type:
            return blocks, index + 1
        if token.type != "list_item_open":
            index += 1
            continue

        item_blocks, index = parse_list_item(
            tokens,
            index,
            ordered=ordered,
            ordinal=ordinal,
            level=level,
            current_section=current_section,
        )
        blocks.extend(item_blocks)
        if ordered:
            ordinal += 1

    return blocks, index


def parse_blockquote(tokens: list[Token], start_index: int, *, current_section: str | None) -> tuple[list[dict[str, Any]], int]:
    blocks: list[dict[str, Any]] = []
    index = start_index + 1

    while index < len(tokens):
        token = tokens[index]
        if token.type == "blockquote_close":
            return blocks, index + 1

        if token.type == "paragraph_open":
            inline_token = tokens[index + 1]
            blocks.append(
                make_paragraph_block(
                    block_type="blockquote",
                    inline_token=inline_token,
                    line=line_number(token),
                )
            )
            index += 3
            continue

        if token.type in {"bullet_list_open", "ordered_list_open"}:
            nested_blocks, index = parse_list(tokens, index, level=1, current_section=current_section)
            for block in nested_blocks:
                block.setdefault("quote_depth", 1)
            blocks.extend(nested_blocks)
            continue

        if token.type == "fence":
            blocks.append(
                {
                    "type": "code_block",
                    "text": token.content,
                    "runs": [{"text": token.content, "code": True}],
                    "language": token.info.strip() or None,
                    "line": line_number(token),
                    "quote_depth": 1,
                }
            )
            index += 1
            continue

        if token.type == "table_open":
            table_block, index = parse_table(tokens, index)
            table_block["quote_depth"] = 1
            blocks.append(table_block)
            continue

        index += 1

    return blocks, index


def parse_markdown_blocks(text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    tokens = parser().parse(text)
    blocks: list[dict[str, Any]] = []
    outline: list[dict[str, Any]] = []
    section_transitions: list[dict[str, Any]] = []
    current_section: str | None = None
    index = 0

    while index < len(tokens):
        token = tokens[index]

        if token.type == "heading_open":
            inline_token = tokens[index + 1]
            heading_runs = inline_runs(inline_token.children)
            raw_title = runs_to_text(heading_runs).strip()
            title = strip_heading_numbering(raw_title)
            level = int(token.tag[1])
            heading_block = {
                "type": "heading",
                "level": level,
                "text": title,
                "runs": [{**run, "text": strip_heading_numbering(str(run.get("text") or ""))} for run in heading_runs if str(run.get("text") or "").strip()],
                "line": line_number(token),
            }
            if not heading_block["runs"]:
                heading_block["runs"] = [{"text": title}]
            blocks.append(heading_block)
            outline.append({"level": level, "text": title, "line": line_number(token)})

            previous_section = current_section
            current_section = SECTION_REFERENCE if normalize_heading_text(title) == "TÀI LIỆU THAM KHẢO" else None
            if current_section != previous_section:
                section_transitions.append({"section": current_section or "body", "heading": title, "line": line_number(token)})

            index += 3
            continue

        if token.type == "paragraph_open":
            inline_token = tokens[index + 1]
            block = make_paragraph_block(block_type="paragraph", inline_token=inline_token, line=line_number(token))
            if current_section == SECTION_REFERENCE:
                reference_block = parse_reference_line(block["text"])
                if reference_block is not None:
                    reference_block["runs"] = block["runs"]
                    reference_block["line"] = block["line"]
                    block = reference_block
            blocks.append(block)
            index += 3
            continue

        if token.type in {"bullet_list_open", "ordered_list_open"}:
            list_blocks, index = parse_list(tokens, index, level=0, current_section=current_section)
            blocks.extend(list_blocks)
            continue

        if token.type == "blockquote_open":
            quote_blocks, index = parse_blockquote(tokens, index, current_section=current_section)
            blocks.extend(quote_blocks)
            continue

        if token.type == "fence":
            blocks.append(
                {
                    "type": "code_block",
                    "text": token.content,
                    "runs": [{"text": token.content, "code": True}],
                    "language": token.info.strip() or None,
                    "line": line_number(token),
                }
            )
            index += 1
            continue

        if token.type == "code_block":
            blocks.append(
                {
                    "type": "code_block",
                    "text": token.content,
                    "runs": [{"text": token.content, "code": True}],
                    "language": None,
                    "line": line_number(token),
                }
            )
            index += 1
            continue

        if token.type == "hr":
            blocks.append({"type": "thematic_break", "text": "", "line": line_number(token)})
            index += 1
            continue

        if token.type == "table_open":
            table_block, index = parse_table(tokens, index)
            blocks.append(table_block)
            continue

        index += 1

    metadata = {
        "parser": "markdown-it-py",
        "section_transitions": section_transitions,
    }
    return blocks, outline, metadata


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser_instance = argparse.ArgumentParser(description="Phân tích Markdown thành AST và outline JSON.")
    parser_instance.add_argument("--source-file", required=True)
    parser_instance.add_argument("--run-dir", required=True)
    args = parser_instance.parse_args()

    source_file = Path(args.source_file)
    run_dir = Path(args.run_dir)

    text = source_file.read_text(encoding="utf-8")
    blocks, outline, metadata = parse_markdown_blocks(text)

    ast_payload = {
        "source_file": str(source_file),
        "parser": metadata.get("parser"),
        "block_count": len(blocks),
        "blocks": blocks,
        "metadata": metadata,
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