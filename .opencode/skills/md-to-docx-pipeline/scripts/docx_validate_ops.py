#!/usr/bin/env python3
"""docx_validate_ops.py — warn-only validator, zero blocking.

Validates LLM-generated execution_ops.json against raw template inspection.
This is a PRIMITIVE TOOL — it does NOT make decisions, it only reports warnings.

The LLM reads the warnings and decides whether to fix execution_ops.json
before passing it to execute_execution_ops.py.

VALIDATION RULES FOR ANCHORS:
  - PREFERRED: "/body/p[@paraId=XXXXXXXX]" — stable paraId format
  - OK: IDX_XXXXX for legacy templates without paraIds (warning issued)
  - OK: "PREVIOUS" / sequential anchors
  - HIGH WARNING: unknown paraId or IDX that doesn't exist
  
Anchor validation ensures operations reference valid locations in the template,
preventing silent failures during execution.

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
    "insert_image",
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
    Recognizes IDX_XXXXX synthetic paraIds as valid format.
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


def has_synthetic_para_ids(template_inspection: dict) -> bool:
    """Check if template inspection contains IDX_ synthetic paraIds.

    Returns True if any paraId starts with 'IDX_' prefix.
    """
    for entry in template_inspection.get("all_para_ids", []):
        pid = entry.get("para_id", "")
        if str(pid).startswith("IDX_"):
            return True
    for entry in template_inspection.get("paragraph_sample", []):
        pid = entry.get("para_id", "")
        if str(pid).startswith("IDX_"):
            return True
    return False


def collect_front_matter_para_ids(template_inspection: dict) -> set[str]:
    """Collect para_ids that belong to front matter — purely data-driven.

    Reads is_front_matter from all_para_ids and content_map.
    No hardcoded style names or text patterns.
    """
    front_matter: set[str] = set()

    content_map = template_inspection.get("content_map", {}) or {}
    front_matter_block = content_map.get("front_matter", {}) or {}
    for pid in front_matter_block.get("para_ids", []) or []:
        if pid:
            front_matter.add(str(pid))

    for entry in template_inspection.get("all_para_ids", []):
        if entry.get("is_front_matter") and entry.get("para_id"):
            front_matter.add(str(entry.get("para_id")))

    boundary = template_inspection.get("front_matter_boundary", {}) or {}
    last_para_id = boundary.get("last_para_id")
    if last_para_id:
        front_matter.add(str(last_para_id))

    return front_matter


def build_para_meta_index(template_inspection: dict) -> dict[str, dict]:
    """Build a para_id → metadata index from all_para_ids.

    Returns {para_id: {style_name, text_preview, is_front_matter, is_synthetic_id, ...}}
    Purely data-driven — reads what docx_inspect.py dumped.
    """
    index: dict[str, dict] = {}
    for entry in template_inspection.get("all_para_ids", []):
        pid = entry.get("para_id")
        if pid:
            index[str(pid)] = {
                "style_name": entry.get("style_name"),
                "text_preview": entry.get("text_preview"),
                "is_front_matter": entry.get("is_front_matter"),
                "is_synthetic_id": entry.get("is_synthetic_id"),
                "index": entry.get("index"),
            }
    return index


def collect_style_effective_fonts(template_inspection: dict) -> dict[str, str]:
    """Build a mapping of style names/ids to effective font names when available."""
    style_fonts: dict[str, str] = {}
    for entry in template_inspection.get("styles_raw", []):
        effective_font = entry.get("effective_font")
        if not effective_font:
            continue
        for key in (entry.get("style_id"), entry.get("name")):
            if key:
                style_fonts[str(key)] = str(effective_font)
    for entry in template_inspection.get("styles_for_llm", {}).get("available_styles", []):
        effective_font = entry.get("effective_font")
        if not effective_font:
            continue
        for key in (entry.get("style_id"), entry.get("name")):
            if key:
                style_fonts[str(key)] = str(effective_font)
    return style_fonts


def collect_known_paths(template_inspection: dict) -> set[str]:
    """Collect all known paths from template inspection.

    Reads from docx_inspect_output.json (new schema) or template_inspection_raw.json (legacy).
    """
    known_paths: set[str] = set()

    # New schema: all_para_ids (full document, no sampling)
    for entry in template_inspection.get("all_para_ids", []):
        pid = entry.get("para_id")
        if pid:
            known_paths.add(f"/body/p[@paraId={pid}]")

    # Fallback to paragraph_sample if all_para_ids is empty
    if not known_paths:
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


def resolve_anchor_for_op(operation: dict, known_paths: set[str], known_para_ids: set[str], has_synthetic: bool = False) -> tuple[str, bool]:
    """Resolve and validate anchor for an operation.

    Returns (resolved_anchor, is_valid).
    """
    anchor = operation.get("anchor")

    # Sequential anchors are always valid (case-insensitive check)
    if anchor and str(anchor).lower() in {a.lower() for a in SEQUENTIAL_ANCHORS if a}:
        return str(anchor) if anchor else "sequential", True

    anchor_str = str(anchor)

    # Handle IDX_ synthetic anchors — valid format, not HIGH severity
    if anchor_str.startswith("IDX_"):
        if has_synthetic:
            return anchor_str, True  # synthetic ID is valid in this template
        return anchor_str, False

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
    front_matter_para_ids = collect_front_matter_para_ids(template_inspection)
    para_meta_index = build_para_meta_index(template_inspection)
    style_effective_fonts = collect_style_effective_fonts(template_inspection)
    has_synthetic = has_synthetic_para_ids(template_inspection)

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
                resolved, is_valid = resolve_anchor_for_op(operation, known_paths, known_para_ids, has_synthetic)
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
                    "suggested_fix": {
                        "style": next((entry.get("style_id") or entry.get("name") for entry in template_inspection.get("styles_for_llm", {}).get("available_styles", []) if entry.get("use_for") == "body paragraphs"), None),
                    },
                })

            if style and str(style) in style_effective_fonts:
                effective_font = style_effective_fonts[str(style)]
                if effective_font and operation.get("run_props") and isinstance(operation.get("run_props"), dict):
                    run_props = operation.get("run_props") or {}
                    if run_props.get("font") or run_props.get("font_name") or run_props.get("font_family"):
                        warnings.append({
                            "op_index": index,
                            "type": "font_override",
                            "message": (
                                f"run_props.font overrides style inheritance. Template effective_font for style '{style}' is '{effective_font}'. "
                                "Consider removing run_props.font to inherit from style."
                            ),
                            "severity": "medium",
                            "suggested_fix": {
                                "remove_run_props": ["font", "font_name", "font_family"],
                            },
                        })

            run_props = operation.get("run_props")
            if isinstance(run_props, dict) and any(key in run_props and run_props.get(key) not in (None, "") for key in ("size", "size_pt", "font_size_pt")):
                warnings.append({
                    "op_index": index,
                    "type": "size_override",
                    "message": "run_props.size overrides style inheritance and may drift from the template effective font size.",
                    "severity": "medium",
                    "suggested_fix": {
                        "remove_run_props": ["size", "size_pt", "font_size_pt"],
                    },
                })

            # Validate run_props structure
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
            else:
                para_id = None
                path_str = str(path)
                if path_str.startswith("/body/p[@paraId="):
                    para_id = path_str.split("@paraId=")[-1].rstrip("]")
                if para_id and para_id in front_matter_para_ids:
                    meta = para_meta_index.get(para_id, {})
                    style_name = meta.get("style_name") or "unknown"
                    text_preview = meta.get("text_preview") or ""
                    detail = f"style='{style_name}', text='{text_preview[:40]}'" if style_name else ""
                    warnings.append({
                        "op_index": index,
                        "type": "front_matter_remove",
                        "code": "REMOVE_FRONT_MATTER",
                        "message": f"Remove op targets is_front_matter=true paragraph {para_id}. {detail}".rstrip(),
                        "severity": "high",
                        "suggested_fix": {
                            "action": "remove_this_op",
                            "reason": f"Paragraph {para_id} is front matter (is_front_matter=true in inspection data)",
                        },
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

        elif op_name == "insert_image":
            anchor = operation.get("anchor")
            if not anchor:
                warnings.append({
                    "op_index": index,
                    "type": "missing_anchor",
                    "message": "insert_image op thiếu 'anchor'.",
                    "severity": "high",
                })
            else:
                resolved, is_valid = resolve_anchor_for_op(operation, known_paths, known_para_ids, has_synthetic)
                if not is_valid:
                    warnings.append({
                        "op_index": index,
                        "type": "unknown_anchor",
                        "message": f"insert_image anchor `{resolved}` không tìm thấy trong template.",
                        "severity": "high",
                    })
            image_path = operation.get("image_path")
            if not image_path:
                warnings.append({
                    "op_index": index,
                    "type": "missing_image_path",
                    "message": "insert_image op thiếu 'image_path'.",
                    "severity": "high",
                })

    # ---- Completeness checks (warn-only, run after per-op validation) ----
    completeness_warnings = _check_required_remove_ops(ops, template_inspection, para_meta_index, known_para_ids, front_matter_para_ids)
    if completeness_warnings:
        warnings.extend(completeness_warnings)

    orphan_media_warnings = _check_orphan_media(ops, template_inspection, para_meta_index, front_matter_para_ids)
    if orphan_media_warnings:
        warnings.extend(orphan_media_warnings)

    heading_warnings = _check_heading_level_consistency(ops)
    if heading_warnings:
        warnings.extend(heading_warnings)

    return warnings


def _check_required_remove_ops(
    ops: list[dict],
    template_inspection: dict,
    para_meta_index: dict,
    known_para_ids: set[str],
    front_matter_para_ids: set[str],
) -> list[dict]:
    """CRITICAL: Validate that body_placeholder paraIds have corresponding remove ops.

    Absence of required remove ops is HIGH severity - template content cũ sẽ bị giữ lại.
    """
    all_para_ids = template_inspection.get("all_para_ids", [])
    body_placeholder_ids = {
        entry["para_id"]
        for entry in all_para_ids
        if not entry.get("is_front_matter") and entry.get("para_id")
        and str(entry.get("para_id")) not in front_matter_para_ids
    }

    removed_ids: set[str] = set()
    for op in ops:
        if op.get("op") == "remove":
            path = str(op.get("path", ""))
            if path.startswith("/body/p[@paraId="):
                para_id = path.split("@paraId=")[1].rstrip("]")
                removed_ids.add(para_id)

    missing_removes = body_placeholder_ids - removed_ids
    if not missing_removes:
        return []

    significant_missing = [
        pid for pid in missing_removes
        if (para_meta_index.get(str(pid), {}).get("text_preview") or "").strip()
    ]

    warnings: list[dict] = []
    if significant_missing:
        warnings.append({
            "op_index": 0,
            "type": "missing_required_removes",
            "severity": "high",
            "code": "MISSING_REMOVE_OPS",
            "message": (
                f"CRITICAL: {len(significant_missing)} body placeholder paragraphs "
                f"không có remove op. Template content cũ sẽ bị giữ lại. "
                f"Thêm remove ops cho các paraId sau: {significant_missing[:10]}"
                f"{'...' if len(significant_missing) > 10 else ''}"
            ),
            "missing_para_ids": significant_missing[:20],
            "total_body_placeholders": len(body_placeholder_ids),
            "total_removed": len(removed_ids),
            "remove_op_count": len([op for op in ops if op.get("op") == "remove"]),
            "body_placeholder_count": len(body_placeholder_ids),
            "completeness_pct": round(len(removed_ids) / max(len(body_placeholder_ids), 1) * 100, 1),
        })

    return warnings


def _check_orphan_media(
    ops: list[dict],
    template_inspection: dict,
    para_meta_index: dict,
    front_matter_para_ids: set[str],
) -> list[dict]:
    """Warn if body placeholder paragraphs contain empty text but no remove op.

    Empty-text paragraphs in body zone are likely image/object placeholders
    that will remain in output if not removed.
    """
    removed_ids = {
        str(op.get("path", "")).split("@paraId=")[1].rstrip("]")
        for op in ops if op.get("op") == "remove" and "@paraId=" in str(op.get("path", ""))
    }

    warnings: list[dict] = []
    for entry in template_inspection.get("all_para_ids", []):
        if entry.get("is_front_matter"):
            continue
        pid = str(entry.get("para_id", ""))
        if pid in front_matter_para_ids:
            continue
        text = (entry.get("text_preview") or "").strip()
        if not text and pid not in removed_ids:
            warnings.append({
                "op_index": 0,
                "type": "possible_orphan_image",
                "severity": "medium",
                "code": "ORPHAN_MEDIA",
                "message": (
                    f"Paragraph {pid} trong body zone có text rỗng nhưng không có remove op. "
                    f"Nếu đây là image placeholder, thêm remove op."
                ),
                "para_id": pid,
            })

    return warnings


def _check_heading_level_consistency(ops: list[dict]) -> list[dict]:
    """Check if numeric heading prefix is consistent with assigned heading level.

    E.g., '# 1.4.' in markdown has depth 1 but semantic numbering 1.4 = depth 2.
    The source markdown `#` count is the source of truth.
    """
    import re

    warnings: list[dict] = []
    for i, op in enumerate(ops):
        role = str(op.get("role") or "")
        text = str(op.get("text") or "")
        style = str(op.get("style") or "")

        if role not in ("h1", "h2", "h3"):
            continue

        m = re.match(r'^(\d+(?:\.\d+)*)\.?\s+', text)
        if not m:
            continue

        numeric_depth = len(m.group(1).split('.'))
        expected_level = int(role[1])

        if numeric_depth != expected_level:
            warnings.append({
                "op_index": i + 1,
                "type": "heading_level_mismatch",
                "severity": "medium",
                "code": "HEADING_LEVEL_MISMATCH",
                "message": (
                    f"Heading '{text[:60]}' có numeric prefix depth={numeric_depth} "
                    f"nhưng role='{role}' (level {expected_level}). "
                    f"Số lượng # trong markdown là source of truth, KHÔNG dùng numbering prefix để suy luận level."
                ),
                "suggested_fix": (
                    {"role": f"h{numeric_depth}", "style": f"Heading{numeric_depth}"}
                    if numeric_depth <= 3
                    else {"note": f"numeric_depth={numeric_depth} > 3, giữ nguyên {role}"}
                ),
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
