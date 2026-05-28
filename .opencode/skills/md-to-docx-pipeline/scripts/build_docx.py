from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
import re
import unicodedata
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
ET.register_namespace("w", WORD_NS)
WORD_NAMESPACE = {"w": WORD_NS}


def qname(tag: str) -> str:
    return f"{{{WORD_NS}}}{tag}"


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


def _extract_root_tag(xml_text: str) -> str | None:
    # DOCX part usually starts with <w:document ...>. We only need the opening tag.
    match = re.search(r"<[^>]*?document\b[^>]*?>", xml_text)
    return None if match is None else match.group(0)


def _extract_xmlns_decls(root_tag: str) -> dict[str, str]:
    # Capture xmlns:prefix="uri" declarations from the root element.
    decls: dict[str, str] = {}
    for prefix, uri in re.findall(r"\sxmlns:([A-Za-z0-9_\-]+)=\"([^\"]+)\"", root_tag):
        decls[prefix] = uri
    return decls


def _inject_missing_root_xmlns(original_xml: bytes, new_xml: bytes) -> bytes:
    """Preserve template root xmlns declarations.

    ElementTree tends to drop unused xmlns declarations when serializing.
    However, template root may contain mc:Ignorable listing prefixes (w14/w15/w16...)
    which must still be declared to keep validators happy.
    """

    try:
        original_text = original_xml.decode("utf-8")
        new_text = new_xml.decode("utf-8")
    except UnicodeDecodeError:
        # Fallback: do not attempt to patch if encoding is unexpected.
        return new_xml

    original_root = _extract_root_tag(original_text)
    new_root = _extract_root_tag(new_text)
    if original_root is None or new_root is None:
        return new_xml

    original_decls = _extract_xmlns_decls(original_root)
    if not original_decls:
        return new_xml

    patched_root = new_root
    for prefix, uri in original_decls.items():
        needle = f"xmlns:{prefix}=\""
        if needle in patched_root:
            continue
        patched_root = patched_root[:-1] + f" xmlns:{prefix}=\"{uri}\"" + ">"

    if patched_root == new_root:
        return new_xml
    return new_text.replace(new_root, patched_root, 1).encode("utf-8")


def make_element(tag: str) -> ET.Element:
    return ET.Element(qname(tag))


def paragraph_text(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(".//w:t", WORD_NAMESPACE)).strip()


def paragraph_style_id(paragraph: ET.Element) -> str | None:
    style = paragraph.find("w:pPr/w:pStyle", WORD_NAMESPACE)
    if style is None:
        return None
    return style.attrib.get(qname("val"))


def paragraph_bookmarks(paragraph: ET.Element) -> list[dict]:
    bookmarks: list[dict] = []
    for bookmark in paragraph.findall("w:bookmarkStart", WORD_NAMESPACE):
        name = bookmark.attrib.get(qname("name"))
        bookmark_id = bookmark.attrib.get(qname("id"))
        if not name or bookmark_id is None:
            continue
        bookmarks.append({"name": name, "id": bookmark_id})
    return bookmarks


def looks_like_heading_paragraph(paragraph: ET.Element) -> bool:
    style_id = paragraph_style_id(paragraph)
    if style_id and style_id.lower().startswith("heading"):
        return True
    return normalize_text(paragraph_text(paragraph)).startswith("CHUONG ")


def collect_heading_bookmarks(children: list[ET.Element]) -> dict[str, list[dict]]:
    bookmark_map: dict[str, list[dict]] = {}

    for child in children:
        if child.tag != qname("p") or not looks_like_heading_paragraph(child):
            continue

        text = paragraph_text(child)
        bookmarks = paragraph_bookmarks(child)
        if not text or not bookmarks:
            continue

        bookmark_map[normalize_heading_text(text)] = bookmarks

    return bookmark_map


def mark_document_fields_dirty(document_root: ET.Element) -> int:
    dirty_count = 0

    for field in document_root.findall(".//w:fldSimple", WORD_NAMESPACE):
        field.set(qname("dirty"), "true")
        dirty_count += 1

    for field in document_root.findall(".//w:fldChar", WORD_NAMESPACE):
        if field.attrib.get(qname("fldCharType")) != "begin":
            continue
        field.set(qname("dirty"), "true")
        dirty_count += 1

    return dirty_count


