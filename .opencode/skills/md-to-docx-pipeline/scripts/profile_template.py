from __future__ import annotations

import argparse
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NAMESPACE = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def read_xml_from_docx(docx_path: Path, member: str) -> ET.Element | None:
    with zipfile.ZipFile(docx_path) as archive:
        if member not in archive.namelist():
            return None
        with archive.open(member) as handle:
            return ET.fromstring(handle.read())


def extract_style_names(styles_root: ET.Element | None) -> list[str]:
    if styles_root is None:
        return []
    names: list[str] = []
    for style in styles_root.findall("w:style", WORD_NAMESPACE):
        name = style.find("w:name", WORD_NAMESPACE)
        if name is not None:
            value = name.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val")
            if value:
                names.append(value)
    return sorted(set(names))


def extract_style_catalog(styles_root: ET.Element | None) -> list[dict]:
    if styles_root is None:
        return []

    catalog: list[dict] = []
    for style in styles_root.findall("w:style", WORD_NAMESPACE):
        style_type = style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}type")
        style_id = style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}styleId")
        if style_type != "paragraph" or not style_id:
            continue

        name_node = style.find("w:name", WORD_NAMESPACE)
        outline_node = style.find("w:pPr/w:outlineLvl", WORD_NAMESPACE)
        based_on_node = style.find("w:basedOn", WORD_NAMESPACE)
        num_id_node = style.find("w:pPr/w:numPr/w:numId", WORD_NAMESPACE)
        ilvl_node = style.find("w:pPr/w:numPr/w:ilvl", WORD_NAMESPACE)

        catalog.append(
            {
                "style_id": style_id,
                "name": None if name_node is None else name_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val"),
                "default": style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}default") == "1",
                "custom": style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}customStyle") == "1",
                "qformat": style.find("w:qFormat", WORD_NAMESPACE) is not None,
                "outline_level": None if outline_node is None else outline_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val"),
                "based_on": None if based_on_node is None else based_on_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val"),
                "num_id": None if num_id_node is None else num_id_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val"),
                "ilvl": None if ilvl_node is None else ilvl_node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val"),
            }
        )

    return catalog


def extract_style_numbering(style_catalog: list[dict]) -> dict:
    lookup = {entry.get("style_id"): entry for entry in style_catalog if entry.get("style_id")}

    def resolve(style_id: str | None, seen: set[str]) -> dict | None:
        if not style_id or style_id in seen:
            return None
        entry = lookup.get(style_id)
        if entry is None:
            return None

        num_id = entry.get("num_id")
        ilvl = entry.get("ilvl")
        if num_id not in (None, "", "0"):
            return {"numId": int(num_id), "ilvl": 0 if ilvl in (None, "") else int(ilvl)}

        return resolve(entry.get("based_on"), seen | {style_id})

    style_numbering: dict = {}
    for style_id in lookup:
        numbering = resolve(style_id, set())
        if numbering is not None:
            style_numbering[style_id] = numbering
    return style_numbering


def detect_header_footer_members(docx_path: Path) -> dict:
    with zipfile.ZipFile(docx_path) as archive:
        members = archive.namelist()
    headers = [name for name in members if name.startswith("word/header")]
    footers = [name for name in members if name.startswith("word/footer")]
    return {"headers": headers, "footers": footers}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.upper().split())


def looks_like_heading_style(style: str | None) -> bool:
    if not style:
        return False
    normalized = normalize_text(style)
    return bool(re.search(r"\bHEADING\s*[1-9]\b", normalized)) or "TIEU DE" in normalized or normalized.startswith("CHUONG")


def extract_field_codes(document_root: ET.Element | None) -> list[str]:
    if document_root is None:
        return []

    field_codes: list[str] = []
    for field in document_root.findall(".//w:fldSimple", WORD_NAMESPACE):
        instruction = field.attrib.get(f"{{{WORD_NAMESPACE['w']}}}instr")
        if instruction:
            field_codes.append(instruction)

    for instruction in document_root.findall(".//w:instrText", WORD_NAMESPACE):
        if instruction.text and instruction.text.strip():
            field_codes.append(instruction.text.strip())

    return field_codes


