from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path
from typing import Any

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
DIRECT_BODY_CHILD_PATTERN = re.compile(r"^/body/(?:p(?:\[@[^=]+=.\S+\])?|tbl)\[\d+\]$|^/body/p\[@\w+=\w+\]$")
DECIMAL_HEADING_PATTERN = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+")
BACK_MATTER_MARKERS = {
    "references": {"TAI LIEU THAM KHAO", "REFERENCES", "BIBLIOGRAPHY"},
    "appendix": {"PHU LUC", "APPENDIX"},
}


def looks_like_heading_style(style: str | None) -> bool:
    if not style:
        return False
    normalized = normalize_text(style)
    return bool(HEADING_STYLE_PATTERN.search(normalized)) or "TIEU DE" in normalized or normalized.startswith("CHUONG")


def direct_body_path(path: str | None) -> str | None:
    if not path:
        return None
    if DIRECT_BODY_CHILD_PATTERN.match(str(path)):
        return str(path)
    match = re.match(r"^(/body/(?:p|tbl)\[\d+\])", str(path))
    return None if match is None else match.group(1)


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


def run_format_snapshot(run_format: dict) -> dict:
    snapshot: dict[str, Any] = {}
    for source_key, target_key in [
        ("font.latin", "font_latin"),
        ("font.ascii", "font_ascii"),
        ("effective.font.ascii", "font_ascii"),
        ("font.ea", "font_east_asia"),
        ("effective.font.eastAsia", "font_east_asia"),
        ("font.cs", "font_cs"),
        ("size", "size"),
        ("effective.size", "size"),
        ("color", "color"),
        ("bold", "bold"),
        ("italic", "italic"),
        ("underline", "underline"),
        ("superscript", "superscript"),
        ("subscript", "subscript"),
    ]:
        value = run_format.get(source_key)
        if value in (None, ""):
            continue
        snapshot.setdefault(target_key, value)
    return snapshot


def paragraph_runs(result: dict) -> list[dict]:
    runs: list[dict] = []
    for child in result.get("children", []):
        if child.get("type") != "run":
            continue
        run_snapshot = {
            "path": child.get("path"),
            "text": str(child.get("text") or ""),
            **run_format_snapshot(child.get("format", {})),
        }
        if run_snapshot.get("text"):
            runs.append(run_snapshot)
    return runs


def paragraph_format_snapshot(paragraph_format: dict) -> dict:
    snapshot: dict[str, Any] = {}
    for source_key, target_key in [
        ("align", "align"),
        ("styleId", "style_id"),
        ("styleName", "style_name"),
        ("style", "style"),
        ("numId", "num_id"),
        ("ilvl", "ilvl"),
        ("listStyle", "list_style"),
        ("spaceBefore", "space_before"),
        ("spaceAfter", "space_after"),
        ("lineSpacing", "line_spacing"),
        ("lineRule", "line_rule"),
        ("hangingIndent", "hanging_indent"),
        ("size", "size"),
        ("effective.size", "size"),
        ("font.latin", "font_latin"),
        ("effective.font.ascii", "font_ascii"),
        ("font.ea", "font_east_asia"),
        ("effective.font.eastAsia", "font_east_asia"),
        ("color", "color"),
        ("bold", "bold"),
        ("italic", "italic"),
        ("shading.fill", "shading_fill"),
    ]:
        value = paragraph_format.get(source_key)
        if value in (None, ""):
            continue
        snapshot.setdefault(target_key, value)
    return snapshot


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
                "direct_body_path": direct_body_path(result.get("path")),
                "text": text,
                "style": style_name,
                "style_id": style_id,
                "num_id": result_format.get("numId"),
                "ilvl": result_format.get("ilvl"),
                "bookmarks": paragraph_bookmarks(result),
                "runs": paragraph_runs(result),
                "format": result_format,
                "format_profile": paragraph_format_snapshot(result_format),
            }
        )
    return paragraphs


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
                "normalized_name": normalize_text(name or ""),
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


