#!/usr/bin/env python3
"""execute_execution_ops.py — mechanical ops executor, zero reasoning.

Reads execution_ops.json and applies each operation mechanically to the
target DOCX via OfficeCLI. This is the "hands" — the LLM already decided
WHAT to do. This script ONLY executes.

Supported operations (per issue.md spec):
  - insert_paragraph_after:  insert paragraph after anchor with style/text
  - insert_paragraph_before: insert paragraph before anchor with style/text
  - remove:          delete element by path
  - update_text:     update text of paragraph at path
  - insert_table:    insert table after anchor
  - set_page_layout: set page-level properties (margins, paper_size, orientation)

Usage:
    python execute_execution_ops.py --run-dir <path>
"""
from __future__ import annotations

import argparse
import json
import time
from contextlib import contextmanager
from pathlib import Path

from officecli_native import (
    OfficeCliError,
    ensure_officecli_available,
    officecli_add,
    officecli_batch_commands,
    officecli_close,
    officecli_open,
    officecli_remove,
    officecli_save,
    officecli_set,
    read_json,
    write_json,
)


# Batch sizes for efficiency
REMOVE_BATCH_SIZE = 200
ADD_BATCH_SIZE = 40


@contextmanager
def doc_session(target_path: Path):
    """Open → yield → close document session."""
    officecli_open(str(target_path))
    try:
        yield target_path
    finally:
        try:
            officecli_close(str(target_path))
        except Exception:
            pass


def execute_remove(operation: dict) -> str | None:
    """Mechanically remove element at path."""
    path = operation.get("path")
    if not path:
        return None
    officecli_remove(str(path))
    return None


def execute_insert_paragraph(operation: dict, current_anchor: str, document_path: Path) -> str:
    """Mechanically insert paragraph after anchor with given style/text.

    OfficeCLI requires parent to be '/body' for paragraph insertion.
    The --after flag specifies the anchor paragraph to insert after.
    
    Note: current_anchor is already resolved by resolve_anchor() which handles
    special keywords like "PREVIOUS". Do NOT read operation.get("anchor") here.
    """
    style = str(operation.get("style") or "Normal")
    text = str(operation.get("text") or "")
    anchor = current_anchor  # Use resolved anchor from resolve_anchor()
    run_props = operation.get("run_props") or {}

    # Build set_props: style, text, plus any run-level properties
    set_props = {"style": style}
    if text:
        set_props["text"] = text

    # Merge run_props (font, size, bold, italic, etc.)
    for key, val in run_props.items():
        if val is not None:
            if key == "font":
                set_props["font"] = str(val)
            elif key == "size":
                set_props["size"] = str(val)
            elif key == "bold":
                set_props["bold"] = str(bool(val))
            elif key == "italic":
                set_props["italic"] = str(bool(val))
            elif key in ("color", "color_hex", "font_color"):
                set_props["color"] = str(val)
            elif key in ("align", "alignment"):
                set_props["align"] = str(val)
            elif key in ("space_before", "space_before_pt"):
                set_props["space_before"] = str(val)
            elif key in ("space_after", "space_after_pt"):
                set_props["space_after"] = str(val)
            elif key in ("indent", "indentation", "left_indent", "left_indent_pt"):
                set_props["indent"] = str(val)
            elif key in ("first_line_indent", "first_line_indent_pt"):
                set_props["first_line_indent"] = str(val)

    # OfficeCLI: parent must be '/body' for paragraph insertion
    # Use --after to specify anchor position
    result = officecli_add(
        document_path,
        "/body",
        element_type="paragraph",
        props=set_props,
        after=anchor,
    )
    # Handle both dict result and string path
    if isinstance(result, str):
        # Parse "Added paragraph at /body/p[@paraId=XXXXX]" → "/body/p[@paraId=XXXXX]"
        if " at " in result:
            new_path = result.split(" at ", 1)[1].strip()
        else:
            new_path = result
    elif isinstance(result, dict):
        new_path = result.get("path", "") or ""
        if not new_path:
            data = result.get("data")
            if isinstance(data, str):
                # Parse "Added paragraph at /body/p[@paraId=XXXXX]" → "/body/p[@paraId=XXXXX]"
                if " at " in data:
                    new_path = data.split(" at ", 1)[1].strip()
                else:
                    new_path = data
            elif isinstance(data, dict):
                new_path = data.get("path", "") or ""
        new_path = new_path or anchor
    else:
        new_path = anchor
    return str(new_path)


