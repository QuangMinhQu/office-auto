from __future__ import annotations

import argparse
import os
import re
import shutil
from pathlib import Path

from officecli_native import (
    OfficeCliError,
    ensure_officecli_available,
    extract_added_path,
    normalize_text,
    officecli_add,
    officecli_close,
    officecli_refresh,
    officecli_open,
    officecli_query,
    officecli_remove,
    officecli_save,
    officecli_set,
    officecli_view,
    read_json,
    to_int,
    write_json,
)


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def normalize_heading_text(text: str) -> str:
    return normalize_text(strip_heading_numbering(text))


def paragraph_style(block: dict, style_map: dict) -> str:
    if block.get("type") == "heading":
        level = int(block.get("level", 1))
        if level <= 1:
            return style_map.get("h1", "Heading1")
        if level == 2:
            return style_map.get("h2", "Heading2")
        return style_map.get("h3", "Heading3")
    if block.get("type") == "reference":
        return style_map.get("reference", style_map.get("body", "Normal"))
    if block.get("type") == "list_item":
        return style_map.get("list", style_map.get("body", "Normal"))
    return style_map.get("body", "Normal")


def block_text(block: dict) -> str:
    if block.get("type") == "table_row":
        return " | ".join(block.get("cells", []))
    if block.get("type") == "reference":
        return str(block.get("text", "")).strip()
    if block.get("type") == "list_item":
        if block.get("ordered"):
            return f"{block.get('ordinal', 1)}. {block.get('text', '').strip()}"
        return f"• {block.get('text', '').strip()}"
    return str(block.get("text", "")).strip()


def block_runs(block: dict) -> list[dict]:
    runs = block.get("runs")
    if isinstance(runs, list) and runs:
        return [run for run in runs if str(run.get("text", ""))]
    fallback = block_text(block)
    return [] if not fallback else [{"text": fallback}]


def reference_profile(template_profile: dict) -> dict:
    payload = template_profile.get("reference_profile")
    return payload if isinstance(payload, dict) else {}


def heading_bookmark_map(template_profile: dict, replace_range: dict) -> dict[str, list[dict]]:
    replace_paths = set(replace_range.get("remove_paths", []))
    bookmark_map: dict[str, list[dict]] = {}

    for heading in template_profile.get("document_profile", {}).get("headings", []):
        if replace_paths and heading.get("path") not in replace_paths:
            continue
        text = str(heading.get("text") or "").strip()
        bookmarks = heading.get("bookmarks") or []
        if text and bookmarks:
            bookmark_map[normalize_heading_text(text)] = bookmarks

    return bookmark_map


def run_props(run_info: dict, block: dict | None = None, template_profile: dict | None = None) -> dict:
    props = {"text": str(run_info.get("text", ""))}
    reference_format = reference_profile(template_profile or {}) if block and block.get("type") == "reference" else {}
    if reference_format.get("size"):
        props["size"] = reference_format["size"]
    if reference_format.get("font_ascii"):
        props["font"] = reference_format["font_ascii"]
    if run_info.get("bold"):
        props["bold"] = True
    if run_info.get("italic"):
        props["italic"] = True
    if run_info.get("code"):
        props["font"] = "Courier New"
    return props


def paragraph_props(block: dict, style_map: dict, template_profile: dict) -> dict:
    props: dict = {"style": paragraph_style(block, style_map)}
    if block.get("type") == "list_item":
        props["listStyle"] = "ordered" if block.get("ordered") else "bullet"
        level = to_int(block.get("level"))
        if level is not None and level > 0:
            props["numLevel"] = level

    if block.get("type") == "reference":
        reference_format = reference_profile(template_profile)
        if reference_format.get("style_id"):
            props["style"] = reference_format["style_id"]
        if reference_format.get("num_id") is not None:
            props["numId"] = reference_format["num_id"]
            if reference_format.get("ilvl") is not None:
                props["numLevel"] = reference_format["ilvl"]
        elif reference_format.get("list_style"):
            props["listStyle"] = reference_format["list_style"]
        for source_key, target_key in [
            ("align", "align"),
            ("space_before", "spaceBefore"),
            ("space_after", "spaceAfter"),
            ("line_spacing", "lineSpacing"),
            ("line_rule", "lineRule"),
            ("hanging_indent", "hangingIndent"),
            ("size", "size"),
            ("font_ascii", "font"),
        ]:
            value = reference_format.get(source_key)
            if value not in (None, ""):
                props[target_key] = value
 
    return props


def add_bookmarks(document: Path, paragraph_path: str, bookmarks: list[dict]) -> None:
    for bookmark in bookmarks:
        name = bookmark.get("name")
        if not name:
            continue
        officecli_add(document, paragraph_path, element_type="bookmark", props={"name": name})


def add_paragraph(document: Path, anchor_path: str | None, block: dict, style_map: dict, bookmarks: list[dict] | None = None, template_profile: dict | None = None) -> str:
    runs = block_runs(block)
    props = paragraph_props(block, style_map, template_profile)

    if len(runs) == 1:
        props.update(run_props(runs[0], block=block, template_profile=template_profile))

    payload = officecli_add(
        document,
        "/body",
        element_type="paragraph",
        props=props,
        after=anchor_path,
        index=0 if anchor_path is None else None,
    )
    paragraph_path = extract_added_path(payload)
    if paragraph_path is None:
        raise ValueError("OfficeCLI add paragraph không trả về path mới.")

    add_bookmarks(document, paragraph_path, bookmarks or [])

    if len(runs) > 1:
        for run in runs:
            text_value = str(run.get("text") or "")
            if not text_value:
                continue
            officecli_add(document, paragraph_path, element_type="run", props=run_props(run, block=block, template_profile=template_profile))

    return paragraph_path


