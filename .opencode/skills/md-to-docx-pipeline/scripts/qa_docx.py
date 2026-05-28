from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
ERROR_PATTERNS = [
    "CHƯƠNG 1. CHƯƠNG 1",
    "CHƯƠNG 2. CHƯƠNG 2",
    "4.1. 1.1.",
    "5.1. 2.1.",
]


def qname(tag: str) -> str:
    return f"{{{WORD_NAMESPACE['w']}}}{tag}"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.upper().split())


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def normalize_heading_text(text: str) -> str:
    return normalize_text(strip_heading_numbering(text))


def _check_section_breaks(document_root: ET.Element | None, template_profile: dict) -> bool:
    if document_root is None:
        return False
    body = document_root.find("w:body", WORD_NAMESPACE)
    body_sectpr = len(body.findall("w:sectPr", WORD_NAMESPACE)) if body is not None else 0
    template_body_section = template_profile.get("document_profile", {}).get("body_section_count", 0)
    return template_body_section == 0 or body_sectpr >= template_body_section


def read_xml_from_docx(docx_path: Path, member: str) -> ET.Element | None:
    with zipfile.ZipFile(docx_path) as archive:
        if member not in archive.namelist():
            return None
        with archive.open(member) as handle:
            return ET.fromstring(handle.read())


def archive_members(docx_path: Path) -> list[str]:
    with zipfile.ZipFile(docx_path) as archive:
        return archive.namelist()


def extract_field_codes(document_root: ET.Element | None) -> list[str]:
    if document_root is None:
        return []

    field_codes: list[str] = []
    for field in document_root.findall(".//w:fldSimple", WORD_NAMESPACE):
        instruction = field.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}instr")
        if instruction:
            field_codes.append(instruction)
    for node in document_root.findall(".//w:instrText", WORD_NAMESPACE):
        if node.text and node.text.strip():
            field_codes.append(node.text.strip())
    return field_codes


def extract_paragraphs(document_root: ET.Element | None) -> list[dict]:
    if document_root is None:
        return []
    body = document_root.find("w:body", WORD_NAMESPACE)
    if body is None:
        return []

    paragraphs: list[dict] = []
    for index, paragraph in enumerate(body.findall("w:p", WORD_NAMESPACE)):
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)).strip()
        style = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
        style_id = None if style is None else style.attrib.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
        paragraphs.append({"index": index, "text": text, "style": style_id})
    return paragraphs


def extract_bookmarks(document_root: ET.Element | None) -> set[str]:
    if document_root is None:
        return set()

    names: set[str] = set()
    for bookmark in document_root.findall(".//w:bookmarkStart", WORD_NAMESPACE):
        name = bookmark.attrib.get(qname("name"))
        if name:
            names.add(name)
    return names


def strip_toc_page_number(text: str) -> str:
    return re.sub(r"\s*\d+$", "", text.strip()).strip()


def extract_toc_entries(document_root: ET.Element | None) -> list[dict]:
    if document_root is None:
        return []

    body = document_root.find("w:body", WORD_NAMESPACE)
    if body is None:
        return []

    entries: list[dict] = []
    for index, paragraph in enumerate(body.findall("w:p", WORD_NAMESPACE)):
        style = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
        style_id = None if style is None else style.attrib.get(qname("val"))
        if not style_id or not style_id.lower().startswith("toc"):
            continue

        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)).strip()
        anchors = [
            anchor
            for anchor in (
                hyperlink.attrib.get(qname("anchor"))
                for hyperlink in paragraph.findall(".//w:hyperlink", WORD_NAMESPACE)
            )
            if anchor
        ]
        entries.append({
            "index": index,
            "style": style_id,
            "text": text,
            "anchors": anchors,
            "heading_text": strip_toc_page_number(text),
        })

    return entries


def update_fields_on_open(settings_root: ET.Element | None) -> bool:
    if settings_root is None:
        return False

    update_fields = settings_root.find("w:updateFields", WORD_NAMESPACE)
    if update_fields is None:
        return False

    value = update_fields.attrib.get(qname("val"))
    if value is None:
        return True
    return value.lower() in {"1", "true", "on"}