def enable_update_fields_on_open(settings_xml: bytes) -> bytes:
    settings_root = ET.fromstring(settings_xml)
    update_fields = settings_root.find(qname("updateFields"))
    if update_fields is None:
        update_fields = make_element("updateFields")
        settings_root.append(update_fields)

    update_fields.set(qname("val"), "true")

    serialized = ET.tostring(settings_root, encoding="utf-8", xml_declaration=False)
    return _inject_missing_root_xmlns(settings_xml, serialized)


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


def style_numbering(template_profile: dict, style_id: str) -> dict | None:
    numbering = template_profile.get("style_numbering", {}).get(style_id)
    if isinstance(numbering, dict) and numbering.get("numId") is not None:
        return numbering
    return None


def make_run(text_value: str, bold: bool = False, italic: bool = False, code: bool = False) -> ET.Element:
    run = make_element("r")
    if bold or italic or code:
        run_properties = make_element("rPr")
        if bold:
            run_properties.append(make_element("b"))
        if italic:
            run_properties.append(make_element("i"))
        if code:
            run_fonts = make_element("rFonts")
            run_fonts.set(qname("ascii"), "Courier New")
            run_fonts.set(qname("hAnsi"), "Courier New")
            run_properties.append(run_fonts)
        run.append(run_properties)

    text = make_element("t")
    text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    text.text = text_value
    run.append(text)
    return run


def block_runs(block: dict) -> list[dict]:
    runs = block.get("runs")
    if isinstance(runs, list) and runs:
        return [run for run in runs if str(run.get("text", ""))]
    fallback = block_text(block)
    return [] if not fallback else [{"text": fallback}]


def make_paragraph(block: dict, style_map: dict, template_profile: dict, bookmarks: list[dict] | None = None) -> ET.Element:
    paragraph = make_element("p")
    paragraph_properties = make_element("pPr")
    paragraph.append(paragraph_properties)

    paragraph_style_name = paragraph_style(block, style_map)
    style_element = make_element("pStyle")
    style_element.set(qname("val"), paragraph_style_name)
    paragraph_properties.append(style_element)

    numbering = style_numbering(template_profile, paragraph_style_name)
    if numbering is not None and block.get("type") == "reference":
        num_properties = make_element("numPr")
        level_element = make_element("ilvl")
        level_element.set(qname("val"), str(numbering.get("ilvl", 0)))
        num_id_element = make_element("numId")
        num_id_element.set(qname("val"), str(numbering["numId"]))
        num_properties.append(level_element)
        num_properties.append(num_id_element)
        paragraph_properties.append(num_properties)

    if block.get("type") == "list_item" and block.get("level", 0) > 0:
        indentation = make_element("ind")
        indentation.set(qname("left"), str(720 * int(block.get("level", 0))))
        paragraph_properties.append(indentation)

    bookmark_ids: list[str] = []
    for bookmark in bookmarks or []:
        bookmark_start = make_element("bookmarkStart")
        bookmark_start.set(qname("id"), str(bookmark["id"]))
        bookmark_start.set(qname("name"), str(bookmark["name"]))
        paragraph.append(bookmark_start)
        bookmark_ids.append(str(bookmark["id"]))

    for run_info in block_runs(block):
        paragraph.append(
            make_run(
                str(run_info.get("text", "")),
                bold=bool(run_info.get("bold")),
                italic=bool(run_info.get("italic")),
                code=bool(run_info.get("code")),
            )
        )

    if not list(paragraph.findall(qname("r"))):
        paragraph.append(make_run(block_text(block)))

    for bookmark_id in bookmark_ids:
        bookmark_end = make_element("bookmarkEnd")
        bookmark_end.set(qname("id"), bookmark_id)
        paragraph.append(bookmark_end)

    return paragraph


def paragraph_index_to_body_child_range(body: ET.Element, start_paragraph_index: int, end_paragraph_index: int) -> tuple[int | None, int | None]:
    paragraph_counter = -1
    start_child_index: int | None = None
    end_child_index: int | None = None

    for child_index, child in enumerate(list(body)):
        if child.tag == qname("sectPr"):
            continue
        if child.tag != qname("p"):
            continue

        paragraph_counter += 1
        if paragraph_counter == start_paragraph_index and start_child_index is None:
            start_child_index = child_index
        if paragraph_counter == end_paragraph_index:
            end_child_index = child_index
            break

    return start_child_index, end_child_index