def build_style_graph(style_catalog: list[dict]) -> dict:
    catalog_by_id = {entry["style_id"]: entry for entry in style_catalog}

    def ancestry(style_id: str) -> list[dict]:
        chain: list[dict] = []
        cursor = style_id
        seen: set[str] = set()
        while cursor and cursor not in seen and cursor in catalog_by_id:
            seen.add(cursor)
            entry = catalog_by_id[cursor]
            chain.append(entry)
            cursor = entry.get("based_on")
        return chain

    graph: dict[str, dict] = {}
    for entry in style_catalog:
        chain = ancestry(entry["style_id"])
        resolved_outline = next((item.get("outline_level") for item in chain if item.get("outline_level") is not None), None)
        heading_like = any(item.get("outline_level") is not None or looks_like_heading_style(item.get("name") or item.get("style_id")) for item in chain)
        list_like = any("LIST" in normalize_text(f"{item.get('name') or ''} {item.get('style_id') or ''}") for item in chain)
        numbering_owner = next((item for item in chain if item.get("num_id") is not None), None)
        graph[entry["style_id"]] = {
            "style_id": entry["style_id"],
            "name": entry.get("name"),
            "normalized_name": entry.get("normalized_name"),
            "based_on_chain": [item["style_id"] for item in chain],
            "resolved_outline_level": resolved_outline,
            "heading_like": heading_like,
            "list_like": list_like,
            "numbering": None if numbering_owner is None else {"numId": numbering_owner.get("num_id"), "ilvl": numbering_owner.get("ilvl")},
        }
    return graph


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


def extract_field_graph(field_results: list[dict], toc_results: list[dict]) -> dict:
    fields: list[dict] = []
    pageref_anchors: list[str] = []

    for result in field_results:
        field_format = result.get("format", {})
        instruction = str(field_format.get("instruction") or "").strip()
        field_type = str(field_format.get("fieldType") or "").lower()
        if field_type == "pageref":
            match = re.search(r"PAGEREF\s+([^\s]+)", instruction, re.IGNORECASE)
            if match:
                pageref_anchors.append(match.group(1))
        fields.append(
            {
                "path": result.get("path"),
                "field_type": field_type or None,
                "instruction": instruction,
            }
        )

    toc_nodes = []
    for result in toc_results:
        toc_format = result.get("format", {})
        toc_nodes.append(
            {
                "path": result.get("path"),
                "instruction": str(toc_format.get("instruction") or result.get("text") or "").strip(),
                "levels": toc_format.get("levels"),
                "hyperlinks": toc_format.get("hyperlinks"),
            }
        )

    normalized_codes = [normalize_text(field.get("instruction") or "") for field in fields + toc_nodes]
    has_toc = bool(toc_nodes) or any(" TOC " in f" {code} " or code.startswith("TOC") for code in normalized_codes)
    has_list_of_figures = any('\\C "HINH"' in code or "FIGURE" in code for code in normalized_codes)
    has_list_of_tables = any('\\C "BANG"' in code or "TABLE" in code for code in normalized_codes)

    return {
        "fields": fields,
        "toc_nodes": toc_nodes,
        "pageref_anchors": sorted(set(pageref_anchors)),
        "has_toc": has_toc,
        "has_list_of_figures": has_list_of_figures,
        "has_list_of_tables": has_list_of_tables,
    }


def extract_bookmark_graph(body_paragraphs: list[dict]) -> dict:
    items: list[dict] = []
    for paragraph in body_paragraphs:
        for bookmark in paragraph.get("bookmarks", []):
            items.append(
                {
                    "name": bookmark.get("name"),
                    "id": bookmark.get("id"),
                    "paragraph_path": paragraph.get("path"),
                    "direct_body_path": paragraph.get("direct_body_path"),
                    "text": paragraph.get("text"),
                }
            )

    return {
        "count": len(items),
        "names": sorted({item.get("name") for item in items if item.get("name")}),
        "items": items,
    }


def zone_marker(text: str) -> str | None:
    normalized = normalize_text(text)
    for zone_name, markers in BACK_MATTER_MARKERS.items():
        if normalized in markers:
            return zone_name
    return None


