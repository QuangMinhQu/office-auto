from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import normalize_text, read_json, to_int, write_json
from semantic_grounding import filter_blocks


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def normalize_heading_text(text: str) -> str:
    return normalize_text(strip_heading_numbering(text))


def block_text(block: dict) -> str:
    if block.get("type") == "reference":
        return str(block.get("text", "")).strip()
    if block.get("type") == "list_item":
        if block.get("ordered"):
            return f"{block.get('ordinal', 1)}. {block.get('text', '').strip()}"
        return f"• {block.get('text', '').strip()}"
    if block.get("type") == "table":
        rows = block.get("rows", [])
        return "\n".join(" | ".join(str(cell.get("text") or "") for cell in row.get("cells", [])) for row in rows)
    return str(block.get("text", "")).strip()


def block_runs(block: dict) -> list[dict]:
    runs = block.get("runs")
    if isinstance(runs, list) and runs:
        return [run for run in runs if str(run.get("text", ""))]
    fallback = block_text(block)
    return [] if not fallback else [{"text": fallback}]


def role_for_block(block: dict) -> str:
    block_type = block.get("type")
    if block_type == "heading":
        level = int(block.get("level", 1))
        if level <= 1:
            return "h1"
        if level == 2:
            return "h2"
        return "h3"
    if block_type == "reference":
        return "reference"
    if block_type == "list_item":
        return "list"
    if block_type == "blockquote":
        return "blockquote"
    if block_type == "code_block":
        return "code"
    if block_type == "table":
        return "table"
    return "body"


def prototype_paragraph_defaults(role: str, prototype_catalog: dict) -> dict:
    role_prototype = prototype_catalog.get(role) or {}
    if role_prototype:
        return role_prototype
    if role in {"body", "list", "reference", "blockquote", "code"}:
        return prototype_catalog.get("body", {})
    return {}


def inherits_emphasis_defaults(role: str) -> bool:
    return role in {"h1", "h2", "h3", "code"}


def prefers_justified_body_alignment(role: str) -> bool:
    return role in {"body", "list", "reference", "blockquote"}


def paragraph_set_props(block: dict, role: str, style_map: dict, prototype_catalog: dict, first_run: dict | None = None) -> dict:
    props: dict = {}
    prototype = prototype_paragraph_defaults(role, prototype_catalog)
    if role in {"h1", "h2", "h3", "body", "list", "reference", "blockquote", "code"}:
        props["style"] = style_map.get(role, style_map.get("body", "Normal"))

    paragraph_format = prototype.get("paragraph_format", {})
    for source_key, target_key in [
        ("align", "align"),
        ("space_before", "spaceBefore"),
        ("space_after", "spaceAfter"),
        ("line_spacing", "lineSpacing"),
        ("line_rule", "lineRule"),
        ("hanging_indent", "hangingIndent"),
    ]:
        value = paragraph_format.get(source_key)
        if value not in (None, ""):
            if target_key == "align" and prefers_justified_body_alignment(role) and str(value).lower() == "center":
                continue
            props.setdefault(target_key, value)

    if prefers_justified_body_alignment(role) and "align" not in props:
        props["align"] = "justify"

    if block.get("type") == "list_item":
        props["listStyle"] = "ordered" if block.get("ordered") else "bullet"
        level = to_int(block.get("level"))
        if level is not None and level > 0:
            props["numLevel"] = level

    if block.get("type") == "reference":
        reference_prototype = prototype_catalog.get("reference", {})
        if reference_prototype.get("num_id") is not None:
            props["numId"] = reference_prototype["num_id"]
        if reference_prototype.get("ilvl") is not None:
            props["numLevel"] = reference_prototype["ilvl"]
        paragraph_format = reference_prototype.get("paragraph_format", {})
        for source_key, target_key in [
            ("align", "align"),
            ("space_before", "spaceBefore"),
            ("space_after", "spaceAfter"),
            ("line_spacing", "lineSpacing"),
            ("line_rule", "lineRule"),
            ("hanging_indent", "hangingIndent"),
        ]:
            value = paragraph_format.get(source_key)
            if value not in (None, ""):
                props[target_key] = value

    prototype_first_run = next((run for run in prototype.get("runs", []) if str(run.get("text") or "")), {})
    for source_key, target_key in [
        ("font_ascii", "font"),
        ("font_latin", "font"),
        ("size", "size"),
        ("color", "color"),
    ]:
        value = prototype_first_run.get(source_key)
        if value not in (None, ""):
            props.setdefault(target_key, value)

    if inherits_emphasis_defaults(role):
        for source_key, target_key in [("bold", "bold"), ("italic", "italic"), ("underline", "underline")]:
            value = prototype_first_run.get(source_key)
            if value not in (None, ""):
                props.setdefault(target_key, value)

    for source_key, target_key in [
        ("font_ascii", "font"),
        ("font_latin", "font"),
        ("size", "size"),
        ("color", "color"),
        ("bold", "bold"),
        ("italic", "italic"),
        ("underline", "underline"),
    ]:
        value = (first_run or {}).get(source_key)
        if value not in (None, ""):
            props[target_key] = value
    return props


