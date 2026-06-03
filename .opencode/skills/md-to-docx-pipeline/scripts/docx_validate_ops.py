#!/usr/bin/env python3
"""docx_validate_ops.py — warn-only validator, zero blocking.

Validates LLM-generated execution_ops.json against raw template inspection.
This is a PRIMITIVE TOOL — it does NOT make decisions, it only reports warnings.

The LLM reads the warnings and decides whether to fix execution_ops.json
before passing it to docx_apply_ops (execute_execution_ops.py).

No dependencies on compile_execution_ops.py or any heuristic scripts.
Fully independent per issue.md architecture.

Usage:
    python docx_validate_ops.py --run-dir <path> [--ops-file <path>]
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from officecli_native import read_json, write_json


# Sequential anchors that don't need explicit path matching
SEQUENTIAL_ANCHORS = {"previous", "selected_replace_range", "selected_replace_range.insert_after_path", None, ""}

# All supported op types per issue.md spec
SUPPORTED_OPS = {
    "insert_paragraph_after",
    "insert_paragraph_before",
    "remove",
    "update_text",
    "insert_table",
    "insert_table_after",
    "set_page_layout",
}


def collect_known_style_ids(template_inspection: dict) -> set[str]:
    """Collect all style_ids from template inspection (new schema)."""
    style_ids: set[str] = set()

    # New schema: styles_raw
    for entry in template_inspection.get("styles_raw", []):
        sid = entry.get("style_id")
        if sid:
            style_ids.add(str(sid))
        name = entry.get("name")
        if name:
            style_ids.add(str(name))

    return style_ids


def collect_known_para_ids(template_inspection: dict) -> set[str]:
    """Collect all para_ids from template inspection (new schema).

    Priority:
    1. all_para_ids — full document paraIds (ground truth for validator)
    2. paragraph_sample — first N paragraphs (fallback, limited to 30)

    This ensures anchors beyond the first 30 paragraphs are still validated.
    """
    para_ids: set[str] = set()

    # Priority 1: all_para_ids (full document, no sampling)
    for entry in template_inspection.get("all_para_ids", []):
        pid = entry.get("para_id")
        if pid:
            para_ids.add(str(pid))

    # Fallback: paragraph_sample (first N paragraphs, max 30)
    if not para_ids:
        for entry in template_inspection.get("paragraph_sample", []):
            pid = entry.get("para_id")
            if pid:
                para_ids.add(str(pid))

    return para_ids


def collect_known_paths(template_inspection: dict) -> set[str]:
    """Collect all known paths from template inspection.

    Reads from docx_inspect_output.json (new schema) or template_inspection_raw.json (legacy).
    """
    known_paths: set[str] = set()

    # New schema: paragraph_sample (docx_inspect_output.json)
    for entry in template_inspection.get("paragraph_sample", []):
        pid = entry.get("para_id")
        if pid:
            known_paths.add(f"/body/p[@paraId={pid}]")

    # Legacy schema fallback (template_inspection_raw.json)
    body_structure = template_inspection.get("body_structure_raw", {})
    for child in body_structure.get("direct_body_children", []):
        if child.get("para_id"):
            known_paths.add(f"/body/p[@paraId={child['para_id']}]")

    for entry in template_inspection.get("body_children", []):
        if entry.get("path"):
            known_paths.add(str(entry.get("path")))

    for entry in template_inspection.get("body_paragraphs", []):
        if entry.get("path"):
            known_paths.add(str(entry.get("path")))

    for entry in template_inspection.get("toc_entries", []):
        if entry.get("path"):
            known_paths.add(str(entry.get("path")))

    for entry in template_inspection.get("field_entries", []):
        if entry.get("path"):
            known_paths.add(str(entry.get("path")))

    return known_paths


def resolve_anchor_for_op(operation: dict, known_paths: set[str], known_para_ids: set[str]) -> tuple[str, bool]:
    """Resolve and validate anchor for an operation.

    Returns (resolved_anchor, is_valid).
    """
    anchor = operation.get("anchor")

    # Sequential anchors are always valid (case-insensitive check)
    if anchor and str(anchor).lower() in {a.lower() for a in SEQUENTIAL_ANCHORS if a}:
        return str(anchor) if anchor else "sequential", True

    anchor_str = str(anchor)

    # Check if anchor is a paraId reference
    if anchor_str.startswith("/body/p[@paraId="):
        para_id = anchor_str.split("@paraId=")[1].rstrip("]")
        if para_id in known_para_ids:
            return anchor_str, True
        return anchor_str, False

    # Check if anchor is a direct path
    if anchor_str in known_paths:
        return anchor_str, True

    return anchor_str, False


def validate_ops_payload(ops_payload: dict, template_inspection: dict) -> list[dict]:
    """Validate execution_ops.json against template inspection.

    Returns list of warning dicts with op_index, type, message, severity.
    No blocking — only warnings for LLM to review.
    """
    warnings: list[dict] = []

    known_style_ids = collect_known_style_ids(template_inspection)
    known_paths = collect_known_paths(template_inspection)
    known_para_ids = collect_known_para_ids(template_inspection)

    # Check if ops_payload has ops array or is itself the ops array
    if isinstance(ops_payload, list):
        ops = ops_payload
    else:
        ops = ops_payload.get("ops", [])

    for index, operation in enumerate(ops, start=1):
        op_name = str(operation.get("op") or "")

        # Check if op type is supported
        if op_name not in SUPPORTED_OPS:
            warnings.append({
                "op_index": index,
                "type": "unknown_op",
                "message": f"Op type '{op_name}' không nằm trong danh sách supported ops. "
                           f"Supported: {sorted(SUPPORTED_OPS)}",
                "severity": "high",
            })
            continue

        # Validate based on op type
        if op_name in ("insert_paragraph_after", "insert_paragraph_before"):
            anchor = operation.get("anchor")
            if not anchor:
                warnings.append({
                    "op_index": index,
                    "type": "missing_anchor",
                    "message": f"Thiếu anchor tường minh; executor sẽ fallback sang anchor tuần tự hiện tại.",
                    "severity": "medium",
                })
            else:
                resolved, is_valid = resolve_anchor_for_op(operation, known_paths, known_para_ids)
                if not is_valid:
                    warnings.append({
                        "op_index": index,
                        "type": "unknown_anchor",
                        "message": f"Anchor `{resolved}` không tìm thấy trong template. "
                                   f"Có {len(known_para_ids)} paraIds trong paragraph_sample.",
                        "severity": "high",
                    })

            # Validate style
            style = operation.get("style")
            if style and str(style) not in known_style_ids:
                warnings.append({
                    "op_index": index,
                    "type": "unknown_style",
                    "message": f"Style '{style}' không tồn tại trong template. "
                               f"Styles có sẵn: {sorted(known_style_ids)[:10]}{'...' if len(known_style_ids) > 10 else ''}",
                    "severity": "high",
                })

            # Validate run_props structure
            run_props = operation.get("run_props")
            if run_props and not isinstance(run_props, dict):
                warnings.append({
                    "op_index": index,
                    "type": "invalid_run_props",
                    "message": f"run_props phải là dict, nhận được {type(run_props).__name__}.",
                    "severity": "medium",
                })

            # Validate para_props structure
            para_props = operation.get("para_props")
            if para_props and not isinstance(para_props, dict):
                warnings.append({
                    "op_index": index,
                    "type": "invalid_para_props",
                    "message": f"para_props phải là dict, nhận được {type(para_props).__name__}.",
                    "severity": "medium",
                })

        elif op_name == "remove":
            path = operation.get("path")
            if not path:
                warnings.append({
                    "op_index": index,
                    "type": "missing_path",
                    "message": "Remove op thiếu 'path'.",
                    "severity": "high",
                })
            elif str(path) not in known_paths:
                warnings.append({
                    "op_index": index,
                    "type": "unknown_path",
                    "message": f"Remove path `{path}` không tìm thấy trong template.",
                    "severity": "high",
                })

        elif op_name == "update_text":
            path = operation.get("path")
            if not path:
                warnings.append({
                    "op_index": index,
                    "type": "missing_path",
                    "message": "update_text op thiếu 'path'.",
                    "severity": "high",
                })
            elif str(path) not in known_paths:
                warnings.append({
                    "op_index": index,
                    "type": "unknown_path",
                    "message": f"update_text path `{path}` không tìm thấy trong template.",
                    "severity": "high",
                })

        elif op_name in ("insert_table", "insert_table_after"):
            anchor = operation.get("anchor")
            if not anchor:
                warnings.append({
                    "op_index": index,
                    "type": "missing_anchor",
                    "message": "insert_table op thiếu 'anchor'.",
                    "severity": "high",
                })
            elif anchor not in SEQUENTIAL_ANCHORS:
                resolved, is_valid = resolve_anchor_for_op(operation, known_paths, known_para_ids)
                if not is_valid:
                    warnings.append({
                        "op_index": index,
                        "type": "unknown_anchor",
                        "message": f"Table anchor `{resolved}` không tìm thấy trong template.",
                        "severity": "high",
                    })

            # Validate table structure
            rows = operation.get("rows", [])
            if not rows:
                warnings.append({
                    "op_index": index,
                    "type": "empty_table",
                    "message": "insert_table op có 'rows' rỗng hoặc thiếu.",
                    "severity": "medium",
                })

        elif op_name == "set_page_layout":
            # set_page_layout doesn't need anchor, just validate structure
            margins = operation.get("margins")
            paper_size = operation.get("paper_size")
            orientation = operation.get("orientation")

            if not margins and not paper_size and not orientation:
                warnings.append({
                    "op_index": index,
                    "type": "empty_page_layout",
                    "message": "set_page_layout op không có margins, paper_size, hoặc orientation.",
                    "severity": "medium",
                })

    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="docx_validate_ops: warn-only validator, zero blocking. "
                    "LLM reads warnings and self-fixes execution_ops.json."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory with docx_inspect_output.json")
    parser.add_argument("--ops-file", required=False, default=None,
                        help="Path to execution_ops.json (default: <run-dir>/execution_ops.json)")
    parser.add_argument("--output-file", default="execution_ops_validation.json",
                        help="Output validation report filename")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)

    # Read ops file
    ops_file = Path(args.ops_file) if args.ops_file else run_dir / "execution_ops.json"
    if not ops_file.exists():
        raise FileNotFoundError(f"execution_ops.json not found at: {ops_file}")

    ops_payload = read_json(ops_file)

    # Read template inspection (new schema: docx_inspect_output.json)
    inspect_file = run_dir / "docx_inspect_output.json"
    if not inspect_file.exists():
        # Fallback to legacy schema
        inspect_file = run_dir / "template_inspection_raw.json"
    if not inspect_file.exists():
        raise FileNotFoundError(f"Neither docx_inspect_output.json nor template_inspection_raw.json found in: {run_dir}")

    template_inspection = read_json(inspect_file)

    # Validate
    warnings = validate_ops_payload(ops_payload, template_inspection)

    # Build report
    report = {
        "status": "ok" if not warnings else "warnings",
        "warning_count": len(warnings),
        "high_severity_count": len([w for w in warnings if w.get("severity") == "high"]),
        "medium_severity_count": len([w for w in warnings if w.get("severity") == "medium"]),
        "low_severity_count": len([w for w in warnings if w.get("severity") == "low"]),
        "warnings": warnings,
        "total_ops": len(ops_payload.get("ops", [])) if isinstance(ops_payload, dict) else len(ops_payload),
    }

    output_path = run_dir / args.output_file
    write_json(output_path, report)

    # Update run.json
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["execution_ops_validation"] = str(output_path)
    write_json(run_dir / "run.json", run_state)

    # Print summary
    print(f"[docx_validate_ops] Validation complete: {report['warning_count']} warnings "
          f"({report['high_severity_count']} high, {report['medium_severity_count']} medium)")
    if warnings:
        print("[docx_validate_ops] Warnings:")
        for w in warnings[:10]:  # Show first 10
            print(f"  op#{w['op_index']} [{w['severity']}]: {w['message'][:100]}")
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")

    print(f"[docx_validate_ops] Report written to: {output_path}")
    print("[docx_validate_ops] NEXT STEP: LLM reviews warnings → fixes execution_ops.json if needed")


if __name__ == "__main__":
    main()