def guess_heading_level(paragraph: dict, style_graph: dict) -> int | None:
    style_id = paragraph.get("style_id")
    if style_id and style_id in style_graph:
        resolved_outline = style_graph[style_id].get("resolved_outline_level")
        if resolved_outline is not None:
            return int(str(resolved_outline)) + 1

    text = str(paragraph.get("text") or "").strip()
    if not text:
        return None

    normalized = normalize_text(text)
    if normalized.startswith("CHUONG ") or normalized.startswith("PHAN ") or zone_marker(text) is not None:
        return 1

    decimal_match = DECIMAL_HEADING_PATTERN.match(text)
    if decimal_match:
        return len(decimal_match.group(1).split("."))

    if looks_like_heading_style(paragraph.get("style") or paragraph.get("style_id")):
        return 1

    return None


def is_heading_paragraph(paragraph: dict, style_graph: dict) -> bool:
    return guess_heading_level(paragraph, style_graph) is not None


def build_zone_descriptor(name: str, start_index: int | None, end_index: int | None, body_paragraphs: list[dict]) -> dict | None:
    if start_index is None or end_index is None or end_index < start_index:
        return None
    start_paragraph = body_paragraphs[start_index]
    end_paragraph = body_paragraphs[end_index]
    return {
        "name": name,
        "paragraph_start_index": start_index,
        "paragraph_end_index": end_index,
        "body_start_path": start_paragraph.get("path"),
        "body_end_path": end_paragraph.get("path"),
        "direct_start_path": start_paragraph.get("direct_body_path"),
        "direct_end_path": end_paragraph.get("direct_body_path"),
    }


def previous_nonempty_index(body_paragraphs: list[dict], before_index: int | None) -> int | None:
    if before_index is None:
        return None
    for index in range(before_index - 1, -1, -1):
        if str(body_paragraphs[index].get("text") or "").strip():
            return index
    return None


def build_replace_candidate(
    name: str,
    *,
    start_index: int | None,
    end_index: int | None,
    body_paragraphs: list[dict],
    direct_body_children: list[dict],
    preserve_zones: list[str] | None = None,
) -> dict:
    if start_index is None or end_index is None or end_index < start_index:
        return {
            "name": name,
            "status": "unresolved",
            "paragraph_start_index": None,
            "paragraph_end_index": None,
            "body_start_path": None,
            "body_end_path": None,
            "direct_body_start_path": None,
            "direct_body_end_path": None,
            "remove_paths": [],
            "insert_after_path": None,
            "remove_scope": "direct-body-children",
            "preserve_zones": preserve_zones or [],
        }

    start_paragraph = body_paragraphs[start_index]
    end_paragraph = body_paragraphs[end_index]
    direct_start = start_paragraph.get("direct_body_path")
    direct_end = end_paragraph.get("direct_body_path")
    direct_paths = [item.get("path") for item in direct_body_children]

    if direct_start not in direct_paths or direct_end not in direct_paths:
        return {
            "name": name,
            "status": "unresolved",
            "paragraph_start_index": start_index,
            "paragraph_end_index": end_index,
            "body_start_path": start_paragraph.get("path"),
            "body_end_path": end_paragraph.get("path"),
            "direct_body_start_path": direct_start,
            "direct_body_end_path": direct_end,
            "remove_paths": [],
            "insert_after_path": None,
            "remove_scope": "direct-body-children",
            "preserve_zones": preserve_zones or [],
        }

    start_direct_index = direct_paths.index(direct_start)
    end_direct_index = direct_paths.index(direct_end)
    remove_paths = direct_paths[start_direct_index : end_direct_index + 1]
    insert_after_path = direct_paths[start_direct_index - 1] if start_direct_index > 0 else None

    return {
        "name": name,
        "status": "resolved",
        "paragraph_start_index": start_index,
        "paragraph_end_index": end_index,
        "body_start_path": start_paragraph.get("path"),
        "body_end_path": end_paragraph.get("path"),
        "direct_body_start_path": direct_start,
        "direct_body_end_path": direct_end,
        "remove_paths": remove_paths,
        "insert_after_path": insert_after_path,
        "remove_scope": "direct-body-children",
        "preserve_zones": preserve_zones or [],
        "preserves_front_matter": start_direct_index > 0,
    }