def execute_insert_table(operation: dict, current_anchor: str, document_path: Path, range_info: dict | None = None) -> str:
    """Mechanically insert table after anchor.
    
    Uses resolve_anchor() to handle special keywords like "PREVIOUS".
    Do NOT read operation.get("anchor") directly — it may be a literal string.
    """
    anchor = resolve_anchor(operation, current_anchor, range_info)
    rows = operation.get("rows", [])
    columns = operation.get("columns")

    # Build table rows data
    table_data = []
    for row in rows:
        cells = row.get("cells", [])
        row_data = {"cells": cells}
        table_data.append(row_data)

    props = {}
    if columns:
        props["columns"] = str(columns)

    # OfficeCLI: parent must be '/body' for table insertion
    result = officecli_add(
        document_path,
        "/body",
        element_type="table",
        props=props,
        after=anchor,
    )
    # Handle both dict result and string path
    if isinstance(result, str):
        new_path = result
    elif isinstance(result, dict):
        new_path = result.get("path", "") or ""
        if not new_path:
            data = result.get("data")
            if isinstance(data, str):
                new_path = data
            elif isinstance(data, dict):
                new_path = data.get("path", "") or ""
        new_path = new_path or anchor
    else:
        new_path = anchor

    # Add rows/cells to table (mechanical, no reasoning)
    for row_idx, row_data in enumerate(table_data):
        cells = row_data.get("cells", [])
        for cell_idx, cell_text in enumerate(cells):
            cell_path = f"{new_path}/row[{row_idx}]/cell[{cell_idx}]"
            if cell_text:
                officecli_set(document_path, cell_path, props={"text": str(cell_text)})

    return str(new_path)


def execute_insert_paragraph_before(operation: dict, current_anchor: str, document_path: Path) -> str:
    """Mechanically insert paragraph BEFORE anchor with given style/text.

    Similar to insert_paragraph_after but inserts before the anchor element.
    """
    style = str(operation.get("style") or "Normal")
    text = str(operation.get("text") or "")
    anchor = str(operation.get("anchor") or current_anchor or "")
    run_props = operation.get("run_props") or {}

    # Build set_props: style, text, plus any run-level properties
    set_props = {"style": style}
    if text:
        set_props["text"] = text

    # Merge run_props (font, size, bold, italic, etc.)
    for key, val in run_props.items():
        if val is not None:
            if key == "font":
                set_props["font"] = str(val)
            elif key == "size":
                set_props["size"] = str(val)
            elif key == "bold":
                set_props["bold"] = str(bool(val))
            elif key == "italic":
                set_props["italic"] = str(bool(val))
            elif key in ("color", "color_hex", "font_color"):
                set_props["color"] = str(val)
            elif key in ("align", "alignment"):
                set_props["align"] = str(val)
            elif key in ("space_before", "space_before_pt"):
                set_props["space_before"] = str(val)
            elif key in ("space_after", "space_after_pt"):
                set_props["space_after"] = str(val)
            elif key in ("indent", "indentation", "left_indent", "left_indent_pt"):
                set_props["indent"] = str(val)
            elif key in ("first_line_indent", "first_line_indent_pt"):
                set_props["first_line_indent"] = str(val)

    # OfficeCLI: parent must be '/body' for paragraph insertion
    # Use --before to specify anchor position
    result = officecli_add(
        document_path,
        "/body",
        element_type="paragraph",
        props=set_props,
        before=anchor,
    )
    # Handle both dict result and string path
    if isinstance(result, str):
        new_path = result
    elif isinstance(result, dict):
        new_path = result.get("path", "") or ""
        if not new_path:
            data = result.get("data")
            if isinstance(data, str):
                new_path = data
            elif isinstance(data, dict):
                new_path = data.get("path", "") or ""
        new_path = new_path or anchor
    return str(new_path)


