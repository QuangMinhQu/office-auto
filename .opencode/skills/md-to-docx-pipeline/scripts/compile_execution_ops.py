from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import read_json, write_json
from semantic_grounding import derive_render_window


SEQUENTIAL_ANCHORS = {None, "", "previous", "selected_replace_range", "selected_replace_range.insert_after_path"}
HEADING_ROLES = {"h1", "h2", "h3", "legal_chuong", "legal_dieu"}


def resolve_selected_range(payload: dict, template_inspection: dict | None = None) -> tuple[dict | None, list[str]]:
    blocking_reasons: list[str] = []

    selected_range = payload.get("selected_replace_range")
    if isinstance(selected_range, dict) and selected_range.get("status") == "resolved":
        return selected_range, blocking_reasons

    remove_paths = payload.get("remove_paths")
    insert_after_path = payload.get("insert_after_path") or payload.get("anchor")
    if isinstance(remove_paths, list) and insert_after_path:
        return {
            "name": "llm-provided-range",
            "status": "resolved",
            "remove_scope": "direct-body-children",
            "remove_paths": [str(path) for path in remove_paths],
            "insert_after_path": str(insert_after_path),
            "preserve_zones": payload.get("preserve_zones", []),
        }, blocking_reasons

    blocking_reasons.append("Thiếu selected_replace_range rõ ràng cho execution_ops.json.")
    return None, blocking_reasons


def default_prototype_path(role: str, ops_payload: dict) -> str | None:
    prototype_roles = ops_payload.get("prototype_roles") or {}
    prototype = prototype_roles.get(role) or prototype_roles.get("body") or {}
    return prototype.get("path")


def normalize_anchor(anchor: str | None) -> str | None:
    if anchor is None:
        return None
    normalized = str(anchor).strip()
    return normalized or None


def compile_ops_to_render_ops(ops_payload: dict) -> tuple[list[dict], list[dict], dict]:
    render_ops: list[dict] = []
    additional_remove_commands: list[dict] = []
    style_map: dict[str, str] = {}

    for index, operation in enumerate(ops_payload.get("ops", [])):
        op_name = operation.get("op")
        if op_name == "remove":
            path = operation.get("path")
            if path:
                additional_remove_commands.append({"command": "remove", "path": str(path)})
            continue

        if op_name == "insert_table_after":
            rows = operation.get("rows", [])
            column_count = max((len(row.get("cells", [])) for row in rows), default=0)
            render_ops.append(
                {
                    "index": index,
                    "kind": "table",
                    "role": "table",
                    "block_type": "table",
                    "anchor": normalize_anchor(operation.get("anchor")),
                    "rows": rows,
                    "row_count": len(rows),
                    "column_count": column_count,
                }
            )
            continue

        if op_name != "insert_paragraph_after":
            continue

        role = str(operation.get("role") or "body")
        style = str(operation.get("style") or "Normal")
        run_props = dict(operation.get("run_props") or {})
        set_props = {"style": style, **run_props}
        text = str(operation.get("text") or "")
        if text:
            set_props["text"] = text
        style_map.setdefault(role, style)
        render_ops.append(
            {
                "index": index,
                "kind": "paragraph",
                "role": role,
                "block_type": operation.get("block_type") or ("heading" if role in HEADING_ROLES else "paragraph"),
                "anchor": normalize_anchor(operation.get("anchor")),
                "prototype_path": operation.get("prototype_path") or default_prototype_path(role, ops_payload),
                "fallback_style": style,
                "set_props": set_props,
                "append_runs": list(operation.get("append_runs") or []),
                "bookmarks": list(operation.get("bookmarks") or []),
            }
        )

    return render_ops, additional_remove_commands, style_map