def replace_body_range(template_file: Path, target_file: Path, blocks: list[dict], style_map: dict, replace_range: dict, template_profile: dict) -> dict:
    shutil.copy2(template_file, target_file)

    with zipfile.ZipFile(target_file, "r") as archive:
        document_xml = archive.read("word/document.xml")
        settings_xml = archive.read("word/settings.xml") if "word/settings.xml" in archive.namelist() else None

    tree = ET.fromstring(document_xml)
    body = tree.find(qname("body"))
    if body is None:
        raise ValueError("Không tìm thấy w:body trong tài liệu đích.")

    start_index = replace_range.get("paragraph_start_index")
    end_index = replace_range.get("paragraph_end_index")
    if start_index is None or end_index is None:
        raise ValueError("replace_range không có chỉ số paragraph hợp lệ.")

    body_children_before = len(list(body))
    start_child_index, end_child_index = paragraph_index_to_body_child_range(body, int(start_index), int(end_index))
    if start_child_index is None or end_child_index is None or start_child_index > end_child_index:
        raise ValueError("Không ánh xạ được replace_range sang direct child của w:body.")

    existing_children = list(body)
    heading_bookmarks = collect_heading_bookmarks(existing_children[start_child_index:end_child_index + 1])
    for child in existing_children[start_child_index:end_child_index + 1]:
        body.remove(child)

    insertion_index = start_child_index
    inserted = 0
    for block in blocks:
        text = block_text(block)
        if not text:
            continue
        bookmarks = None
        if block.get("type") == "heading":
            bookmarks = heading_bookmarks.get(normalize_heading_text(text))
        body.insert(insertion_index, make_paragraph(block, style_map, template_profile, bookmarks=bookmarks))
        insertion_index += 1
        inserted += 1

    dirty_field_count = mark_document_fields_dirty(tree)
    document_bytes = ET.tostring(tree, encoding="utf-8", xml_declaration=False)
    document_bytes = _inject_missing_root_xmlns(document_xml, document_bytes)
    settings_bytes = None if settings_xml is None else enable_update_fields_on_open(settings_xml)
    temporary_target = target_file.with_suffix(target_file.suffix + ".tmp")

    with zipfile.ZipFile(target_file, "r") as source_archive:
        with zipfile.ZipFile(temporary_target, "w", zipfile.ZIP_DEFLATED) as target_archive:
            for item in source_archive.infolist():
                if item.filename == "word/document.xml":
                    target_archive.writestr(item, document_bytes)
                elif item.filename == "word/settings.xml" and settings_bytes is not None:
                    target_archive.writestr(item, settings_bytes)
                else:
                    target_archive.writestr(item, source_archive.read(item.filename))

    temporary_target.replace(target_file)

    return {
        "body_children_before": body_children_before,
        "body_children_after": len(list(body)),
        "replaced_child_count": end_child_index - start_child_index + 1,
        "inserted_block_count": inserted,
        "body_replaced": inserted > 0,
        "dirty_field_count": dirty_field_count,
        "update_fields_on_open": settings_bytes is not None,
        "field_refresh_strategy": "update-fields-on-open" if settings_bytes is not None else "none",
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

    if plan.get("mode") != "preserve-template-scaffold":
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Script build hiện chỉ cho phép mode preserve-template-scaffold trong workflow an toàn mới.",
            "body_replaced": False,
        }
        run_state["status"] = "blocked"
    elif resolved_range is None:
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Không resolve được replace_ranges nên build bị chặn để tránh làm mất scaffold của template.",
            "body_replaced": False,
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
            "replace_range": resolved_range,
            "preserve": plan.get("preserve", []),
            "style_map": plan.get("style_map", {}),
            "template_header_count": template_profile.get("header_count", 0),
            "template_footer_count": template_profile.get("footer_count", 0),
            **replacement_stats,
            "message": "Đã thay vùng nội dung chính theo bounded range và giữ scaffold của template ở ngoài phạm vi thay.",
        }
        run_state["status"] = "built"

    run_state["artifacts"]["build_report"] = str(run_dir / "build_report.json")

    write_json(run_dir / "build_report.json", build_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