def execute_update_text(operation: dict, document_path: Path) -> str:
    """Mechanically update text of a paragraph at given path.

    If run_props provided, also update run-level properties.
    """
    path = operation.get("path")
    if not path:
        raise ValueError(f"update_text op #{operation.get('index', '?')} missing 'path'")

    text = str(operation.get("text", ""))
    run_props = operation.get("run_props") or {}

    # Build set_props
    set_props: dict[str, str] = {}
    if text:
        set_props["text"] = text

    for key, val in run_props.items():
        if val is not None:
            if key == "font":
                set_props["font"] = str(val)
            elif key == "size":
                set_props["size"] = str(val)
            elif key == "bold":
                set_props["bold"] = str(bool(val))
            elif key == "italic":
                set_props["italic"] = str(bool(val))
            elif key in ("color", "color_hex", "font_color"):
                set_props["color"] = str(val)

    if not set_props:
        return str(path)

    officecli_set(document_path, path, props=set_props)
    return str(path)


def execute_set_page_layout(operation: dict, document_path: Path) -> str:
    """Mechanically set page layout properties.

    Params:
      - margins: dict with top/bottom/left/right in twips or points
      - paper_size: dict with w/h in twips, or preset like "A4", "Letter"
      - orientation: "portrait" or "landscape"
    """
    margins = operation.get("margins")
    paper_size = operation.get("paper_size")
    orientation = operation.get("orientation")

    set_props: dict[str, str] = {}

    if margins:
        for side in ("top", "bottom", "left", "right"):
            if side in margins:
                set_props[f"margin_{side}"] = str(margins[side])

    if paper_size:
        if isinstance(paper_size, dict):
            if "w" in paper_size:
                set_props["paper_width"] = str(paper_size["w"])
            if "h" in paper_size:
                set_props["paper_height"] = str(paper_size["h"])
        elif isinstance(paper_size, str):
            set_props["paper_size"] = paper_size

    if orientation:
        set_props["orientation"] = str(orientation)

    if set_props:
        # Set page layout at document level
        officecli_set(document_path, "/body", props=set_props)

    return "page_layout"


def resolve_anchor(op: dict, current_anchor: str, range_info: dict | None) -> str:
    """Resolve anchor for an operation.

    Mechanics only: no intelligence, just path resolution.
    Special keywords:
      - "PREVIOUS" / "previous" → use current_anchor (last inserted/processed path)
      - "selected" → use range_info.insert_after_path if available
    """
    explicit_anchor = op.get("anchor")
    anchor_str = str(explicit_anchor).strip() if explicit_anchor else ""

    # Handle "PREVIOUS" keyword FIRST — use the last processed anchor
    if anchor_str and anchor_str.upper() == "PREVIOUS":
        return current_anchor

    # Handle other explicit anchors
    if explicit_anchor and anchor_str:
        return str(explicit_anchor)

    # Use range insert_after_path if available
    if range_info:
        insert_after = range_info.get("insert_after_path")
        if insert_after and str(insert_after).strip():
            return str(insert_after)

    # Fall back to current anchor
    return current_anchor


