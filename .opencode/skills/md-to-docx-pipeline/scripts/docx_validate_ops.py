from __future__ import annotations

import argparse
from pathlib import Path

from compile_execution_ops import resolve_selected_range
from officecli_native import read_json, write_json


SEQUENTIAL_ANCHORS = {"previous", "selected_replace_range", "selected_replace_range.insert_after_path"}


def collect_known_style_ids(template_inspection: dict) -> set[str]:
    return {
        str(entry.get("style_id"))
        for entry in template_inspection.get("style_catalog", [])
        if entry.get("style_id")
    }


def collect_known_paths(template_inspection: dict) -> set[str]:
    known_paths: set[str] = set()

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


def validate_ops_payload(ops_payload: dict, template_inspection: dict) -> list[str]:
    warnings: list[str] = []
    selected_range, selection_warnings = resolve_selected_range(ops_payload, template_inspection)
    warnings.extend(selection_warnings)

    known_style_ids = collect_known_style_ids(template_inspection)
    known_paths = collect_known_paths(template_inspection)
    selected_anchor = str((selected_range or {}).get("insert_after_path") or "")

    for index, operation in enumerate(ops_payload.get("ops", []), start=1):
        op_name = str(operation.get("op") or "")
        if op_name in {"insert_paragraph_after", "insert_table_after"}:
            anchor = operation.get("anchor")
            if not anchor:
                warnings.append(f"op#{index}: thiếu anchor tường minh; builder sẽ fallback sang anchor tuần tự hiện tại.")
            elif anchor not in SEQUENTIAL_ANCHORS and str(anchor) not in known_paths and str(anchor) != selected_anchor:
                warnings.append(f"op#{index}: anchor `{anchor}` không thấy trong template_inspection_raw.")

        if op_name == "insert_paragraph_after":
            style = operation.get("style")
            if style and str(style) not in known_style_ids:
                warnings.append(f"op#{index}: style `{style}` không tồn tại trong style_catalog của template.")
            prototype_path = operation.get("prototype_path")
            if prototype_path and str(prototype_path) not in known_paths:
                warnings.append(f"op#{index}: prototype_path `{prototype_path}` không thấy trong template_inspection_raw.")

        if op_name == "remove":
            path = operation.get("path")
            if path and str(path) not in known_paths:
                warnings.append(f"op#{index}: remove path `{path}` không thấy trong template_inspection_raw.")

    return warnings


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate execution_ops.json và trả warnings không chặn build.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--ops-file", required=True)
    parser.add_argument("--output-file", default="execution_ops_validation.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ops_payload = read_json(Path(args.ops_file))
    template_inspection = read_json(run_dir / "template_inspection_raw.json")
    warnings = validate_ops_payload(ops_payload, template_inspection)
    report = {
        "status": "warnings" if warnings else "ok",
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    write_json(run_dir / args.output_file, report)

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["execution_ops_validation"] = str(run_dir / args.output_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()