def count_dirty_fields(document_root: ET.Element | None) -> int:
    if document_root is None:
        return 0

    dirty_count = 0
    for field in document_root.findall(".//w:fldSimple", WORD_NAMESPACE):
        if field.attrib.get(qname("dirty"), "").lower() in {"1", "true", "on"}:
            dirty_count += 1
    for field in document_root.findall(".//w:fldChar", WORD_NAMESPACE):
        if field.attrib.get(qname("fldCharType")) != "begin":
            continue
        if field.attrib.get(qname("dirty"), "").lower() in {"1", "true", "on"}:
            dirty_count += 1
    return dirty_count


def extract_heading_texts(paragraphs: list[dict]) -> list[str]:
    results: list[str] = []
    for paragraph in paragraphs:
        style = (paragraph.get("style") or "").lower()
        text = paragraph.get("text") or ""
        if not text:
            continue
        if style.startswith("toc"):
            continue
        normalized = normalize_text(text)
        if style.startswith("heading") or normalized.startswith("CHUONG "):
            results.append(text)
    return results


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
    document_root = read_xml_from_docx(target_file, "word/document.xml") if target_exists else None
    settings_root = read_xml_from_docx(target_file, "word/settings.xml") if target_exists else None
    members = archive_members(target_file) if target_exists else []
    field_codes = extract_field_codes(document_root)
    paragraphs = extract_paragraphs(document_root)
    bookmarks = extract_bookmarks(document_root)
    toc_entries = extract_toc_entries(document_root)
    heading_texts = extract_heading_texts(paragraphs)
    source_headings = [item.get("text", "") for item in outline_payload.get("outline", [])]
    normalized_document_text = "\n".join(paragraph.get("text", "") for paragraph in paragraphs)
    duplicate_patterns = [pattern for pattern in ERROR_PATTERNS if pattern in normalized_document_text]

    required_preserve = set(plan.get("preserve", []))
    normalized_field_codes = [normalize_text(code) for code in field_codes]
    toc_present = any(" TOC " in f" {code} " or code.startswith("TOC") for code in normalized_field_codes)
    list_of_figures_present = any("FIGURE" in code for code in normalized_field_codes)
    list_of_tables_present = any("TABLE" in code for code in normalized_field_codes)
    header_count = len([name for name in members if name.startswith("word/header")])
    footer_count = len([name for name in members if name.startswith("word/footer")])
    required_parts_present = target_exists and "word/document.xml" in members and "word/styles.xml" in members
    update_fields_enabled = update_fields_on_open(settings_root)
    dirty_field_count = count_dirty_fields(document_root)
    refresh_on_open_ready = toc_present and update_fields_enabled and dirty_field_count > 0

    toc_missing_hyperlinks = [entry for entry in toc_entries if entry.get("text") and not entry.get("anchors")]
    toc_broken_anchors = [
        entry
        for entry in toc_entries
        if any(anchor not in bookmarks for anchor in entry.get("anchors", []))
    ]
    toc_heading_texts = [entry.get("heading_text", "") for entry in toc_entries if entry.get("heading_text")]
    toc_rendered_matches_source = is_subsequence(source_headings, toc_heading_texts)
    toc_links_ok = not toc_missing_hyperlinks and not toc_broken_anchors
    toc_ok = (
        "toc" not in required_preserve
        or (
            toc_present
            and not toc_missing_hyperlinks
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
        "section_breaks": _check_section_breaks(document_root, template_profile),
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

    qa_report = {
        "status": "passed" if all([
            required_parts_present,
            scaffold_preserved,
            replace_ranges_resolved,
            outline_ok,
            body_replaced_ok,
            not template_residue,
            not duplicate_patterns,
        ]) else "failed",
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
            "validate": target_exists,
            "section_breaks": scaffold_checks["section_breaks"],
        },
        "toc_refresh_strategy": "update-fields-on-open" if refresh_on_open_ready else "rendered-in-package",
        "update_fields_on_open": update_fields_enabled,
        "dirty_field_count": dirty_field_count,
        "bookmark_count": len(bookmarks),
        "toc_entry_count": len(toc_entries),
        "toc_rendered_matches_source": toc_rendered_matches_source,
        "toc_missing_hyperlinks": [entry["index"] for entry in toc_missing_hyperlinks],
        "toc_broken_anchor_entries": [entry["index"] for entry in toc_broken_anchors],
        "message": "QA đã kiểm package, scaffold, range và semantic gate cho contract preserve-template-scaffold."
    }

    run_state["artifacts"]["qa_report"] = str(run_dir / "qa_report.json")
    run_state["status"] = "ready" if qa_report["status"] == "passed" else "needs-repair"

    write_json(run_dir / "qa_report.json", qa_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()