def execute_ops_batch(
    ops: list[dict],
    target_path: Path,
    range_info: dict | None = None,
) -> dict:
    """Execute a batch of operations mechanically.

    Returns summary stats.
    """
    report = {
        "total_ops": len(ops),
        "succeeded": 0,
        "failed": 0,
        "removed_count": 0,
        "inserted_paragraphs": 0,
        "inserted_tables": 0,
        "updated_texts": 0,
        "page_layout_changes": 0,
        "inserted_paths": [],
        "errors": [],
    }

    current_anchor: str = ""

    with doc_session(target_path) as session:
        # First pass: execute all removes
        remove_ops = [op for op in ops if op.get("op") == "remove"]
        remove_batch = []
        remove_count = 0

        for op in remove_ops:
            try:
                path = op.get("path")
                if path:
                    remove_batch.append({"command": "remove", "path": str(path)})
                    remove_count += 1

                    if len(remove_batch) >= REMOVE_BATCH_SIZE:
                        officecli_batch_commands(session, remove_batch)
                        remove_batch = []
            except OfficeCliError as exc:
                report["failed"] += 1
                report["errors"].append({"op": "remove", "path": str(path), "error": str(exc)})

        # Flush remaining removes
        if remove_batch:
            try:
                officecli_batch_commands(session, remove_batch)
            except OfficeCliError as exc:
                report["failed"] += 1
                report["errors"].append({"batch": "remove", "error": str(exc)})

        report["removed_count"] = remove_count

        # Second pass: execute inserts (paragraphs, tables)
        insert_ops = [
            op for op in ops
            if op.get("op") in (
                "insert_paragraph_after",
                "insert_paragraph_before",
                "insert_table_after",
                "insert_table",
            )
        ]

        batchable_buffer = []
        batchable_count = 0

        for op in insert_ops:
            op_name = op.get("op")

            if op_name == "insert_paragraph_after":
                # Check if this can be batched (simple paragraph, same anchor)
                is_simple = (
                    "style" in op
                    and "text" in op
                    and not op.get("run_props")
                    and (op.get("anchor") is None or op.get("anchor") == current_anchor)
                )
                if is_simple:
                    batchable_buffer.append(op)
                    batchable_count += 1
                    if len(batchable_buffer) >= ADD_BATCH_SIZE:
                        _flush_batch_add(session, batchable_buffer, current_anchor, report)
                        batchable_buffer.clear()
                        batchable_count = 0
                    continue

                # Flush buffer first
                if batchable_buffer:
                    _flush_batch_add(session, batchable_buffer, current_anchor, report)
                    batchable_buffer.clear()
                    batchable_count = 0

                # Execute single
                anchor = resolve_anchor(op, current_anchor, range_info)
                try:
                    new_path = execute_insert_paragraph(op, anchor, session)
                    current_anchor = new_path or anchor
                    report["inserted_paragraphs"] += 1
                    report["succeeded"] += 1
                    report["inserted_paths"].append(new_path)
                except OfficeCliError as exc:
                    report["failed"] += 1
                    report["errors"].append({"op": "insert_paragraph", "path": str(anchor), "error": str(exc)})

            elif op_name == "insert_paragraph_before":
                # Flush buffer first
                if batchable_buffer:
                    _flush_batch_add(session, batchable_buffer, current_anchor, report)
                    batchable_buffer.clear()
                    batchable_count = 0

                anchor = resolve_anchor(op, current_anchor, range_info)
                try:
                    new_path = execute_insert_paragraph_before(op, anchor, session)
                    current_anchor = new_path or anchor
                    report["inserted_paragraphs"] += 1
                    report["succeeded"] += 1
                    report["inserted_paths"].append(new_path)
                except OfficeCliError as exc:
                    report["failed"] += 1
                    report["errors"].append({"op": "insert_paragraph_before", "path": str(anchor), "error": str(exc)})

            elif op_name in ("insert_table_after", "insert_table"):
                # Flush buffer
                if batchable_buffer:
                    _flush_batch_add(session, batchable_buffer, current_anchor, report)
                    batchable_buffer.clear()
                    batchable_count = 0

                anchor = resolve_anchor(op, current_anchor, range_info)
                try:
                    new_path = execute_insert_table(op, anchor, session, range_info)
                    current_anchor = new_path or anchor
                    report["inserted_tables"] += 1
                    report["succeeded"] += 1
                    report["inserted_paths"].append(new_path)
                except OfficeCliError as exc:
                    report["failed"] += 1
                    report["errors"].append({"op": "insert_table", "path": str(anchor), "error": str(exc)})

        # Third pass: execute update_text ops
        update_ops = [op for op in ops if op.get("op") == "update_text"]
        for op in update_ops:
            try:
                new_path = execute_update_text(op, session)
                report["updated_texts"] += 1
                report["succeeded"] += 1
                if new_path:
                    report["inserted_paths"].append(new_path)
            except Exception as exc:
                report["failed"] += 1
                report["errors"].append({"op": "update_text", "path": str(op.get("path", "?")), "error": str(exc)})

        # Fourth pass: execute set_page_layout ops
        layout_ops = [op for op in ops if op.get("op") == "set_page_layout"]
        for op in layout_ops:
            try:
                execute_set_page_layout(op, session)
                report["page_layout_changes"] += 1
                report["succeeded"] += 1
            except Exception as exc:
                report["failed"] += 1
                report["errors"].append({"op": "set_page_layout", "error": str(exc)})

        # Flush remaining batchable
        if batchable_buffer:
            _flush_batch_add(session, batchable_buffer, current_anchor, report)

        # Save the document
        officecli_save(session)

    return report


