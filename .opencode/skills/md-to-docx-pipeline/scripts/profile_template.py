from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

from officecli_native import (
    ensure_officecli_available,
    is_truthy,
    normalize_text,
    officecli_get,
    officecli_query,
    officecli_view,
    to_int,
    write_json,
)


HEADING_STYLE_PATTERN = re.compile(r"\bHEADING\s*[1-9]\b")


def looks_like_heading_style(style: str | None) -> bool:
    if not style:
        return False
    normalized = normalize_text(style)
    return bool(HEADING_STYLE_PATTERN.search(normalized)) or "TIEU DE" in normalized or normalized.startswith("CHUONG")


def paragraph_bookmarks(result: dict) -> list[dict]:
    bookmarks: list[dict] = []
    for child in result.get("children", []):
        if child.get("type") != "bookmark":
            continue
        bookmark_format = child.get("format", {})
        name = bookmark_format.get("name")
        bookmark_id = bookmark_format.get("id")
        if not name or bookmark_id in (None, ""):
            continue
        bookmarks.append({"name": name, "id": str(bookmark_id)})
    return bookmarks


def build_body_paragraphs(results: list[dict]) -> list[dict]:
    body_results = [result for result in results if str(result.get("path", "")).startswith("/body/")]
    paragraphs: list[dict] = []
    for index, result in enumerate(body_results):
        result_format = result.get("format", {})
        text = str(result.get("text") or "").strip()
        style_id = result_format.get("styleId") or result_format.get("style")
        style_name = result_format.get("styleName") or result.get("style") or style_id
        paragraphs.append(
            {
                "paragraph_index": index,
                "path": result.get("path"),
                "text": text,
                "style": style_name,
                "style_id": style_id,
                "num_id": result_format.get("numId"),
                "ilvl": result_format.get("ilvl"),
                "bookmarks": paragraph_bookmarks(result),
                "format": result_format,
            }
        )
    return paragraphs


def extract_reference_profile(body_paragraphs: list[dict]) -> dict:
    reference_heading_index: int | None = None

    for paragraph in body_paragraphs:
        text = str(paragraph.get("text") or "").strip()
        if not text:
            continue
        if normalize_text(text) != "TAI LIEU THAM KHAO":
            continue
        if not looks_like_heading_style(paragraph.get("style") or paragraph.get("style_id")):
            continue
        reference_heading_index = int(paragraph["paragraph_index"])
        break

    if reference_heading_index is None:
        return {}

    for paragraph in body_paragraphs:
        paragraph_index = int(paragraph["paragraph_index"])
        if paragraph_index <= reference_heading_index:
            continue

        text = str(paragraph.get("text") or "").strip()
        if not text:
            continue
        if looks_like_heading_style(paragraph.get("style") or paragraph.get("style_id")):
            break

        paragraph_format = paragraph.get("format", {})
        return {
            "path": paragraph.get("path"),
            "style_id": paragraph.get("style_id"),
            "style_name": paragraph.get("style"),
            "num_id": to_int(paragraph_format.get("numId")),
            "ilvl": to_int(paragraph_format.get("ilvl")),
            "list_style": paragraph_format.get("listStyle"),
            "align": paragraph_format.get("align") or paragraph_format.get("effective.alignment"),
            "space_before": paragraph_format.get("spaceBefore") or paragraph_format.get("effective.spaceBefore"),
            "space_after": paragraph_format.get("spaceAfter") or paragraph_format.get("effective.spaceAfter"),
            "line_spacing": paragraph_format.get("lineSpacing") or paragraph_format.get("effective.lineSpacing"),
            "line_rule": paragraph_format.get("lineRule") or paragraph_format.get("effective.lineRule"),
            "hanging_indent": paragraph_format.get("hangingIndent"),
            "size": paragraph_format.get("size") or paragraph_format.get("effective.size") or paragraph_format.get("size.cs"),
            "font_ascii": paragraph_format.get("font.ascii") or paragraph_format.get("effective.font.ascii"),
        }

    return {}


def extract_style_numbering(body_paragraphs: list[dict]) -> dict:
    candidates: dict[str, Counter[tuple[int, int]]] = {}

    for paragraph in body_paragraphs:
        style_id = paragraph.get("style_id")
        num_id = to_int(paragraph.get("num_id"))
        ilvl = to_int(paragraph.get("ilvl"))
        if not style_id or num_id in (None, 0):
            continue
        candidates.setdefault(str(style_id), Counter())[(int(num_id), 0 if ilvl is None else int(ilvl))] += 1

    numbering: dict = {}
    for style_id, counter in candidates.items():
        (num_id, ilvl), _ = counter.most_common(1)[0]
        numbering[style_id] = {"numId": num_id, "ilvl": ilvl}
    return numbering