def build_insert_after_candidate(
    name: str,
    *,
    insert_after_path: str | None,
    paragraph_end_index: int | None,
    preserve_zones: list[str] | None = None,
) -> dict:
    return {
        "name": name,
        "status": "resolved",
        "paragraph_start_index": None if paragraph_end_index is None else int(paragraph_end_index) + 1,
        "paragraph_end_index": paragraph_end_index,
        "body_start_path": None,
        "body_end_path": None,
        "direct_body_start_path": None,
        "direct_body_end_path": None,
        "remove_paths": [],
        "insert_after_path": insert_after_path,
        "remove_scope": "direct-body-children",
        "preserve_zones": preserve_zones or [],
        "preserves_front_matter": True,
    }


def classify_body(body_elements: list[dict], body_paragraphs: list[dict], section_count: int, style_graph: dict) -> dict:
    if not body_paragraphs:
        return {
            "paragraph_count": 0,
            "section_count": section_count,
            "body_section_count": section_count,
            "direct_body_child_count": 0,
            "headings": [],
            "anchor_candidates": [],
            "replace_range_candidates": [],
            "preserve_zones": [],
            "body_regions": {},
            "toc_paragraph_indices": [],
            "preview": [],
            "zone_markers": {},
        }

    direct_body_children = [
        {"path": element.get("path"), "type": element.get("type")}
        for element in body_elements
        if DIRECT_BODY_CHILD_PATTERN.match(str(element.get("path") or ""))
    ]

    headings: list[dict] = []
    preview: list[dict] = []
    toc_paragraph_indices: list[int] = []
    zone_markers: dict[str, int] = {}

    for paragraph in body_paragraphs:
        text = str(paragraph.get("text") or "").strip()
        style = paragraph.get("style")
        style_id = paragraph.get("style_id")
        normalized_style = normalize_text(style or style_id or "")
        marker = zone_marker(text)
        level_guess = guess_heading_level(paragraph, style_graph)

        if text and len(preview) < 12:
            preview.append({"paragraph_index": paragraph["paragraph_index"], "style": style or style_id, "text": text[:160]})

        if normalized_style.startswith("TOC"):
            toc_paragraph_indices.append(paragraph["paragraph_index"])

        if marker and marker not in zone_markers:
            zone_markers[marker] = int(paragraph["paragraph_index"])

        if level_guess is None or not text:
            continue

        headings.append(
            {
                "paragraph_index": paragraph["paragraph_index"],
                "path": paragraph.get("path"),
                "direct_body_path": paragraph.get("direct_body_path"),
                "style": style or style_id,
                "style_id": style_id,
                "text": text,
                "bookmarks": paragraph.get("bookmarks", []),
                "level_guess": level_guess,
                "zone": marker or "body",
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
    last_nonempty_index = next(
        (paragraph["paragraph_index"] for paragraph in reversed(body_paragraphs) if str(paragraph.get("text") or "").strip()),
        None,
    )

    references_start = zone_markers.get("references")
    appendix_start = zone_markers.get("appendix")
    preserve_zones: list[dict] = []

    if first_heading is not None and int(first_heading["paragraph_index"]) > 0:
        zone = build_zone_descriptor("front-matter", 0, int(first_heading["paragraph_index"]) - 1, body_paragraphs)
        if zone is not None:
            preserve_zones.append(zone)
    elif first_heading is None and last_nonempty_index is not None:
        zone = build_zone_descriptor("front-matter", 0, int(last_nonempty_index), body_paragraphs)
        if zone is not None:
            preserve_zones.append(zone)

    if references_start is not None:
        references_end = previous_nonempty_index(body_paragraphs, appendix_start) if appendix_start and appendix_start > references_start else last_nonempty_index
        zone = build_zone_descriptor("references", references_start, references_end, body_paragraphs)
        if zone is not None:
            preserve_zones.append(zone)

    if appendix_start is not None:
        zone = build_zone_descriptor("appendix", appendix_start, last_nonempty_index, body_paragraphs)
        if zone is not None:
            preserve_zones.append(zone)

    replace_candidates: list[dict] = []
    if first_heading is not None and last_nonempty_index is not None:
        first_heading_index = int(first_heading["paragraph_index"])
        replace_candidates.append(
            build_replace_candidate(
                "after-front-matter-to-end-of-main-story",
                start_index=first_heading_index,
                end_index=last_nonempty_index,
                body_paragraphs=body_paragraphs,
                direct_body_children=direct_body_children,
                preserve_zones=[zone["name"] for zone in preserve_zones],
            )
        )

        if references_start is not None and references_start > first_heading_index:
            references_end = previous_nonempty_index(body_paragraphs, references_start)
            replace_candidates.append(
                build_replace_candidate(
                    "after-front-matter-before-references",
                    start_index=first_heading_index,
                    end_index=references_end,
                    body_paragraphs=body_paragraphs,
                    direct_body_children=direct_body_children,
                    preserve_zones=["front-matter", "references", "appendix"],
                )
            )

        if appendix_start is not None and appendix_start > first_heading_index:
            appendix_end = previous_nonempty_index(body_paragraphs, appendix_start)
            replace_candidates.append(
                build_replace_candidate(
                    "after-front-matter-before-appendix",
                    start_index=first_heading_index,
                    end_index=appendix_end,
                    body_paragraphs=body_paragraphs,
                    direct_body_children=direct_body_children,
                    preserve_zones=["front-matter", "appendix"],
                )
            )
    else:
        replace_candidates.append(
            build_insert_after_candidate(
                "after-front-matter-to-end-of-main-story",
                insert_after_path=None if not direct_body_children else direct_body_children[-1].get("path"),
                paragraph_end_index=last_nonempty_index,
                preserve_zones=[zone["name"] for zone in preserve_zones],
            )
        )

    return {
        "paragraph_count": len(body_paragraphs),
        "section_count": section_count,
        "body_section_count": section_count,
        "direct_body_child_count": len(direct_body_children),
        "headings": headings,
        "anchor_candidates": headings,
        "replace_range_candidates": replace_candidates,
        "preserve_zones": preserve_zones,
        "body_regions": {
            "front_matter_end_paragraph_index": None if first_heading is None or first_heading["paragraph_index"] == 0 else first_heading["paragraph_index"] - 1,
            "main_content_start_paragraph_index": None if first_heading is None else first_heading["paragraph_index"],
            "main_content_end_paragraph_index": last_nonempty_index,
            "reference_start_paragraph_index": references_start,
            "appendix_start_paragraph_index": appendix_start,
            "toc_end_paragraph_index": toc_end_index,
        },
        "toc_paragraph_indices": toc_paragraph_indices,
        "preview": preview,
        "zone_markers": zone_markers,
    }


def prototype_from_paragraph(paragraph: dict, role: str, *, fallback_role: str | None = None, synthetic_run_overrides: dict | None = None) -> dict:
    runs = [dict(run) for run in paragraph.get("runs", [])]
    if synthetic_run_overrides and runs:
        for run in runs:
            run.update(synthetic_run_overrides)
    return {
        "role": role,
        "fallback_role": fallback_role,
        "path": paragraph.get("path"),
        "direct_body_path": paragraph.get("direct_body_path"),
        "style_id": paragraph.get("style_id"),
        "style_name": paragraph.get("style"),
        "paragraph_format": paragraph.get("format_profile", {}),
        "runs": runs,
        "num_id": to_int(paragraph.get("num_id")),
        "ilvl": to_int(paragraph.get("ilvl")),
        "text": paragraph.get("text"),
    }


def extract_reference_profile(body_paragraphs: list[dict], style_graph: dict) -> dict:
    reference_heading_index: int | None = None

    for paragraph in body_paragraphs:
        text = str(paragraph.get("text") or "").strip()
        if not text:
            continue
        if zone_marker(text) != "references":
            continue
        if not is_heading_paragraph(paragraph, style_graph):
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
        if is_heading_paragraph(paragraph, style_graph):
            break

        return prototype_from_paragraph(paragraph, "reference", fallback_role="body")

    return {}


def paragraph_by_index(body_paragraphs: list[dict], paragraph_index: int | None) -> dict | None:
    if paragraph_index is None:
        return None
    for paragraph in body_paragraphs:
        if int(paragraph["paragraph_index"]) == int(paragraph_index):
            return paragraph
    return None


def is_direct_body_paragraph(paragraph: dict) -> bool:
    path = str(paragraph.get("path") or "")
    direct_body_path = str(paragraph.get("direct_body_path") or "")
    return bool(path) and path == direct_body_path and path.startswith("/body/p[")


def is_all_caps_like_text(text: str) -> bool:
    letters = [character for character in text if character.isalpha()]
    if len(letters) < 6:
        return False
    uppercase_ratio = sum(1 for character in letters if character.isupper()) / len(letters)
    return uppercase_ratio >= 0.9


def is_preferred_body_prototype(paragraph: dict, style_graph: dict) -> bool:
    text = str(paragraph.get("text") or "").strip()
    if not text or is_heading_paragraph(paragraph, style_graph) or zone_marker(text) is not None:
        return False

    paragraph_format = paragraph.get("format") or {}
    runs = paragraph.get("runs") or []
    first_run = next((run for run in runs if str(run.get("text") or "").strip()), {})
    align = str(paragraph_format.get("align") or "").lower()
    is_bold = is_truthy(paragraph_format.get("bold")) or is_truthy(first_run.get("bold"))
    is_italic = is_truthy(paragraph_format.get("italic")) or is_truthy(first_run.get("italic"))
    has_lowercase = any(character.isalpha() and character.islower() for character in text)
    ends_like_sentence = text.rstrip().endswith((".", ";", ":"))
    return has_lowercase and ends_like_sentence and len(text) >= 24 and align != "center" and not is_bold and not is_italic and not is_all_caps_like_text(text)


def extract_prototype_catalog(body_paragraphs: list[dict], style_graph: dict, reference_profile: dict, document_profile: dict) -> dict:
    headings = document_profile.get("headings", [])
    main_start = document_profile.get("body_regions", {}).get("main_content_start_paragraph_index")

    def first_heading(level: int) -> dict | None:
        for heading in headings:
            if int(heading.get("level_guess") or 0) == level:
                return paragraph_by_index(body_paragraphs, int(heading["paragraph_index"]))
        return None

    def first_matching(predicate: Any) -> dict | None:
        for paragraph in body_paragraphs:
            if predicate(paragraph):
                return paragraph
        return None

    def first_direct_body_matching(predicate: Any) -> dict | None:
        return first_matching(lambda paragraph: is_direct_body_paragraph(paragraph) and predicate(paragraph))

    body_prototype = first_direct_body_matching(
        lambda paragraph: int(paragraph["paragraph_index"]) >= int(main_start or 0) and is_preferred_body_prototype(paragraph, style_graph)
    ) or first_direct_body_matching(
        lambda paragraph: is_preferred_body_prototype(paragraph, style_graph)
    ) or first_matching(
        lambda paragraph: int(paragraph["paragraph_index"]) >= int(main_start or 0) and is_preferred_body_prototype(paragraph, style_graph)
    ) or first_matching(
        lambda paragraph: is_preferred_body_prototype(paragraph, style_graph)
    ) or first_direct_body_matching(
        lambda paragraph: int(paragraph["paragraph_index"]) >= int(main_start or 0)
        and bool(str(paragraph.get("text") or "").strip())
        and not is_heading_paragraph(paragraph, style_graph)
    ) or first_direct_body_matching(
        lambda paragraph: bool(str(paragraph.get("text") or "").strip()) and not is_heading_paragraph(paragraph, style_graph)
    ) or first_matching(
        lambda paragraph: int(paragraph["paragraph_index"]) >= int(main_start or 0)
        and bool(str(paragraph.get("text") or "").strip())
        and not is_heading_paragraph(paragraph, style_graph)
    ) or first_matching(lambda paragraph: bool(str(paragraph.get("text") or "").strip()) and not is_heading_paragraph(paragraph, style_graph))

    list_prototype = first_direct_body_matching(
        lambda paragraph: bool(str(paragraph.get("text") or "").strip())
        and (
            to_int(paragraph.get("num_id")) not in (None, 0)
            or style_graph.get(paragraph.get("style_id") or "", {}).get("list_like")
            or str(paragraph.get("format", {}).get("listStyle") or "") != ""
        )
    ) or first_matching(
        lambda paragraph: bool(str(paragraph.get("text") or "").strip())
        and (
            to_int(paragraph.get("num_id")) not in (None, 0)
            or style_graph.get(paragraph.get("style_id") or "", {}).get("list_like")
            or str(paragraph.get("format", {}).get("listStyle") or "") != ""
        )
    )

    catalog: dict[str, dict] = {}
    for role, paragraph in [
        ("h1", first_heading(1)),
        ("h2", first_heading(2)),
        ("h3", first_heading(3)),
        ("body", body_prototype),
        ("list", list_prototype),
    ]:
        if paragraph is None:
            continue
        catalog[role] = prototype_from_paragraph(paragraph, role, fallback_role="body" if role != "body" else None)

    if reference_profile:
        catalog["reference"] = reference_profile
    elif body_prototype is not None:
        catalog["reference"] = prototype_from_paragraph(body_prototype, "reference", fallback_role="body")

    if body_prototype is not None and "blockquote" not in catalog:
        catalog["blockquote"] = prototype_from_paragraph(body_prototype, "blockquote", fallback_role="body")
        catalog["code"] = prototype_from_paragraph(
            body_prototype,
            "code",
            fallback_role="body",
            synthetic_run_overrides={"font_latin": "Courier New", "font_ascii": "Courier New"},
        )

    return catalog


def detect_preserve_parts(field_graph: dict, header_results: list[dict], footer_results: list[dict], document_profile: dict) -> list[str]:
    preserve = ["styles-and-numbering", "section-breaks"]
    if header_results or footer_results:
        preserve.append("headers-footers")
    if field_graph.get("has_toc"):
        preserve.append("toc")
    if field_graph.get("has_list_of_figures"):
        preserve.append("list-of-figures")
    if field_graph.get("has_list_of_tables"):
        preserve.append("list-of-tables")
    if document_profile.get("section_count", 0) > 0:
        preserve.append("page-setup")
    if field_graph.get("pageref_anchors"):
        preserve.append("cross-references")
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
    style_graph = build_style_graph(style_catalog)
    field_codes = extract_field_codes(field_results, toc_results)
    field_graph = extract_field_graph(field_results, toc_results)
    document_profile = classify_body(body_elements, body_paragraphs, len(section_results), style_graph)
    reference_profile = extract_reference_profile(body_paragraphs, style_graph)
    prototype_catalog = extract_prototype_catalog(body_paragraphs, style_graph, reference_profile, document_profile)
    bookmark_graph = extract_bookmark_graph(body_paragraphs)

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
        "style_graph": style_graph,
        "style_numbering": style_numbering,
        "has_numbering": bool(numbering_tree),
        "has_document_xml": bool(body_elements),
        "header_count": len(header_results),
        "footer_count": len(footer_results),
        "header_members": [result.get("path") for result in header_results],
        "footer_members": [result.get("path") for result in footer_results],
        "field_codes": field_codes,
        "field_graph": field_graph,
        "bookmark_graph": bookmark_graph,
        "prototype_catalog": prototype_catalog,
        "preserve_defaults": detect_preserve_parts(field_graph, header_results, footer_results, document_profile),
        "reference_profile": reference_profile,
        "document_profile": document_profile,
        "scaffold_contract": {
            "preserve_zones": document_profile.get("preserve_zones", []),
            "replace_zones": document_profile.get("replace_range_candidates", []),
            "dependent_sections": [
                name
                for name, enabled in [
                    ("toc", field_graph.get("has_toc")),
                    ("list-of-figures", field_graph.get("has_list_of_figures")),
                    ("list-of-tables", field_graph.get("has_list_of_tables")),
                    ("cross-references", bool(field_graph.get("pageref_anchors"))),
                ]
                if enabled
            ],
        },
    }

    write_json(run_dir / "template_profile.json", payload)


if __name__ == "__main__":
    main()