def compile_execution_artifacts(
    *,
    run_dir: Path,
    template_inspection: dict,
    ops_payload: dict,
    source_file: str | None,
    template_file: str,
    target_file: str,
) -> tuple[dict, dict, dict]:
    existing_run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    existing_artifacts = dict(existing_run_state.get("artifacts") or {})
    content_ast = read_json(run_dir / "content_ast.json") if (run_dir / "content_ast.json").exists() else {"blocks": []}
    selected_range, blocking_reasons = resolve_selected_range(ops_payload, template_inspection)

    render_ops, extra_remove_commands, style_map = compile_ops_to_render_ops(ops_payload)
    remove_batch_commands = []
    if selected_range and selected_range.get("status") == "resolved":
        remove_batch_commands.extend(
            {"command": "remove", "path": path}
            for path in reversed(selected_range.get("remove_paths", []))
        )
    remove_batch_commands.extend(extra_remove_commands)

    ready = bool(selected_range and selected_range.get("status") == "resolved" and not blocking_reasons)
    source_render_window = derive_render_window(
        content_ast.get("blocks", []),
        sample_content_file=existing_artifacts.get("sample_content"),
    )
    plan = {
        "contract_version": "3.0",
        "mode_requested": "preserve-template-scaffold",
        "mode": "preserve-template-scaffold",
        "source_file": source_file,
        "template_file": template_file,
        "target_file": target_file,
        "heading_count": len([op for op in render_ops if op.get("role") in HEADING_ROLES]),
        "style_map": style_map,
        "prototype_roles": ops_payload.get("prototype_roles", {}),
        "preserve": ops_payload.get("preserve", []),
        "preserve_zones": list((selected_range or {}).get("preserve_zones", [])),
        "replace_ranges": [selected_range] if selected_range else [],
        "selected_replace_range": selected_range,
        "field_dependencies": {
            "field_count": len(template_inspection.get("field_entries", [])),
            "toc_count": len(template_inspection.get("toc_entries", [])),
        },
        "bookmark_dependencies": {
            "template_bookmark_count": len(
                [
                    bookmark
                    for paragraph in template_inspection.get("body_paragraphs", [])
                    for bookmark in paragraph.get("bookmarks", [])
                ]
            )
        },
        "post_conditions": [
            "headers-footers-preserved",
            "section-breaks-preserved",
            "llm-provided-execution-ops-used",
            "replace-range-operates-on-direct-body-children",
        ],
        "execution_strategy": "llm-execution-ops",
        "execution_artifacts": {
            "template_inspection_raw": str(run_dir / "template_inspection_raw.json"),
            "execution_ops": str(run_dir / "execution_ops.json"),
            "execution_plan": str(run_dir / "execution_plan.json"),
        },
        "semantic_grounding": {
            key: value
            for key, value in {
                "normalized_markdown": existing_artifacts.get("normalized_markdown"),
                "pandoc_style_spec": existing_artifacts.get("pandoc_style_spec"),
                "sample_content": existing_artifacts.get("sample_content"),
                "sample_outline": existing_artifacts.get("sample_outline"),
                "source_render_window": source_render_window,
            }.items()
            if value
        },
        "planner_diagnostics": {
            "ops_count": len(ops_payload.get("ops", [])),
            "compiler": "compile_execution_ops.py",
            "source_render_window": source_render_window,
        },
        "status": "ready-for-execution" if ready else "blocked",
        "blocking_reasons": blocking_reasons,
    }

    execution_plan = {
        "status": "ready" if ready else "blocked",
        "template_file": template_file,
        "target_file": target_file,
        "selected_replace_range": selected_range,
        "remove_batch_commands": remove_batch_commands,
        "render_ops": render_ops,
        "render_summary": {
            "paragraph_like_ops": len([operation for operation in render_ops if operation.get("kind") == "paragraph"]),
            "table_ops": len([operation for operation in render_ops if operation.get("kind") == "table"]),
        },
        "toc_refresh_strategy": "rewrite-toc-fields-on-open",
        "blocking_reasons": blocking_reasons,
    }

    run_state = {
        **existing_run_state,
        "mode_requested": "preserve-template-scaffold",
        "mode": "preserve-template-scaffold",
        "source_file": source_file,
        "template_file": template_file,
        "target_file": target_file,
        "preserve": plan.get("preserve", []),
        "replace_ranges": plan.get("replace_ranges", []),
        "selected_replace_range": selected_range,
        "artifacts": {
            **existing_artifacts,
            "content_ast": str(run_dir / "content_ast.json"),
            "content_outline": str(run_dir / "content_outline.json"),
            "template_inspection_raw": str(run_dir / "template_inspection_raw.json"),
            "execution_ops": str(run_dir / "execution_ops.json"),
            "plan": str(run_dir / "plan.json"),
            "execution_plan": str(run_dir / "execution_plan.json"),
        },
        "status": "planned" if ready else "blocked",
    }
    return plan, execution_plan, run_state


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile execution_ops.json thành execution_plan.json theo đường cơ học.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--ops-file", required=True)
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--target-file", required=True)
    parser.add_argument("--source-file", required=False)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    ops_payload = read_json(Path(args.ops_file))
    template_inspection = read_json(run_dir / "template_inspection_raw.json")
    write_json(run_dir / "execution_ops.json", ops_payload)

    plan, execution_plan, run_state = compile_execution_artifacts(
        run_dir=run_dir,
        template_inspection=template_inspection,
        ops_payload=ops_payload,
        source_file=args.source_file,
        template_file=args.template_file,
        target_file=args.target_file,
    )
    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "execution_plan.json", execution_plan)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()