def paragraph_text(paragraph: ET.Element) -> str:
    texts = [node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)]
    return "".join(texts).strip()


def paragraph_style(paragraph: ET.Element) -> str | None:
    style = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
    if style is None:
        return None
    return style.attrib.get(f"{{{WORD_NAMESPACE['w']}}}val")


def field_char_type(node: ET.Element) -> str | None:
    return node.attrib.get(f"{{{WORD_NAMESPACE['w']}}}fldCharType")


def paragraph_instr_text(paragraph: ET.Element) -> str:
    return " ".join((node.text or "") for node in paragraph.findall(".//w:instrText", WORD_NAMESPACE)).strip()


def find_toc_paragraph_indices(paragraphs: list[ET.Element]) -> set[int]:
    toc_indices: set[int] = set()
    pending_field_start: int | None = None
    in_toc = False

    for index, paragraph in enumerate(paragraphs):
        style_id = paragraph_style(paragraph)
        field_types = [field_char_type(node) for node in paragraph.findall(".//w:fldChar", WORD_NAMESPACE)]
        instr_text = normalize_text(paragraph_instr_text(paragraph))
        has_toc_instruction = " TOC " in f" {instr_text} " or instr_text.startswith("TOC")
        toc_style = normalize_text(style_id or "").startswith("TOC")

        if "begin" in field_types and pending_field_start is None:
            pending_field_start = index

        if has_toc_instruction or toc_style:
            in_toc = True
            if pending_field_start is None:
                pending_field_start = index

        if in_toc and pending_field_start is not None:
            for paragraph_index in range(pending_field_start, index + 1):
                toc_indices.add(paragraph_index)

        if "end" in field_types and in_toc:
            in_toc = False
            pending_field_start = None
        elif "end" in field_types and pending_field_start is not None:
            pending_field_start = None

    return toc_indices


def classify_body(document_root: ET.Element | None) -> dict:
    if document_root is None:
        return {
            "paragraph_count": 0,
            "section_count": 0,
            "headings": [],
            "anchor_candidates": [],
            "replace_range_candidates": [],
            "body_regions": {},
            "preview": [],
        }

    body = document_root.find("w:body", WORD_NAMESPACE)
    if body is None:
        return {
            "paragraph_count": 0,
            "section_count": 0,
            "headings": [],
            "anchor_candidates": [],
            "replace_range_candidates": [],
            "body_regions": {},
            "preview": [],
        }

    paragraphs = body.findall("w:p", WORD_NAMESPACE)
    toc_paragraph_indices = find_toc_paragraph_indices(paragraphs)
    headings: list[dict] = []
    anchor_candidates: list[dict] = []
    preview: list[dict] = []
    first_heading_index: int | None = None

    for index, paragraph in enumerate(paragraphs):
        text = paragraph_text(paragraph)
        style = paragraph_style(paragraph)
        normalized = normalize_text(text)
        is_heading = looks_like_heading_style(style) or normalized.startswith("CHUONG ")

        if text and len(preview) < 12:
            preview.append({"paragraph_index": index, "style": style, "text": text[:160]})

        if is_heading and text:
            entry = {"paragraph_index": index, "style": style, "text": text}
            headings.append(entry)
            anchor_candidates.append(entry)
            if first_heading_index is None and index not in toc_paragraph_indices:
                first_heading_index = index

    if first_heading_index is None and headings:
        first_heading_index = headings[0]["paragraph_index"]

    if toc_paragraph_indices and first_heading_index is not None and first_heading_index <= max(toc_paragraph_indices):
        first_heading_index = max(toc_paragraph_indices) + 1

    last_paragraph_index: int | None = None
    for index in range(len(paragraphs) - 1, -1, -1):
        paragraph = paragraphs[index]
        has_section_properties = paragraph.find("w:pPr/w:sectPr", WORD_NAMESPACE) is not None
        if has_section_properties:
            continue
        if paragraph_text(paragraph).strip() or paragraph.findall(".//w:drawing", WORD_NAMESPACE):
            last_paragraph_index = index
            break

    replace_candidates: list[dict] = []
    if first_heading_index is not None and last_paragraph_index is not None and first_heading_index <= last_paragraph_index:
        replace_candidates.append(
            {
                "name": "after-front-matter-to-end-of-main-story",
                "status": "resolved",
                "paragraph_start_index": first_heading_index,
                "paragraph_end_index": last_paragraph_index,
                "preserves_front_matter": first_heading_index > 0,
            }
        )
    else:
        replace_candidates.append(
            {
                "name": "after-front-matter-to-end-of-main-story",
                "status": "unresolved",
                "paragraph_start_index": None,
                "paragraph_end_index": None,
                "preserves_front_matter": False,
            }
        )

    body = document_root.find("w:body", WORD_NAMESPACE)
    body_sectpr_count = len(body.findall("w:sectPr", WORD_NAMESPACE)) if body is not None else 0
    return {
        "paragraph_count": len(paragraphs),
        "section_count": len(document_root.findall(".//w:sectPr", WORD_NAMESPACE)),
        "body_section_count": body_sectpr_count,
        "headings": headings,
        "anchor_candidates": anchor_candidates,
        "replace_range_candidates": replace_candidates,
        "body_regions": {
            "front_matter_end_paragraph_index": first_heading_index - 1 if first_heading_index not in (None, 0) else None,
            "main_content_start_paragraph_index": first_heading_index,
            "main_content_end_paragraph_index": last_paragraph_index,
            "toc_end_paragraph_index": max(toc_paragraph_indices) if toc_paragraph_indices else None,
        },
        "toc_paragraph_indices": sorted(toc_paragraph_indices),
        "preview": preview,
    }