def infer_outline_level(style_id: str | None, style_name: str | None) -> str | None:
    normalized = normalize_text(f"{style_id or ''} {style_name or ''}")
    match = re.search(r"HEADING\s*([1-9])", normalized)
    if match is None:
        return None
    return str(int(match.group(1)) - 1)


def extract_style_catalog(style_results: list[dict], style_numbering: dict) -> list[dict]:
    catalog: list[dict] = []

    for result in style_results:
        if result.get("type") != "style":
            continue

        style_format = result.get("format", {})
        style_id = style_format.get("id")
        if not style_id or style_format.get("type") != "paragraph":
            continue

        name = style_format.get("name") or result.get("text")
        numbering = style_numbering.get(style_id, {})
        catalog.append(
            {
                "style_id": style_id,
                "name": name,
                "default": style_id == "Normal",
                "custom": is_truthy(style_format.get("customStyle")),
                "qformat": style_id == "Normal" or looks_like_heading_style(name) or normalize_text(name or "").startswith("LIST"),
                "outline_level": infer_outline_level(style_id, name),
                "based_on": style_format.get("basedOn"),
                "num_id": None if not numbering else numbering.get("numId"),
                "ilvl": None if not numbering else numbering.get("ilvl"),
            }
        )

    return catalog


def extract_field_codes(field_results: list[dict], toc_results: list[dict]) -> list[str]:
    codes: list[str] = []

    for result in toc_results:
        instruction = str(result.get("text") or "").strip()
        if instruction:
            codes.append(instruction)

    for result in field_results:
        instruction = str(result.get("format", {}).get("instruction") or "").strip()
        if instruction:
            codes.append(instruction)

    return codes


def classify_body(body_elements: list[dict], body_paragraphs: list[dict], section_count: int) -> dict:
    if not body_paragraphs:
        return {
            "paragraph_count": 0,
            "section_count": section_count,
            "body_section_count": section_count,
            "headings": [],
            "anchor_candidates": [],
            "replace_range_candidates": [],
            "body_regions": {},
            "toc_paragraph_indices": [],
            "preview": [],
        }

    headings: list[dict] = []
    preview: list[dict] = []
    toc_paragraph_indices: list[int] = []

    for paragraph in body_paragraphs:
        text = str(paragraph.get("text") or "").strip()
        style = paragraph.get("style")
        style_id = paragraph.get("style_id")
        normalized_style = normalize_text(style or style_id or "")
        normalized_text = normalize_text(text)

        if text and len(preview) < 12:
            preview.append({"paragraph_index": paragraph["paragraph_index"], "style": style or style_id, "text": text[:160]})

        if normalized_style.startswith("TOC"):
            toc_paragraph_indices.append(paragraph["paragraph_index"])

        is_heading = looks_like_heading_style(style or style_id) or normalized_text.startswith("CHUONG ")
        if not is_heading or not text:
            continue

        headings.append(
            {
                "paragraph_index": paragraph["paragraph_index"],
                "path": paragraph.get("path"),
                "style": style or style_id,
                "style_id": style_id,
                "text": text,
                "bookmarks": paragraph.get("bookmarks", []),
            }
        )

    toc_end_index = max(toc_paragraph_indices) if toc_paragraph_indices else None
    first_heading = next(
        (
            heading
            for heading in headings
            if toc_end_index is None or int(heading["paragraph_index"]) > int(toc_end_index)
        ),
        None,
    )

    start_element_index: int | None = None
    last_content_element_index: int | None = None
    if first_heading is not None:
        heading_path = first_heading.get("path")
        for element_index, element in enumerate(body_elements):
            if element.get("path") == heading_path:
                start_element_index = element_index
                break

    last_content_paragraph_index: int | None = None
    for paragraph in body_paragraphs:
        if str(paragraph.get("text") or "").strip():
            last_content_paragraph_index = int(paragraph["paragraph_index"])

    last_content_element_index = last_content_paragraph_index if last_content_paragraph_index is not None else 0

    replace_candidates: list[dict] = []
    if first_heading is not None and last_content_element_index is not None:
        first_idx = int(first_heading["paragraph_index"])
        last_idx = last_content_element_index
        remove_paths = [
            paragraph["path"]
            for paragraph in body_paragraphs
            if first_idx <= int(paragraph["paragraph_index"]) <= last_idx
            and str(paragraph.get("path", "")).startswith("/body/")
        ]
        start_path = remove_paths[0] if remove_paths else None
        end_path = remove_paths[-1] if remove_paths else None
        start_paragraph_index = first_idx
        end_paragraph_index = last_idx if end_path else None

        first_heading_idx = int(first_heading["paragraph_index"])
        insert_after = None
        if first_heading_idx > 0:
            for paragraph in body_paragraphs:
                if int(paragraph["paragraph_index"]) == first_heading_idx - 1:
                    insert_after = paragraph.get("path")
                    break
        replace_candidates.append(
            {
                "name": "after-front-matter-to-end-of-main-story",
                "status": "resolved",
                "paragraph_start_index": start_paragraph_index,
                "paragraph_end_index": end_paragraph_index,
                "body_start_path": start_path,
                "body_end_path": end_path,
                "remove_paths": remove_paths,
                "insert_after_path": insert_after,
                "preserves_front_matter": first_heading_idx > 0,
            }
        )
    else:
        replace_candidates.append(
            {
                "name": "after-front-matter-to-end-of-main-story",
                "status": "unresolved",
                "paragraph_start_index": None,
                "paragraph_end_index": None,
                "body_start_path": None,
                "body_end_path": None,
                "remove_paths": [],
                "insert_after_path": None,
                "preserves_front_matter": False,
            }
        )

    return {
        "paragraph_count": len(body_paragraphs),
        "section_count": section_count,
        "body_section_count": section_count,
        "headings": headings,
        "anchor_candidates": headings,
        "replace_range_candidates": replace_candidates,
        "body_regions": {
            "front_matter_end_paragraph_index": None if first_heading is None or first_heading["paragraph_index"] == 0 else first_heading["paragraph_index"] - 1,
            "main_content_start_paragraph_index": None if first_heading is None else first_heading["paragraph_index"],
            "main_content_end_element_index": last_content_element_index,
            "toc_end_paragraph_index": toc_end_index,
        },
        "toc_paragraph_indices": toc_paragraph_indices,
        "preview": preview,
    }