def run_props(run_info: dict, role: str, prototype_catalog: dict) -> dict:
    prototype = prototype_paragraph_defaults(role, prototype_catalog)
    prototype_first_run = next((run for run in prototype.get("runs", []) if str(run.get("text") or "")), {})
    props = {"text": str(run_info.get("text", ""))}
    code_role = role == "code"
    if run_info.get("bold"):
        props["bold"] = True
    elif inherits_emphasis_defaults(role) and prototype_first_run.get("bold"):
        props["bold"] = True
    if run_info.get("italic"):
        props["italic"] = True
    elif inherits_emphasis_defaults(role) and prototype_first_run.get("italic"):
        props["italic"] = True
    if run_info.get("underline"):
        props["underline"] = True
    elif inherits_emphasis_defaults(role) and prototype_first_run.get("underline"):
        props["underline"] = prototype_first_run["underline"]
    if run_info.get("color"):
        props["color"] = run_info["color"]
    elif prototype_first_run.get("color"):
        props["color"] = prototype_first_run["color"]
    if run_info.get("size"):
        props["size"] = run_info["size"]
    elif prototype_first_run.get("size"):
        props["size"] = prototype_first_run["size"]
    if run_info.get("font_ascii"):
        props["font"] = run_info["font_ascii"]
    elif run_info.get("font_latin"):
        props["font"] = run_info["font_latin"]
    elif prototype_first_run.get("font_ascii"):
        props["font"] = prototype_first_run["font_ascii"]
    elif prototype_first_run.get("font_latin"):
        props["font"] = prototype_first_run["font_latin"]
    elif code_role:
        props["font"] = "Courier New"
    return props


def heading_bookmark_map(template_profile: dict, selected_range: dict | None) -> dict[str, list[dict]]:
    replace_paths = set((selected_range or {}).get("remove_paths", []))
    bookmark_map: dict[str, list[dict]] = {}

    for heading in template_profile.get("document_profile", {}).get("headings", []):
        direct_body_path = heading.get("direct_body_path") or heading.get("path")
        if replace_paths and direct_body_path not in replace_paths:
            continue
        text = str(heading.get("text") or "").strip()
        bookmarks = heading.get("bookmarks") or []
        if text and bookmarks:
            bookmark_map[normalize_heading_text(text)] = bookmarks
    return bookmark_map


def compile_paragraph_operation(block: dict, style_map: dict, prototype_catalog: dict, bookmark_map: dict[str, list[dict]]) -> dict:
    role = role_for_block(block)
    prototype = prototype_catalog.get(role) or prototype_catalog.get("body") or {}
    runs = block_runs(block)
    first_run = runs[0] if runs else {"text": block_text(block)}
    paragraph_props = paragraph_set_props(block, role, style_map, prototype_catalog, first_run)
    set_props = dict(paragraph_props)
    if first_run.get("text"):
        set_props["text"] = str(first_run.get("text") or "")

    append_runs = [run_props(run, role, prototype_catalog) for run in runs[1:] if str(run.get("text") or "")]
    bookmarks = []
    if block.get("type") == "heading":
        bookmarks = bookmark_map.get(normalize_heading_text(str(block.get("text") or "")), [])

    return {
        "kind": "paragraph",
        "role": role,
        "block_type": block.get("type"),
        "source_line": block.get("line"),
        "prototype_path": prototype.get("path"),
        "fallback_style": style_map.get(role, style_map.get("body", "Normal")),
        "set_props": set_props,
        "append_runs": append_runs,
        "bookmarks": bookmarks,
    }


