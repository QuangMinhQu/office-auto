from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def qname(tag: str) -> str:
    return f"{{{WORD_NS}}}{tag}"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_element(tag: str) -> ET.Element:
    return ET.Element(qname(tag))


def paragraph_style(block: dict, style_map: dict) -> str:
    if block.get("type") == "heading":
        level = int(block.get("level", 1))
        if level <= 1:
            return style_map.get("h1", "Heading1")
        if level == 2:
            return style_map.get("h2", "Heading2")
        return style_map.get("h3", "Heading3")
    if block.get("type") == "list_item":
        return style_map.get("list", style_map.get("body", "Normal"))
    return style_map.get("body", "Normal")


def block_text(block: dict) -> str:
    if block.get("type") == "table_row":
        return " | ".join(block.get("cells", []))
    if block.get("type") == "list_item":
        if block.get("ordered"):
            return f"{block.get('ordinal', 1)}. {block.get('text', '').strip()}"
        return f"• {block.get('text', '').strip()}"
    return str(block.get("text", "")).strip()


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


def make_paragraph(block: dict, style_map: dict) -> ET.Element:
    paragraph = make_element("p")
    paragraph_properties = make_element("pPr")
    paragraph.append(paragraph_properties)

    paragraph_style_name = paragraph_style(block, style_map)
    style_element = make_element("pStyle")
    style_element.set(qname("val"), paragraph_style_name)
    paragraph_properties.append(style_element)

    if block.get("type") == "list_item" and block.get("level", 0) > 0:
        indentation = make_element("ind")
        indentation.set(qname("left"), str(720 * int(block.get("level", 0))))
        paragraph_properties.append(indentation)

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


def replace_body_range(template_file: Path, target_file: Path, blocks: list[dict], style_map: dict, replace_range: dict) -> dict:
    shutil.copy2(template_file, target_file)

    with zipfile.ZipFile(target_file, "r") as archive:
        document_xml = archive.read("word/document.xml")

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
    for child in existing_children[start_child_index:end_child_index + 1]:
        body.remove(child)

    insertion_index = start_child_index
    inserted = 0
    for block in blocks:
        text = block_text(block)
        if not text:
            continue
        body.insert(insertion_index, make_paragraph(block, style_map))
        insertion_index += 1
        inserted += 1

    document_bytes = ET.tostring(tree, encoding="utf-8", xml_declaration=False)
    temporary_target = target_file.with_suffix(target_file.suffix + ".tmp")

    with zipfile.ZipFile(target_file, "r") as source_archive:
        with zipfile.ZipFile(temporary_target, "w", zipfile.ZIP_DEFLATED) as target_archive:
            for item in source_archive.infolist():
                if item.filename == "word/document.xml":
                    target_archive.writestr(item, document_bytes)
                else:
                    target_archive.writestr(item, source_archive.read(item.filename))

    temporary_target.replace(target_file)

    return {
        "body_children_before": body_children_before,
        "body_children_after": len(list(body)),
        "replaced_child_count": end_child_index - start_child_index + 1,
        "inserted_block_count": inserted,
        "body_replaced": inserted > 0,
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