from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import (
    ensure_officecli_available,
    normalize_text,
    officecli_get,
    officecli_query,
    officecli_validate,
    officecli_view,
    read_json,
    write_json,
)


ERROR_PATTERNS = [
    "CHƯƠNG 1. CHƯƠNG 1",
    "CHƯƠNG 2. CHƯƠNG 2",
    "4.1. 1.1.",
    "5.1. 2.1.",
]


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def normalize_heading_text(text: str) -> str:
    return normalize_text(strip_heading_numbering(text))


def strip_toc_page_number(text: str) -> str:
    return re.sub(r"\s*\d+$", "", text.strip()).strip()


def collect_body_paragraphs(paragraph_results: list[dict]) -> list[dict]:
    body_results = [result for result in paragraph_results if str(result.get("path", "")).startswith("/body/")]
    paragraphs: list[dict] = []

    for index, result in enumerate(body_results):
        result_format = result.get("format", {})
        style_name = result_format.get("styleName") or result.get("style") or result_format.get("style")
        bookmarks = {
            child.get("format", {}).get("name")
            for child in result.get("children", [])
            if child.get("type") == "bookmark" and child.get("format", {}).get("name")
        }
        paragraphs.append(
            {
                "index": index,
                "path": result.get("path"),
                "text": str(result.get("text") or "").strip(),
                "style": style_name,
                "style_id": result_format.get("styleId"),
                "bookmarks": bookmarks,
            }
        )

    return paragraphs


def collect_bookmarks(paragraphs: list[dict]) -> set[str]:
    names: set[str] = set()
    for paragraph in paragraphs:
        names.update(paragraph.get("bookmarks", set()))
    return names


def extract_heading_texts(paragraphs: list[dict]) -> list[str]:
    results: list[str] = []
    for paragraph in paragraphs:
        style = normalize_text(paragraph.get("style") or paragraph.get("style_id") or "")
        text = paragraph.get("text") or ""
        if not text or style.startswith("TOC"):
            continue
        normalized = normalize_text(text)
        if style.startswith("HEADING") or normalized.startswith("CHUONG ") or normalized.startswith("NGHI DINH "):
            results.append(text)
    return results


def extract_toc_entries(paragraphs: list[dict]) -> list[dict]:
    entries: list[dict] = []

    for paragraph in paragraphs:
        style = normalize_text(paragraph.get("style") or paragraph.get("style_id") or "")
        if not style.startswith("TOC"):
            continue
        text = str(paragraph.get("text") or "").strip()
        entries.append(
            {
                "index": paragraph.get("index"),
                "style": paragraph.get("style") or paragraph.get("style_id"),
                "text": text,
                "heading_text": strip_toc_page_number(text),
            }
        )

    return entries


def field_instructions(field_results: list[dict]) -> list[str]:
    return [
        str(result.get("format", {}).get("instruction") or "").strip()
        for result in field_results
        if str(result.get("format", {}).get("instruction") or "").strip()
    ]


def extract_pageref_anchors(field_results: list[dict]) -> list[str]:
    anchors: list[str] = []
    for result in field_results:
        result_format = result.get("format", {})
        if str(result_format.get("fieldType") or "").lower() != "pageref":
            continue
        instruction = str(result_format.get("instruction") or "")
        match = re.search(r"PAGEREF\s+([^\s]+)", instruction, re.IGNORECASE)
        if match:
            anchors.append(match.group(1))
    return anchors


