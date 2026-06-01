from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import ensure_officecli_available, normalize_text, officecli_query, officecli_view, read_json, write_json


def safe_query(document: Path, selector: str) -> list[dict]:
    try:
        return officecli_query(document, selector)
    except Exception:
        return []


def paragraph_style_discipline(paragraphs: list[dict]) -> dict:
    body_paragraphs = [item for item in paragraphs if str(item.get("path") or "").startswith("/body/")]
    nonempty = [item for item in body_paragraphs if str(item.get("text") or "").strip()]
    if not nonempty:
        return {"ratio": 0.0, "named_count": 0, "total_count": 0}

    named_count = 0
    for paragraph in nonempty:
        paragraph_format = paragraph.get("format") or {}
        style_name = str(paragraph_format.get("styleName") or paragraph.get("style") or "")
        style_id = str(paragraph_format.get("styleId") or paragraph_format.get("style") or "")
        normalized = normalize_text(f"{style_name} {style_id}")
        if normalized and not any(token in normalized for token in ["NORMAL", "DEFAULT PARAGRAPH STYLE"]):
            named_count += 1

    ratio = round(named_count / len(nonempty), 4)
    return {"ratio": ratio, "named_count": named_count, "total_count": len(nonempty)}


def infer_recommended_path(signals: dict) -> tuple[str, str]:
    if signals["has_toc_field"] or signals["has_pageref"] or signals["has_bookmarks"] or signals["has_multiple_sections"]:
        return "structural_preserve", "Document contains cross-reference/section topology that should preserve structure and perform bounded replacement."

    if signals["has_tables"] or signals["has_textboxes"] or signals["has_footnotes"] or signals["has_comments"]:
        return "hybrid", "Document contains mixed structures (table/textbox/notes/comments); use hybrid preservation strategy."

    if signals["style_discipline_ratio"] >= 0.85:
        return "semantic_style", "Document is style-disciplined and can use semantic style path."

    return "hybrid", "Default to hybrid path because style discipline is weak and topology is uncertain."


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect DOCX topology and recommend pipeline path.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    template_file = Path(args.template_file)
    run_dir = Path(args.run_dir)

    officecli_version = ensure_officecli_available()
    field_results = safe_query(template_file, "field")
    paragraph_results = safe_query(template_file, "paragraph")
    bookmark_results = safe_query(template_file, "bookmark")
    table_results = safe_query(template_file, "table")
    section_results = safe_query(template_file, "section")
    comment_results = safe_query(template_file, "comment")
    footnote_results = safe_query(template_file, "footnote")
    text_view = officecli_view(template_file, "text") or {"elements": []}

    field_instructions = [
        normalize_text(str((item.get("format") or {}).get("instruction") or ""))
        for item in field_results
        if str((item.get("format") or {}).get("instruction") or "").strip()
    ]

    style_discipline = paragraph_style_discipline(paragraph_results)
    has_txbx = any("TXBXCONTENT" in normalize_text(str(element.get("path") or "")) for element in text_view.get("elements", []))
    section_count = len(section_results)

    signals = {
        "has_toc_field": any(" TOC " in f" {code} " or code.startswith("TOC") for code in field_instructions),
        "has_pageref": any("PAGEREF" in code for code in field_instructions),
        "has_bookmarks": bool(bookmark_results),
        "has_tables": bool(table_results),
        "has_footnotes": bool(footnote_results),
        "has_textboxes": has_txbx,
        "has_comments": bool(comment_results),
        "has_multiple_sections": section_count > 1,
        "section_count": section_count,
        "style_discipline_ratio": style_discipline["ratio"],
        "style_discipline_named": style_discipline["named_count"],
        "style_discipline_total": style_discipline["total_count"],
    }

    recommended_path, reason = infer_recommended_path(signals)
    topology_payload = {
        "template_file": str(template_file),
        "officecli_version": officecli_version,
        **signals,
        "recommended_path": recommended_path,
        "recommended_path_reason": reason,
    }

    topology_file = run_dir / "topology.json"
    write_json(topology_file, topology_payload)

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["topology"] = str(topology_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
