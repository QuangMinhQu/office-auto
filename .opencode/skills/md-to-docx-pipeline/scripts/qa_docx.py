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


def filter_outline(outline: list[dict], source_render_window: dict | None = None) -> list[dict]:
    """Inline replacement for legacy semantic_grounding.filter_outline.
    
    For new pipeline: just return outline as-is (no semantic filtering needed).
    source_render_window is ignored.
    """
    return outline


BACK_MATTER_MARKERS = {
    "references": {"TAI LIEU THAM KHAO", "REFERENCES", "BIBLIOGRAPHY"},
    "appendix": {"PHU LUC", "APPENDIX"},
}
LEGAL_CHAPTER_PATTERN = re.compile(r"^(?:CHƯƠNG|CHUONG)\s+[IVXLCDM\d]+", re.IGNORECASE)
LEGAL_ARTICLE_PATTERN = re.compile(r"^ĐIỀU\s+\d+", re.IGNORECASE)
LEGAL_CLAUSE_PATTERN = re.compile(r"^(?:KHOẢN\s+\d+|\d+\.)", re.IGNORECASE)
PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}]+\}\}|<TODO>|\b(?:lorem ipsum|xxxx)\b", re.IGNORECASE)
LEGACY_DUPLICATE_PATTERNS = [
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


def heading_zone(text: str) -> str | None:
    normalized = normalize_text(text)
    for zone_name, markers in BACK_MATTER_MARKERS.items():
        if normalized in markers:
            return zone_name
    return None


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
                "format_profile": {
                    "align": result_format.get("effective.align") or result_format.get("align"),
                    "size": result_format.get("effective.size") or result_format.get("size"),
                    "font": result_format.get("effective.font.ascii") or result_format.get("font.ascii") or result_format.get("font.latin"),
                    "first_line_indent": result_format.get("effective.firstLineIndent") or result_format.get("firstLineIndent"),
                },
                "bookmarks": bookmarks,
            }
        )

    return paragraphs


def collect_bookmarks(paragraphs: list[dict]) -> set[str]:
    names: set[str] = set()
    for paragraph in paragraphs:
        names.update(paragraph.get("bookmarks", set()))
    return names


def extract_heading_texts(paragraphs: list[dict], prototype_roles: dict) -> list[str]:
    heading_styles = {
        normalize_text(str(prototype_roles.get(role, {}).get("style_id") or ""))
        for role in ["h1", "h2", "h3"]
    }
    results: list[str] = []
    for paragraph in paragraphs:
        style = normalize_text(paragraph.get("style") or paragraph.get("style_id") or "")
        text = paragraph.get("text") or ""
        if not text or style.startswith("TOC"):
            continue
        normalized = normalize_text(text)
        if style in heading_styles or style.startswith("HEADING") or normalized.startswith("CHUONG ") or heading_zone(text) is not None or re.match(r"^\d+(?:\.\d+)*\.?\s+", text):
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


def template_baseline(run_dir: Path) -> dict:
    if (run_dir / "template_profile.json").exists():
        return read_json(run_dir / "template_profile.json")

    if not (run_dir / "template_inspection_raw.json").exists():
        return {}

    inspection = read_json(run_dir / "template_inspection_raw.json")
    outline_snapshot = inspection.get("outline_snapshot") or {}
    headings = []
    for item in outline_snapshot.get("headings", []):
        text = item.get("text") if isinstance(item, dict) else None
        if text:
            headings.append({"text": text, "style": item.get("style") if isinstance(item, dict) else None})

    return {
        "header_count": inspection.get("counts", {}).get("headers", 0),
        "footer_count": inspection.get("counts", {}).get("footers", 0),
        "prototype_catalog": {},
        "document_profile": {
            "body_section_count": inspection.get("counts", {}).get("sections", 0),
            "headings": headings,
        },
    }


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