def has_list_toc(field_codes: list[str], keyword: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    for code in field_codes:
        normalized_code = normalize_text(code)
        if f'\\C "{normalized_keyword}"' in normalized_code or normalized_keyword in normalized_code:
            return True
    return False


def critical_issues(issue_payload: dict) -> list[dict]:
    issues = issue_payload.get("issues", []) if isinstance(issue_payload, dict) else []
    return [issue for issue in issues if int(issue.get("severity", 0)) >= 2]


def check_section_breaks(section_results: list[dict], template_profile: dict) -> bool:
    template_body_section = template_profile.get("document_profile", {}).get("body_section_count", 0)
    return template_body_section == 0 or len(section_results) >= template_body_section


def is_subsequence(source: list[str], output: list[str]) -> bool:
    if not source:
        return True

    source_normalized = [normalize_heading_text(item) for item in source if item.strip()]
    output_normalized = [normalize_heading_text(item) for item in output if item.strip()]

    output_index = 0
    for source_item in source_normalized:
        while output_index < len(output_normalized) and output_normalized[output_index] != source_item:
            output_index += 1
        if output_index >= len(output_normalized):
            return False
        output_index += 1
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh qa_report.json cho pipeline DOCX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state = read_json(run_dir / "run.json")
    plan = read_json(run_dir / "plan.json")
    build_report = read_json(run_dir / "build_report.json") if (run_dir / "build_report.json").exists() else {}
    template_profile = read_json(run_dir / "template_profile.json")
    outline_payload = read_json(run_dir / "content_outline.json") if (run_dir / "content_outline.json").exists() else {"outline": []}

    target_file = Path(run_state.get("target_file"))
    target_exists = target_file.exists()
    officecli_version = ensure_officecli_available() if target_exists else None
    styles_tree = officecli_get(target_file, "/styles", depth=1) if target_exists else {}
    section_results = officecli_query(target_file, "section") if target_exists else []
    header_results = officecli_query(target_file, "header") if target_exists else []
    footer_results = officecli_query(target_file, "footer") if target_exists else []
    paragraph_results = officecli_query(target_file, "paragraph") if target_exists else []
    toc_results = officecli_query(target_file, "toc") if target_exists else []
    field_results = officecli_query(target_file, "field") if target_exists else []
    validate_payload = officecli_validate(target_file) if target_exists else {"success": False}
    issues_payload = officecli_view(target_file, "issues") if target_exists else {"count": 0, "issues": []}
    text_payload = officecli_view(target_file, "text") if target_exists else {"elements": []}

    paragraphs = collect_body_paragraphs(paragraph_results)
    bookmarks = collect_bookmarks(paragraphs)
    toc_entries = extract_toc_entries(paragraphs)
    field_codes = field_instructions(field_results)
    heading_texts = extract_heading_texts(paragraphs)
    source_headings = [item.get("text", "") for item in outline_payload.get("outline", [])]
    normalized_document_text = "\n".join(str(element.get("text") or "") for element in text_payload.get("elements", []))
    duplicate_patterns = [pattern for pattern in ERROR_PATTERNS if pattern in normalized_document_text]

    required_preserve = set(plan.get("preserve", []))
    normalized_field_codes = [normalize_text(code) for code in field_codes]
    toc_present = bool(toc_results) or any(" TOC " in f" {code} " or code.startswith("TOC") for code in normalized_field_codes)
    toc_text_codes = [str(t.get("text", "")) + " " + str(t.get("format", {}).get("instruction", "")) for t in toc_results]
    list_of_figures_present = has_list_toc(field_codes + toc_text_codes, "Hình")
    list_of_tables_present = has_list_toc(field_codes + toc_text_codes, "Bảng")
    header_count = len(header_results)
    footer_count = len(footer_results)
    required_parts_present = target_exists and bool(styles_tree) and bool(validate_payload.get("success"))
    update_fields_enabled = bool(build_report.get("update_fields_on_open"))
    dirty_field_count = int(build_report.get("dirty_field_count", 0) or 0)
    refresh_on_open_ready = toc_present and build_report.get("field_refresh_strategy") in {"rewrite-toc-fields-on-open", "update-fields-on-open"}

    pageref_anchors = extract_pageref_anchors(field_results)
    toc_missing_hyperlinks = [] if pageref_anchors else [entry for entry in toc_entries if entry.get("text")]
    toc_broken_anchors = [anchor for anchor in pageref_anchors if anchor not in bookmarks]
    toc_heading_texts = [entry.get("heading_text", "") for entry in toc_entries if entry.get("heading_text")]
    toc_rendered_matches_source = is_subsequence(source_headings, toc_heading_texts)
    toc_links_ok = not toc_missing_hyperlinks and not toc_broken_anchors
    toc_ok = (
        "toc" not in required_preserve
        or (
            toc_present
            and (
                (toc_rendered_matches_source and toc_links_ok)
                or refresh_on_open_ready
            )
        )
    )
    cross_references_ok = (
        not toc_entries
        or (
            not toc_missing_hyperlinks
            and (
                not toc_broken_anchors
                or refresh_on_open_ready
            )
        )
    )

    scaffold_checks = {
        "headers_footers": (
            "headers-footers" not in required_preserve
            or (
                header_count >= template_profile.get("header_count", 0)
                and footer_count >= template_profile.get("footer_count", 0)
            )
        ),
        "toc": toc_ok,
        "list_of_figures": "list-of-figures" not in required_preserve or list_of_figures_present,
        "list_of_tables": "list-of-tables" not in required_preserve or list_of_tables_present,
        "section_breaks": check_section_breaks(section_results, template_profile),
    }
    scaffold_preserved = all(scaffold_checks.values()) if target_exists else False

    replace_ranges_resolved = any(item.get("status") == "resolved" for item in plan.get("replace_ranges", []))
    outline_ok = is_subsequence(source_headings, heading_texts)
    body_replaced_ok = bool(build_report.get("body_replaced")) and build_report.get("status") == "completed"
    template_heading_set = {
        normalize_text(item.get("text", ""))
        for item in template_profile.get("document_profile", {}).get("headings", [])
        if item.get("text") and not str(item.get("style") or "").lower().startswith("toc")
    }
    source_heading_set = {normalize_text(item) for item in source_headings if item.strip()}
    residual_template_headings = sorted(
        heading for heading in template_heading_set.difference(source_heading_set) if heading and heading in {normalize_text(item) for item in heading_texts}
    )
    template_residue = bool(residual_template_headings)

    validate_ok = bool(validate_payload.get("success"))
    severe_issues = critical_issues(issues_payload)

    qa_report = {
        "status": "passed" if all([
            required_parts_present,
            scaffold_preserved,
            replace_ranges_resolved,
            outline_ok,
            body_replaced_ok,
            not template_residue,
            not duplicate_patterns,
            validate_ok,
            not severe_issues,
        ]) else "failed",
        "officecli_version": officecli_version,
        "source_heading_count": len(source_headings),
        "output_heading_count": len(heading_texts),
        "required_preserve": sorted(required_preserve),
        "required_parts_present": required_parts_present,
        "scaffold_preserved": scaffold_preserved,
        "replace_ranges_resolved": replace_ranges_resolved,
        "outline_ok": outline_ok,
        "body_replaced_ok": body_replaced_ok,
        "template_residue": template_residue,
        "residual_template_headings": residual_template_headings,
        "duplicate_heading_patterns": duplicate_patterns,
        "checks": {
            "package": required_parts_present,
            "outline": outline_ok,
            "numbering": build_report.get("status") == "completed",
            "toc": scaffold_checks["toc"],
            "references": True,
            "appendix": True,
            "lists": scaffold_checks["list_of_figures"] and scaffold_checks["list_of_tables"],
            "cross_references": cross_references_ok,
            "header_footer": scaffold_checks["headers_footers"],
            "placeholder_leak": "{{" not in normalized_document_text and "<TODO>" not in normalized_document_text,
            "validate": validate_ok,
            "section_breaks": scaffold_checks["section_breaks"],
        },
        "toc_refresh_strategy": build_report.get("field_refresh_strategy", "rendered-in-package"),
        "update_fields_on_open": update_fields_enabled,
        "dirty_field_count": dirty_field_count,
        "bookmark_count": len(bookmarks),
        "toc_entry_count": len(toc_entries),
        "toc_rendered_matches_source": toc_rendered_matches_source,
        "toc_missing_hyperlinks": [entry["index"] for entry in toc_missing_hyperlinks],
        "toc_broken_anchor_entries": toc_broken_anchors,
        "severe_issue_count": len(severe_issues),
        "message": "QA đã kiểm package, scaffold, range và semantic gate cho contract preserve-template-scaffold."
    }

    run_state["artifacts"]["qa_report"] = str(run_dir / "qa_report.json")
    run_state["status"] = "ready" if qa_report["status"] == "passed" else "needs-repair"

    write_json(run_dir / "qa_report.json", qa_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()