def _flush_batch_add(
    document_path: Path,
    buffer: list[dict],
    current_anchor: str,
    report: dict,
) -> None:
    """Batch-add simple paragraphs mechanically.

    OfficeCLI: parent must be '/body' for paragraph insertion.
    Use --after to specify anchor position.
    """
    if not buffer:
        return
    anchor = current_anchor
    try:
        for op in buffer:
            style = str(op.get("style") or "Normal")
            text = str(op.get("text") or "")
            props = {"style": style}
            if text:
                props["text"] = text
            result = officecli_add(
                document_path,
                "/body",
                element_type="paragraph",
                props=props,
                after=anchor,
            )
            # Handle both dict result and string path
            if isinstance(result, str):
                new_path = result
            elif isinstance(result, dict):
                new_path = result.get("path", "") or ""
                if not new_path:
                    data = result.get("data")
                    if isinstance(data, str):
                        new_path = data
                    elif isinstance(data, dict):
                        new_path = data.get("path", "") or ""
                new_path = new_path or anchor
            anchor = new_path
            report["inserted_paths"].append(new_path)

        report["succeeded"] += len(buffer)
        report["inserted_paragraphs"] += len(buffer)
    except OfficeCliError as exc:
        report["failed"] += len(buffer)
        report["errors"].append({"batch": "add", "count": len(buffer), "anchor": anchor, "error": str(exc)})


def main() -> None:
    parser = argparse.ArgumentParser(
        description="execute_execution_ops: mechanical executor, zero reasoning."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory with execution_ops.json")
    parser.add_argument(
        "--template-file", default=None,
        help="Template file (copied to target before execution). If omitted, uses target from ops."
    )
    parser.add_argument(
        "--target-file", default=None,
        help="Target output file. If omitted, uses ops target or template path."
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ops_file = run_dir / "execution_ops.json"

    if not ops_file.exists():
        raise FileNotFoundError(f"execution_ops.json not found in: {run_dir}")

    ops_payload = read_json(ops_file)

    # Handle both formats: plain list or dict with "ops" key
    if isinstance(ops_payload, list):
        ops_list = ops_payload
        ops_dict = {}
    else:
        ops_list = ops_payload.get("ops", [])
        ops_dict = ops_payload

    # Determine target file
    target_path_str = args.target_file or ops_dict.get("target_file") or ""
    if not target_path_str:
        # Fallback: use template file path with _output suffix
        template_file = ops_dict.get("template_file", "") or (args.template_file or "")
        if template_file:
            target_path_str = str(Path(template_file).with_suffix(".docx"))
        else:
            raise ValueError("Cannot determine target file. Provide --target-file or set target_file in execution_ops.json.")

    target_path = Path(target_path_str)

    # If template is provided and target is different, copy template to target
    template_file = args.template_file or ops_dict.get("template_file", "")
    if template_file and str(template_file) != str(target_path):
        import shutil
        tpl = Path(template_file)
        if tpl.exists():
            # Create target parent directory if needed
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(tpl), str(target_path))
            print(f"[execute_execution_ops] Copied {tpl} → {target_path}")
        else:
            print(f"[execute_execution_ops] Warning: template {tpl} not found, target will be created from scratch")

    print(f"[execute_execution_ops] Reading ops from: {ops_file}")
    print(f"[execute_execution_ops] Target: {target_path}")

    # Get range info for anchor resolution
    range_info = ops_dict.get("selected_replace_range") or ops_dict.get("range") or None

    # Get prototype roles for style fallback
    prototype_roles = ops_dict.get("prototype_roles") or {}

    # Execute
    start = time.perf_counter()
    print(f"[execute_execution_ops] Executing {len(ops_list)} operations...")

    report = execute_ops_batch(
        ops_list,
        target_path,
        range_info=range_info,
    )

    duration = round(time.perf_counter() - start, 2)

    report["duration_seconds"] = duration
    report["template_file"] = template_file
    report["target_file"] = str(target_path)
    report["prototype_roles_count"] = len(prototype_roles)

    # Write report
    report_path = run_dir / "execute_ops_report.json"
    write_json(report_path, report)
    write_json(run_dir / "run.json", {
        "status": "failed" if report["failed"] > 0 else "built",
        "artifacts": {"execute_ops_report": str(report_path)},
    })

    status = "completed" if report["failed"] == 0 else "partial"
    print(f"[execute_execution_ops] {status}: {report['succeeded']} succeeded, "
          f"{report['failed']} failed, {report['removed_count']} removed, "
          f"{report['inserted_paragraphs']} paragraphs, "
          f"{report['inserted_tables']} tables in {duration}s")

    if report["errors"]:
        print(f"[execute_execution_ops] Errors: {len(report['errors'])}")
        for err in report["errors"][:5]:  # show first 5
            print(f"  - {err}")

    if report["failed"] > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