def detect_duplicate_heading_patterns(document_text: str, heading_texts: list[str]) -> list[str]:
    findings: set[str] = set()
    normalized_document = normalize_text(document_text)
    for pattern in LEGACY_DUPLICATE_PATTERNS:
        if normalize_text(pattern) in normalized_document:
            findings.add(pattern)

    for heading in heading_texts:
        normalized_heading = normalize_text(heading)
        chapter_dup = re.search(r"^(CHUONG|PHAN)\s+([^\s]+)\s+\1\s+\2\b", normalized_heading)
        if chapter_dup:
            findings.add(heading)
        duplicate_numbering = re.search(r"^(\d+(?:\.\d+)+\.?)(?:\s+)(\d+(?:\.\d+)+\.?)", normalized_heading)
        if duplicate_numbering:
            first = duplicate_numbering.group(1).rstrip(".")
            second = duplicate_numbering.group(2).rstrip(".")
            if first == second or second.startswith(first):
                findings.add(heading)
    return sorted(findings)


def source_zone_markers(outline_payload: dict) -> set[str]:
    markers: set[str] = set()
    for item in outline_payload.get("outline", []):
        marker = heading_zone(str(item.get("text") or ""))
        if marker:
            markers.add(marker)
    return markers


def output_zone_markers(heading_texts: list[str]) -> set[str]:
    markers: set[str] = set()
    for text in heading_texts:
        marker = heading_zone(text)
        if marker:
            markers.add(marker)
    return markers


def placeholder_leak(document_text: str) -> bool:
    return bool(PLACEHOLDER_PATTERN.search(document_text))


def required_heading_numbering(plan: dict) -> bool:
    prototype_roles = plan.get("prototype_roles", {})
    for role in ["h1", "h2", "h3"]:
        prototype = prototype_roles.get(role, {})
        if prototype.get("num_id") not in (None, ""):
            return True
    return False


def legal_role_from_text(text: str) -> str | None:
    if LEGAL_CHAPTER_PATTERN.match(text):
        return "legal_chuong"
    if LEGAL_ARTICLE_PATTERN.match(text):
        return "legal_dieu"
    if LEGAL_CLAUSE_PATTERN.match(text):
        return "legal_khoan"
    return None


def expected_role(paragraph: dict, style_map: dict) -> str | None:
    style_tokens = {
        normalize_text(paragraph.get("style") or ""),
        normalize_text(paragraph.get("style_id") or ""),
    }
    for role, style_id in style_map.items():
        if normalize_text(str(style_id or "")) in style_tokens:
            return role

    text = str(paragraph.get("text") or "")
    return legal_role_from_text(text)


def prototype_expected_format(role: str, prototype_catalog: dict) -> dict:
    prototype = prototype_catalog.get(role) or {}
    if not prototype and role in {"legal_dieu", "legal_khoan", "reference", "list", "blockquote", "code"}:
        prototype = prototype_catalog.get("body") or {}
    if not prototype and role == "legal_chuong":
        prototype = prototype_catalog.get("h1") or prototype_catalog.get("body") or {}

    paragraph_format = prototype.get("paragraph_format") or {}
    first_run = next((run for run in prototype.get("runs", []) if str(run.get("text") or "").strip()), {})
    return {
        "align": paragraph_format.get("align"),
        "size": first_run.get("size") or paragraph_format.get("size"),
        "font": first_run.get("font_ascii") or first_run.get("font_latin") or paragraph_format.get("font_ascii") or paragraph_format.get("font_latin"),
        "first_line_indent": paragraph_format.get("first_line_indent"),
    }


