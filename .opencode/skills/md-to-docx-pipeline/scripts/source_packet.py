#!/usr/bin/env python3
"""source_packet.py — mechanical markdown block splitter, zero semantics.

Splits a markdown file into typed blocks for safe handoff to the Planner.
Blocks are purely mechanical — type is determined by Markdown syntax patterns,
NOT semantic interpretation. The LLM (Planner) maps blocks to DOCX ops.

Block types:
  - heading:     line starting with # (1-6 levels)
  - paragraph:   non-empty text line, not matching any other pattern
  - caption_candidate: matches [Hình ...], [Bảng ...], [Figure ...], [Table ...]
  - list_item:   line starting with -, *, +, or digit-numbered
  - empty_line:  blank line

Outputs source_packet.json with:
  - source_file: absolute path
  - sha256: integrity checksum
  - line_count: total lines
  - block_count: total blocks
  - blocks[]: ordered array of typed blocks

Usage:
    python3 source_packet.py --source noidung.md --run-dir .office-auto/state/...
"""
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

from officecli_native import write_json

# Caption patterns — purely mechanical, no semantic role assignment
CAPTION_PATTERN = re.compile(
    r'^\s*\[(?:Hình|Bảng|Figure|Table|Fig|Tab)\s*[^\]]+\]',
    re.IGNORECASE,
)
# List item patterns
UNORDERED_LIST_PATTERN = re.compile(r'^\s*[-*+]\s+')
ORDERED_LIST_PATTERN = re.compile(r'^\s*\d+[.)]\s+')
# Heading pattern
HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.*)')


def compute_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify_line(line: str) -> str:
    """Classify a single line into a mechanical block type.

    Purely syntax-driven — no semantic interpretation.
    """
    stripped = line.strip()

    if not stripped:
        return "empty_line"

    if HEADING_PATTERN.match(stripped):
        return "heading"

    if CAPTION_PATTERN.match(stripped):
        return "caption_candidate"

    if UNORDERED_LIST_PATTERN.match(stripped) or ORDERED_LIST_PATTERN.match(stripped):
        return "list_item"

    return "paragraph"


def split_into_blocks(lines: list[str]) -> list[dict[str, Any]]:
    """Split lines into typed blocks.

    Adjacent empty_lines are merged. Headings get sub-blocks for their content.
    """
    blocks: list[dict[str, Any]] = []
    block_id = 1

    # First pass: collect line-level blocks
    current_lines: list[str] = []
    current_type: str | None = None

    for i, line in enumerate(lines):
        line_type = classify_line(line)

        # Merge consecutive empty lines
        if line_type == "empty_line":
            if current_type == "empty_line":
                current_lines.append(line)
                continue
            # Flush previous block if any
            if current_type is not None and current_lines:
                blocks.append({
                    "id": f"B{block_id:04d}",
                    "type": current_type,
                    "text": "\n".join(current_lines),
                    "line_start": i + 1 - len(current_lines),
                    "line_end": i,
                })
                block_id += 1
            current_lines = [line]
            current_type = "empty_line"
            continue

        # Start new block if type changes
        if current_type != line_type:
            if current_type is not None and current_lines:
                blocks.append({
                    "id": f"B{block_id:04d}",
                    "type": current_type,
                    "text": "\n".join(current_lines),
                    "line_start": i + 1 - len(current_lines),
                    "line_end": i,
                })
                block_id += 1
            current_lines = [line]
            current_type = line_type
        else:
            current_lines.append(line)

    # Flush final block
    if current_type is not None and current_lines:
        blocks.append({
            "id": f"B{block_id:04d}",
            "type": current_type,
            "text": "\n".join(current_lines),
            "line_start": len(lines) + 1 - len(current_lines),
            "line_end": len(lines),
        })
        block_id += 1

    return blocks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="source_packet: mechanical markdown block splitter — zero semantics."
    )
    parser.add_argument("--source", required=True, help="Path to source markdown file (e.g., noidung.md)")
    parser.add_argument("--run-dir", required=True, help="Run directory for output artifacts")
    parser.add_argument("--max-blocks-per-chunk", type=int, default=30,
                        help="Max blocks per chunk for chunked planning (default: 30)")
    parser.add_argument("--chunk-index", type=int, default=0,
                        help="Chunk index to output (0 = full, >0 = specific chunk)")
    args = parser.parse_args()

    source_path = Path(args.source)
    run_dir = Path(args.run_dir)

    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    # Read source
    source_text = source_path.read_text(encoding="utf-8")
    source_sha256 = compute_sha256(source_text)
    lines = source_text.splitlines(keepends=False)
    # Also preserve line breaks in blocks for multi-paragraph text
    line_with_breaks = source_text.splitlines(keepends=True)

    # Split into blocks
    all_blocks = split_into_blocks(lines)

    # Compute chunks
    chunk_blocks = None
    if args.chunk_index > 0 and args.max_blocks_per_chunk > 0:
        start = (args.chunk_index - 1) * args.max_blocks_per_chunk
        end = start + args.max_blocks_per_chunk
        chunk_blocks = all_blocks[start:end] if start < len(all_blocks) else []

    # Build packet
    packet: dict[str, Any] = {
        "source_file": str(source_path.resolve()),
        "sha256": source_sha256,
        "line_count": len(lines),
        "block_count": len(all_blocks),
        "blocks": chunk_blocks if chunk_blocks is not None else all_blocks,
        "note": (
            "types are MECHANICAL (Markdown syntax patterns only). "
            "The LLM decides actual DOCX mapping (style, role, anchor). "
            "caption_candidate means [Hình ...]/[Bảng ...] pattern found — "
            "LLM decides whether to map to body or caption style."
        ),
    }

    if chunk_blocks is not None:
        packet["chunk_index"] = args.chunk_index
        packet["total_chunks"] = max(1, -( -len(all_blocks) // args.max_blocks_per_chunk))
        packet["blocks_in_chunk"] = len(chunk_blocks)
    else:
        packet["chunk_index"] = 0
        packet["total_chunks"] = 1

    # Write output
    suffix = f"_chunk{args.chunk_index:03d}" if args.chunk_index > 0 else ""
    output_path = run_dir / f"source_packet{suffix}.json"
    write_json(output_path, packet)

    print(f"[source_packet] Source: {source_path}")
    print(f"[source_packet] SHA-256: {source_sha256[:16]}...")
    print(f"[source_packet] Lines: {len(lines)}, Blocks: {len(all_blocks)}")
    if chunk_blocks is not None:
        print(f"[source_packet] Chunk {args.chunk_index}/{packet['total_chunks']}: "
              f"{len(chunk_blocks)} blocks (lines {chunk_blocks[0]['line_start'] if chunk_blocks else 0}-"
              f"{chunk_blocks[-1]['line_end'] if chunk_blocks else 0})")
    print(f"[source_packet] Output: {output_path}")


if __name__ == "__main__":
    main()