def detect_preserve_parts(field_codes: list[str], header_results: list[dict], footer_results: list[dict], document_profile: dict) -> list[str]:
    preserve = ["styles-and-numbering", "section-breaks"]
    if header_results or footer_results:
        preserve.append("headers-footers")

    normalized_fields = [normalize_text(code) for code in field_codes]
    if any(" TOC " in f" {code} " or code.startswith("TOC") for code in normalized_fields):
        preserve.append("toc")
    if any('\\C "HINH"' in code or "FIGURE" in code for code in normalized_fields):
        preserve.append("list-of-figures")
    if any('\\C "BANG"' in code or "TABLE" in code for code in normalized_fields):
        preserve.append("list-of-tables")
    if document_profile.get("section_count", 0) > 0:
        preserve.append("page-setup")

    return sorted(set(preserve))


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập profile ngắn cho template DOCX.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    template_file = Path(args.template_file)
    run_dir = Path(args.run_dir)

    officecli_version = ensure_officecli_available()
    outline_view = officecli_view(template_file, "outline") or {}
    stats_view = officecli_view(template_file, "stats") or {}
    text_view = officecli_view(template_file, "text") or {}
    styles_tree = officecli_get(template_file, "/styles", depth=2) or {}
    numbering_tree = officecli_get(template_file, "/numbering", depth=4) or {}
    section_results = officecli_query(template_file, "section")
    style_results = officecli_query(template_file, "style")
    paragraph_results = officecli_query(template_file, "paragraph")
    header_results = officecli_query(template_file, "header")
    footer_results = officecli_query(template_file, "footer")
    toc_results = officecli_query(template_file, "toc")
    field_results = officecli_query(template_file, "field")

    body_elements = [element for element in text_view.get("elements", []) if str(element.get("path", "")).startswith("/body/")]
    body_paragraphs = build_body_paragraphs(paragraph_results)
    style_numbering = extract_style_numbering(body_paragraphs)
    style_catalog = extract_style_catalog(style_results, style_numbering)
    field_codes = extract_field_codes(field_results, toc_results)
    document_profile = classify_body(body_elements, body_paragraphs, len(section_results))

    payload = {
        "template_file": str(template_file),
        "officecli_version": officecli_version,
        "outline_snapshot": outline_view,
        "stats_snapshot": stats_view,
        "styles_tree": {
            "path": styles_tree.get("path"),
            "child_count": styles_tree.get("childCount"),
            "type": styles_tree.get("type"),
        },
        "numbering_tree": {
            "path": numbering_tree.get("path"),
            "child_count": numbering_tree.get("childCount"),
            "type": numbering_tree.get("type"),
        },
        "style_names": sorted({entry.get("name") for entry in style_catalog if entry.get("name")}),
        "style_catalog": style_catalog,
        "style_numbering": style_numbering,
        "has_numbering": bool(numbering_tree),
        "has_document_xml": bool(body_elements),
        "header_count": len(header_results),
        "footer_count": len(footer_results),
        "header_members": [result.get("path") for result in header_results],
        "footer_members": [result.get("path") for result in footer_results],
        "field_codes": field_codes,
        "preserve_defaults": detect_preserve_parts(field_codes, header_results, footer_results, document_profile),
        "reference_profile": extract_reference_profile(body_paragraphs),
        "document_profile": document_profile,
    }

    write_json(run_dir / "template_profile.json", payload)


if __name__ == "__main__":
    main()