def check_format_fidelity(paragraphs: list[dict], style_map: dict, prototype_catalog: dict) -> tuple[list[dict], dict]:
    violations: list[dict] = []
    counters = {
        "alignment_drift": 0,
        "font_size_drift": 0,
        "font_family_drift": 0,
        "first_line_indent_drift": 0,
    }

    for paragraph in paragraphs:
        text = str(paragraph.get("text") or "")
        if not text:
            continue
        role = expected_role(paragraph, style_map)
        if not role:
            continue

        expected = prototype_expected_format(role, prototype_catalog)
        actual = paragraph.get("format_profile") or {}
        row_issues: list[str] = []

        expected_align = str(expected.get("align") or "").lower()
        actual_align = str(actual.get("align") or "").lower()
        if expected_align and actual_align and expected_align != actual_align:
            counters["alignment_drift"] += 1
            row_issues.append("alignment_drift")

        expected_size = str(expected.get("size") or "")
        actual_size = str(actual.get("size") or "")
        if expected_size and actual_size and expected_size != actual_size:
            counters["font_size_drift"] += 1
            row_issues.append("font_size_drift")

        expected_font = normalize_text(str(expected.get("font") or ""))
        actual_font = normalize_text(str(actual.get("font") or ""))
        if expected_font and actual_font and expected_font != actual_font:
            counters["font_family_drift"] += 1
            row_issues.append("font_family_drift")

        expected_indent = str(expected.get("first_line_indent") or "")
        actual_indent = str(actual.get("first_line_indent") or "")
        if expected_indent and actual_indent and expected_indent != actual_indent:
            counters["first_line_indent_drift"] += 1
            row_issues.append("first_line_indent_drift")

        if row_issues:
            violations.append(
                {
                    "index": paragraph.get("index"),
                    "path": paragraph.get("path"),
                    "role": role,
                    "style": paragraph.get("style") or paragraph.get("style_id"),
                    "issues": row_issues,
                    "expected": expected,
                    "actual": actual,
                }
            )

    hard_fail = counters["alignment_drift"] + counters["font_size_drift"] + counters["font_family_drift"] > 0
    return violations, {
        "checked_paragraphs": len([paragraph for paragraph in paragraphs if str(paragraph.get("text") or "")]),
        "violation_count": len(violations),
        **counters,
        "hard_fail": hard_fail,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh qa_report.json cho pipeline DOCX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state = read_json(run_dir / "run.json")
    
    # New pipeline: read execution_ops.json (versioned schema)
    execution_ops = read_json(run_dir / "execution_ops.json") if (run_dir / "execution_ops.json").exists() else {}
    if isinstance(execution_ops, dict):
        ops_list = execution_ops.get("ops", [])
        execution_version = execution_ops.get("version", "1")
    else:
        ops_list = execution_ops if isinstance(execution_ops, list) else []
        execution_version = "1"
    
    # New pipeline: read execute_ops_report.json
    build_report = read_json(run_dir / "execute_ops_report.json") if (run_dir / "execute_ops_report.json").exists() else {}
    
    # Legacy fallback: plan.json (may not exist in new pipeline)
    plan = read_json(run_dir / "plan.json") if (run_dir / "plan.json").exists() else {}
    execution_plan = read_json(run_dir / "execution_plan.json") if (run_dir / "execution_plan.json").exists() else {}
    roundtrip_report = read_json(run_dir / "roundtrip_report.json") if (run_dir / "roundtrip_report.json").exists() else {}
    template_profile = template_baseline(run_dir)
    outline_payload = read_json(run_dir / "content_outline.json") if (run_dir / "content_outline.json").exists() else {"outline": []}
    source_render_window = (plan.get("semantic_grounding") or {}).get("source_render_window") or {}

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
    numbered_results = officecli_query(target_file, "paragraph[numId>0]") if target_exists else []
    validate_payload = officecli_validate(target_file) if target_exists else {"success": False}
    issues_payload = officecli_view(target_file, "issues") if target_exists else {"count": 0, "issues": []}
    text_payload = officecli_view(target_file, "text") if target_exists else {"elements": []}

    paragraphs = collect_body_paragraphs(paragraph_results)
    bookmarks = collect_bookmarks(paragraphs)
    toc_entries = extract_toc_entries(paragraphs)
    field_codes = field_instructions(field_results)
    prototype_roles = plan.get("prototype_roles", {})
    heading_texts = extract_heading_texts(paragraphs, prototype_roles)
    format_violations, format_fidelity = check_format_fidelity(
        paragraphs,
        plan.get("style_map", {}),
        template_profile.get("prototype_catalog", {}),
    )
    grounded_outline = filter_outline(outline_payload.get("outline", []), source_render_window)
    source_headings = [item.get("text", "") for item in grounded_outline]
    normalized_document_text = "\n".join(str(element.get("text") or "") for element in text_payload.get("elements", []))
    duplicate_patterns = detect_duplicate_heading_patterns(normalized_document_text, heading_texts)

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
    refresh_on_open_ready = toc_present and build_report.get("field_refresh_strategy") in {"rewrite-toc-fields-on-open", "update-fields-on-open", "officecli-refresh"}

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
                or (refresh_on_open_ready and bool(field_results or toc_results))
            )
        )
    )
    cross_references_ok = not pageref_anchors or not toc_broken_anchors

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

    selected_range = plan.get("selected_replace_range") or {}
    replace_ranges_resolved = selected_range.get("status") == "resolved"
    remove_strategy_ok = build_report.get("remove_scope") == "direct-body-children"
    outline_ok = is_subsequence(source_headings, heading_texts)
    insert_only_range = not bool(selected_range.get("remove_paths"))
    
    # New pipeline: check execution success from execute_ops_report
    exec_status_ok = build_report.get("status") == "completed" or build_report.get("succeeded", 0) > 0
    body_replaced_ok = (
        exec_status_ok
        and (
            int(build_report.get("inserted_paragraphs", 0) or 0) > 0
            or int(build_report.get("inserted_tables", 0) or 0) > 0
        )
    )
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
    numbering_needed = required_heading_numbering(plan)
    numbering_ok = (not numbering_needed) or bool(numbered_results)
    source_markers = source_zone_markers({"outline": grounded_outline})
    output_markers = output_zone_markers(heading_texts)
    references_ok = "references" not in source_markers or "references" in output_markers
    appendix_ok = "appendix" not in source_markers or "appendix" in output_markers
    placeholder_ok = not placeholder_leak(normalized_document_text)
    
    # New pipeline: execution_plan_ready from execute_ops_report
    execution_plan_ready = build_report.get("status") == "completed" or build_report.get("succeeded", 0) > 0
    semantic_roundtrip_ok = roundtrip_report.get("status") == "passed"
    format_fidelity_ok = not format_fidelity.get("hard_fail", False)

    qa_report = {
        "status": "passed" if all([
            required_parts_present,
            scaffold_preserved,
            outline_ok,
            body_replaced_ok,
            numbering_ok,
            references_ok,
            appendix_ok,
            not template_residue,
            not duplicate_patterns,
            placeholder_ok,
            format_fidelity_ok,
            validate_ok,
            not severe_issues,
        ]) else "failed",
        "officecli_version": officecli_version,
        "source_heading_count": len(source_headings),
        "output_heading_count": len(heading_texts),
        "required_preserve": sorted(required_preserve),
        "required_parts_present": required_parts_present,
        "scaffold_preserved": scaffold_preserved,
        "outline_ok": outline_ok,
        "body_replaced_ok": body_replaced_ok,
        "template_residue": template_residue,
        "residual_template_headings": residual_template_headings,
        "duplicate_heading_patterns": duplicate_patterns,
        "checks": {
            "package": required_parts_present,
            "outline": outline_ok,
            "numbering": numbering_ok,
            "toc": scaffold_checks["toc"],
            "semantic_roundtrip": semantic_roundtrip_ok,
            "references": references_ok,
            "appendix": appendix_ok,
            "lists": scaffold_checks["list_of_figures"] and scaffold_checks["list_of_tables"],
            "cross_references": cross_references_ok,
            "header_footer": scaffold_checks["headers_footers"],
            "placeholder_leak": placeholder_ok,
            "format_fidelity": format_fidelity_ok,
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
        "semantic_roundtrip_ok": semantic_roundtrip_ok,
        "format_fidelity_ok": format_fidelity_ok,
        "format_fidelity_summary": format_fidelity,
        "format_fidelity_violations": format_violations[:50],
        "roundtrip_missing_headings": roundtrip_report.get("missing_headings", []),
        "roundtrip_extra_headings": roundtrip_report.get("extra_headings", []),
        "roundtrip_body_text_similarity": roundtrip_report.get("body_text_similarity_summary", {}),
        "source_zone_markers": sorted(source_markers),
        "output_zone_markers": sorted(output_markers),
        "severe_issue_count": len(severe_issues),
        "message": "QA đã kiểm package, scaffold, selected range, execution graph và semantic gate cho contract preserve-template-scaffold.",
    }

    run_state.setdefault("artifacts", {})["qa_report"] = str(run_dir / "qa_report.json")
    run_state["status"] = "ready" if qa_report["status"] == "passed" else "needs-repair"

    write_json(run_dir / "qa_report.json", qa_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()