def detect_preserve_parts(field_codes: list[str], header_footer: dict, document_profile: dict) -> list[str]:
    preserve = ["styles-and-numbering", "section-breaks"]
    if header_footer["headers"] or header_footer["footers"]:
        preserve.append("headers-footers")

    normalized_fields = [normalize_text(code) for code in field_codes]
    if any(" TOC " in f" {code} " or code.startswith("TOC") for code in normalized_fields):
        preserve.append("toc")
    if any("FIGURE" in code for code in normalized_fields):
        preserve.append("list-of-figures")
    if any("TABLE" in code for code in normalized_fields):
        preserve.append("list-of-tables")
    if document_profile.get("section_count", 0) > 0:
        preserve.append("page-setup")

    return sorted(set(preserve))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập profile ngắn cho template DOCX.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    template_file = Path(args.template_file)
    run_dir = Path(args.run_dir)

    styles_root = read_xml_from_docx(template_file, "word/styles.xml")
    numbering_root = read_xml_from_docx(template_file, "word/numbering.xml")
    document_root = read_xml_from_docx(template_file, "word/document.xml")
    header_footer = detect_header_footer_members(template_file)
    field_codes = extract_field_codes(document_root)
    document_profile = classify_body(document_root)

    style_catalog = extract_style_catalog(styles_root)
    payload = {
        "template_file": str(template_file),
        "style_names": extract_style_names(styles_root),
        "style_catalog": style_catalog,
        "style_numbering": extract_style_numbering(style_catalog),
        "has_numbering": numbering_root is not None,
        "has_document_xml": document_root is not None,
        "header_count": len(header_footer["headers"]),
        "footer_count": len(header_footer["footers"]),
        "header_members": header_footer["headers"],
        "footer_members": header_footer["footers"],
        "field_codes": field_codes,
        "preserve_defaults": detect_preserve_parts(field_codes, header_footer, document_profile),
        "document_profile": document_profile,
    }

    write_json(run_dir / "template_profile.json", payload)


if __name__ == "__main__":
    main()