def compile_table_operation(block: dict) -> dict:
    rows = block.get("rows", [])
    column_count = max((len(row.get("cells", [])) for row in rows), default=0)
    return {
        "kind": "table",
        "role": "table",
        "block_type": "table",
        "source_line": block.get("line"),
        "rows": rows,
        "row_count": len(rows),
        "column_count": column_count,
    }


def compile_block_operation(block: dict, style_map: dict, prototype_catalog: dict, bookmark_map: dict[str, list[dict]]) -> dict | None:
    if block.get("type") == "thematic_break":
        return {
            "kind": "paragraph",
            "role": "body",
            "block_type": "thematic_break",
            "source_line": block.get("line"),
            "prototype_path": (prototype_catalog.get("body") or {}).get("path"),
            "fallback_style": style_map.get("body", "Normal"),
            "set_props": {"style": style_map.get("body", "Normal"), "text": ""},
            "append_runs": [],
            "bookmarks": [],
        }
    if block.get("type") == "table":
        return compile_table_operation(block)
    if block.get("type") in {"heading", "paragraph", "list_item", "reference", "blockquote", "code_block"}:
        return compile_paragraph_operation(block, style_map, prototype_catalog, bookmark_map)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile execution_plan.json cho pipeline DOCX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    plan = read_json(run_dir / "plan.json")
    content_ast = read_json(run_dir / "content_ast.json")
    template_profile = read_json(run_dir / "template_profile.json")

    if plan.get("status") != "ready-for-execution":
        execution_plan = {
            "status": "blocked",
            "message": "Plan đang blocked nên không compile execution graph.",
            "remove_batch_commands": [],
            "render_ops": [],
            "blocking_reasons": plan.get("blocking_reasons", []),
        }
        write_json(run_dir / "execution_plan.json", execution_plan)
        return

    selected_range = plan.get("selected_replace_range")
    if not selected_range or selected_range.get("status") != "resolved":
        execution_plan = {
            "status": "blocked",
            "message": "Không có selected_replace_range resolved nên không compile execution graph.",
            "remove_batch_commands": [],
            "render_ops": [],
        }
        write_json(run_dir / "execution_plan.json", execution_plan)
        return

    bookmark_map = heading_bookmark_map(template_profile, selected_range)
    source_render_window = (plan.get("semantic_grounding") or {}).get("source_render_window") or {}
    blocks = filter_blocks(content_ast.get("blocks", []), source_render_window)
    render_ops = []
    for index, block in enumerate(blocks):
        operation = compile_block_operation(
            block,
            plan.get("style_map", {}),
            template_profile.get("prototype_catalog", {}),
            bookmark_map,
        )
        if operation is None:
            continue
        operation["index"] = index
        render_ops.append(operation)

    remove_batch_commands = [
        {"command": "remove", "path": path}
        for path in reversed(selected_range.get("remove_paths", []))
    ]
    execution_plan = {
        "status": "ready",
        "template_file": plan.get("template_file"),
        "target_file": plan.get("target_file"),
        "selected_replace_range": selected_range,
        "remove_batch_commands": remove_batch_commands,
        "render_ops": render_ops,
        "render_summary": {
            "paragraph_like_ops": len([operation for operation in render_ops if operation.get("kind") == "paragraph"]),
            "table_ops": len([operation for operation in render_ops if operation.get("kind") == "table"]),
        },
        "toc_refresh_strategy": "rewrite-toc-fields-on-open",
    }
    write_json(run_dir / "execution_plan.json", execution_plan)


if __name__ == "__main__":
    main()