from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import officecli_query, officecli_set, read_json, write_json


BODY_STYLE_ROLES = ["body", "list", "reference", "blockquote", "legal_dieu", "legal_khoan"]


def style_name(paragraph: dict) -> str:
    paragraph_format = paragraph.get("format") or {}
    return str(paragraph_format.get("styleName") or paragraph.get("style") or paragraph_format.get("styleId") or "")


def paragraph_text(paragraph: dict) -> str:
    return str(paragraph.get("text") or "").strip()


def prototype_body_font_size(plan: dict) -> str | None:
    prototype_roles = plan.get("prototype_roles") or {}
    body = prototype_roles.get("body") or {}
    return body.get("size")


def gather_body_styles(plan: dict) -> set[str]:
    style_map = plan.get("style_map") or {}
    styles = set()
    for role in BODY_STYLE_ROLES:
        style_id = style_map.get(role)
        if isinstance(style_id, str) and style_id.strip():
            styles.add(style_id.strip())
    return styles


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize known formatting drift after DOCX build.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    plan = read_json(run_dir / "plan.json") if (run_dir / "plan.json").exists() else {}
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    target_file = Path(run_state.get("target_file") or plan.get("target_file") or "")

    report = {
        "status": "blocked",
        "target_file": str(target_file),
        "alignment_fixes": 0,
        "font_size_fixes": 0,
        "message": "post_process_docx chưa chạy vì thiếu target file.",
    }

    if not target_file.exists():
        write_json(run_dir / "post_process_report.json", report)
        run_state.setdefault("artifacts", {})["post_process_report"] = str(run_dir / "post_process_report.json")
        write_json(run_dir / "run.json", run_state)
        return

    paragraphs = officecli_query(target_file, "paragraph")
    body_styles = gather_body_styles(plan)
    body_size = prototype_body_font_size(plan)

    alignment_fixes = 0
    font_size_fixes = 0

    for paragraph in paragraphs:
        path = str(paragraph.get("path") or "")
        if not path.startswith("/body/"):
            continue

        text = paragraph_text(paragraph)
        para_style = style_name(paragraph)
        para_format = paragraph.get("format") or {}
        align = str(para_format.get("effective.align") or para_format.get("align") or "").lower()

        if para_style in body_styles and align == "center" and text:
            officecli_set(target_file, path, props={"align": "justify"})
            alignment_fixes += 1

        if body_size and not text:
            size = str(para_format.get("effective.size") or para_format.get("size") or "")
            if size and size != body_size:
                officecli_set(target_file, path, props={"size": body_size})
                font_size_fixes += 1

    report = {
        "status": "completed",
        "target_file": str(target_file),
        "alignment_fixes": alignment_fixes,
        "font_size_fixes": font_size_fixes,
        "message": "Applied post-build normalization for known paragraph-level drift.",
    }

    report_file = run_dir / "post_process_report.json"
    write_json(report_file, report)
    run_state.setdefault("artifacts", {})["post_process_report"] = str(report_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