def rewrite_toc_fields(document: Path) -> list[str]:
    rewritten_paths: list[str] = []

    for toc in officecli_query(document, "toc"):
        path = toc.get("path")
        if not path:
            continue
        toc_format = toc.get("format", {})
        props = {}
        if toc_format.get("levels"):
            props["levels"] = toc_format["levels"]
        props["hyperlinks"] = bool(toc_format.get("hyperlinks", True))
        props["pageNumbers"] = True
        if not props:
            continue
        officecli_set(document, str(path), props=props)
        rewritten_paths.append(str(path))

    return rewritten_paths


def refresh_fields_if_supported(document: Path, rewritten_tocs: list[str]) -> tuple[str, bool]:
    if not rewritten_tocs:
        return ("none", False)

    if os.name != "nt":
        return ("rewrite-toc-fields-on-open", False)

    try:
        officecli_refresh(document)
    except OfficeCliError:
        return ("rewrite-toc-fields-on-open", False)

    return ("officecli-refresh", True)


def body_element_count(document: Path) -> int:
    text_view = officecli_view(document, "text") or {}
    return len([element for element in text_view.get("elements", []) if str(element.get("path", "")).startswith("/body/")])


def replace_body_range(template_file: Path, target_file: Path, blocks: list[dict], style_map: dict, replace_range: dict, template_profile: dict) -> dict:
    shutil.copy2(template_file, target_file)

    before_count = body_element_count(target_file)
    remove_paths = list(replace_range.get("remove_paths", []))
    current_anchor = replace_range.get("insert_after_path")
    heading_bookmarks = heading_bookmark_map(template_profile, replace_range)
    inserted_paragraph_count = 0
    inserted_paths: list[str] = []

    officecli_open(target_file)
    try:
        for path in reversed(remove_paths):
            officecli_remove(target_file, str(path))

        for block in blocks:
            text = block_text(block)
            if not text and block.get("type") != "thematic_break":
                continue

            bookmarks = None
            if block.get("type") == "heading":
                bookmarks = heading_bookmarks.get(normalize_heading_text(text), [])

            current_anchor = add_paragraph(target_file, current_anchor, block, style_map, bookmarks=bookmarks, template_profile=template_profile)
            inserted_paths.append(current_anchor)
            inserted_paragraph_count += 1

        rewritten_tocs = rewrite_toc_fields(target_file)
        officecli_save(target_file)
    finally:
        officecli_close(target_file)

    after_count = body_element_count(target_file)
    refresh_strategy, refreshed = refresh_fields_if_supported(target_file, rewritten_tocs)
    return {
        "body_children_before": before_count,
        "body_children_after": after_count,
        "replaced_child_count": len(remove_paths),
        "inserted_block_count": inserted_paragraph_count,
        "inserted_paths": inserted_paths,
        "body_replaced": inserted_paragraph_count > 0,
        "dirty_field_count": 0,
        "update_fields_on_open": refreshed,
        "field_refresh_strategy": refresh_strategy,
        "toc_rewrites": rewritten_tocs,
        "resident_mode": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh build_report.json cho pipeline DOCX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    plan = read_json(run_dir / "plan.json")
    run_state = read_json(run_dir / "run.json")
    template_profile = read_json(run_dir / "template_profile.json")
    content_ast = read_json(run_dir / "content_ast.json")

    replace_ranges = plan.get("replace_ranges", [])
    resolved_range = next((item for item in replace_ranges if item.get("status") == "resolved"), None)
    target_file = Path(plan.get("target_file"))
    template_file = Path(plan.get("template_file"))
    officecli_version = ensure_officecli_available()

    if plan.get("mode") != "preserve-template-scaffold":
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Script build hiện chỉ cho phép mode preserve-template-scaffold trong workflow an toàn mới.",
            "body_replaced": False,
            "officecli_version": officecli_version,
        }
        run_state["status"] = "blocked"
    elif resolved_range is None:
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Không resolve được replace_ranges nên build bị chặn để tránh làm mất scaffold của template.",
            "body_replaced": False,
            "officecli_version": officecli_version,
        }
        run_state["status"] = "blocked"
    else:
        replacement_stats = replace_body_range(
            template_file=template_file,
            target_file=target_file,
            blocks=content_ast.get("blocks", []),
            style_map=plan.get("style_map", {}),
            replace_range=resolved_range,
            template_profile=template_profile,
        )
        build_report = {
            "status": "completed",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "officecli_version": officecli_version,
            "replace_range": resolved_range,
            "preserve": plan.get("preserve", []),
            "style_map": plan.get("style_map", {}),
            "template_header_count": template_profile.get("header_count", 0),
            "template_footer_count": template_profile.get("footer_count", 0),
            **replacement_stats,
            "message": "Đã thay vùng nội dung chính theo bounded range bằng OfficeCLI resident mode và giữ scaffold của template ở ngoài phạm vi thay.",
        }
        run_state["status"] = "built"

    run_state["artifacts"]["build_report"] = str(run_dir / "build_report.json")

    write_json(run_dir / "build_report.json", build_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
