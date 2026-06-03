#!/usr/bin/env python3
"""docx_inspect.py — raw dump tool, zero heuristics, zero interpretation.

Schema matches issue.md spec exactly:
  - page_layout_raw: raw twips, no conversion
  - styles_raw: raw pt values (None = inherited), outline_level_xml raw
  - paragraph_sample: first N paragraphs, raw text/style/paraId
  - toc_entries_raw: raw TOC entries from document.xml
  - front_matter_boundary: last paraId before body content zone

LLM receives the raw dump and does ALL reasoning:
  - style inheritance tree resolution
  - spacing interpretation (None = inherited)
  - heading detection from outlineLvl raw values
  - template type classification
  - markdown → style mapping

Usage:
    python docx_inspect.py --template-file <path> --run-dir <path>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import zipfile
from pathlib import Path
from typing import Any

from lxml import etree


# Word XML namespace
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.openxmlformats.org/markup-compatibility/2006"


def timestamp_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def dump_styles(doc: Any) -> list[dict]:
    """Layer 1: Style catalog — RAW, no resolve, no classify.

    For each style, return:
      - name, style_id, base_style name (or None)
      - Raw Pt values (None = inherited, LLM self-computes)
      - outline_level_xml: raw w:outlineLvl @w:val (0-9 = heading levels 1-10)
      - No "heading_level", no "resolved_spacing", no "is_heading"
    """
    from docx.oxml.ns import qn

    styles_raw: list[dict] = []
    for style in doc.styles:
        # Only process PARAGRAPH styles — CHARACTER/TABLE/NUMBERING don't have paragraph_format
        if style.type.name != "PARAGRAPH":
            continue
        fmt = style.paragraph_format
        entry: dict[str, Any] = {
            "name": style.name,
            "style_id": style.style_id,
            "base_style": style.base_style.name if style.base_style else None,
        }
        # Raw Pt values — None means inherited from base style
        if fmt.space_before is not None:
            entry["space_before_pt"] = float(fmt.space_before.pt)
        else:
            entry["space_before_pt"] = None
        if fmt.space_after is not None:
            entry["space_after_pt"] = float(fmt.space_after.pt)
        else:
            entry["space_after_pt"] = None

        if fmt.line_spacing is not None:
            entry["line_spacing"] = float(fmt.line_spacing)
        else:
            entry["line_spacing"] = None

        line_rule = fmt.line_spacing_rule
        if line_rule is not None:
            entry["line_spacing_rule"] = str(line_rule)
        else:
            entry["line_spacing_rule"] = None

        if fmt.left_indent is not None:
            entry["left_indent_pt"] = float(fmt.left_indent.pt)
        else:
            entry["left_indent_pt"] = None

        if fmt.first_line_indent is not None:
            entry["first_line_indent_pt"] = float(fmt.first_line_indent.pt)
        else:
            entry["first_line_indent_pt"] = None

        # Run-level raw style info (no resolve)
        run_info = {}
        if style.font.name is not None:
            run_info["font_name"] = style.font.name
        else:
            run_info["font_name"] = None
        if style.font.size is not None:
            run_info["font_size_pt"] = float(style.font.size.pt)
        else:
            run_info["font_size_pt"] = None
        run_info["font_bold"] = style.font.bold
        run_info["font_italic"] = style.font.italic
        if style.font.color is not None and style.font.color.rgb is not None:
            run_info["font_color_hex"] = str(style.font.color.rgb)
        else:
            run_info["font_color_hex"] = None
        entry["run"] = run_info

        # outline_level_xml: raw w:outlineLvl @w:val from styles.xml
        # 0-9 = heading levels 1-10, None = not a heading
        outline_elem = style._element.find(qn('w:outlineLvl'))
        if outline_elem is not None:
            entry["outline_level_xml"] = outline_elem.get(qn('w:val'))
        else:
            entry["outline_level_xml"] = None

        styles_raw.append(entry)

    return styles_raw


def dump_page_layout(template_path: Path) -> dict[str, str | None]:
    """Layer 2: Page layout — RAW XML values (twips).

    Returns raw twip values from <w:sectPr>/<w:pgSz>/<w:pgMar>.
    LLM converts: twips / 1440 = inches, / 72 = points.
    """
    try:
        with zipfile.ZipFile(template_path) as z:
            xml_doc = etree.fromstring(z.read("word/document.xml"))
    except Exception as exc:
        return {"error": f"Cannot read document.xml: {exc}"}

    sect = xml_doc.find(f".//{{{W}}}sectPr")
    if sect is None:
        return {"error": "No <w:sectPr> found in document.xml"}

    pg_sz = sect.find(f"{{{W}}}pgSz")
    pg_mar = sect.find(f"{{{W}}}pgMar")

    result: dict[str, str | None] = {}

    if pg_sz is not None:
        result["paper_w_twip"] = pg_sz.get(f"{{{W}}}w")
        result["paper_h_twip"] = pg_sz.get(f"{{{W}}}h")
        result["paper_orientation"] = pg_sz.get(f"{{{W}}}orient", "portrait")
    else:
        result["paper_w_twip"] = None
        result["paper_h_twip"] = None
        result["paper_orientation"] = "portrait"

    if pg_mar is not None:
        result["margin_top"] = pg_mar.get(f"{{{W}}}top")
        result["margin_bottom"] = pg_mar.get(f"{{{W}}}bottom")
        result["margin_left"] = pg_mar.get(f"{{{W}}}left")
        result["margin_right"] = pg_mar.get(f"{{{W}}}right")
    else:
        result["margin_top"] = None
        result["margin_bottom"] = None
        result["margin_left"] = None
        result["margin_right"] = None

    return result


def dump_paragraph_sample(doc: Any, max_count: int = 30) -> list[dict]:
    """Layer 3: Sample paragraphs — LLM self-identifies structure.

    Returns raw text + style + paraId. No heading classification.
    Default max_count=30 per issue.md spec.
    """
    from docx.oxml.ns import qn

    # Multiple namespaces that may contain paraId
    PARA_ID_NAMESPACES = [
        qn('w:paraId'),
        qn('w14:paraId'),
        '{http://schemas.microsoft.com/office/word/2010/wordml}paraId',
    ]

    sample_paras: list[dict] = []
    for i, para in enumerate(doc.paragraphs[:max_count]):
        element = para._element

        # Try multiple namespaces for paraId
        para_id = None
        for ns_qn in PARA_ID_NAMESPACES:
            para_id = element.get(ns_qn)
            if para_id:
                break

        entry: dict[str, Any] = {
            "index": i,
            "text": para.text,
            "style_name": para.style.name if para.style else None,
            "style_id": para.style.style_id if para.style else None,
        }
        if para_id is not None:
            entry["para_id"] = para_id

        fmt = para.paragraph_format
        if fmt.space_before is not None:
            entry["space_before_pt"] = float(fmt.space_before.pt)
        else:
            entry["space_before_pt"] = None
        if fmt.space_after is not None:
            entry["space_after_pt"] = float(fmt.space_after.pt)
        else:
            entry["space_after_pt"] = None
        if fmt.left_indent is not None:
            entry["left_indent_pt"] = float(fmt.left_indent.pt)
        else:
            entry["left_indent_pt"] = None
        if fmt.first_line_indent is not None:
            entry["first_line_indent_pt"] = float(fmt.first_line_indent.pt)
        else:
            entry["first_line_indent_pt"] = None

        # Alignment raw (no interpretation)
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        align = fmt.alignment
        if align is not None:
            entry["align"] = str(align)
        else:
            entry["align"] = None

        entry["is_empty"] = not para.text.strip()
        sample_paras.append(entry)

    return sample_paras


def dump_all_para_ids(doc: Any) -> list[dict]:
    """Layer 3b: ALL paragraph paraIds — full document, no sampling.

    Returns paraId + text preview (first 80 chars) for every paragraph.
    Used by validator to check anchors against the FULL template,
    not just the first 30 paragraphs.

    This is the ground truth for anchor validation.
    """
    from docx.oxml.ns import qn

    PARA_ID_NAMESPACES = [
        qn('w:paraId'),
        qn('w14:paraId'),
        '{http://schemas.microsoft.com/office/word/2010/wordml}paraId',
    ]

    all_paras: list[dict] = []
    for i, para in enumerate(doc.paragraphs):
        element = para._element

        para_id = None
        for ns_qn in PARA_ID_NAMESPACES:
            para_id = element.get(ns_qn)
            if para_id:
                break

        if para_id is None:
            continue

        entry: dict[str, Any] = {
            "index": i,
            "para_id": para_id,
            "text_preview": (para.text[:80] if para.text else ""),
            "style_name": para.style.name if para.style else None,
        }
        all_paras.append(entry)

    return all_paras


def dump_toc_entries(template_path: Path) -> list[dict]:
    """Layer 4: Raw TOC entries from document.xml.

    Extracts TOC fields with their anchor bookmarks and levels.
    No interpretation — raw values only.
    """
    try:
        with zipfile.ZipFile(template_path) as z:
            xml_doc = etree.fromstring(z.read("word/document.xml"))
    except Exception as exc:
        return [{"error": f"Cannot read document.xml: {exc}"}]

    toc_entries: list[dict] = []

    # Find all TOC fields (fldChar with fldCharType="begin")
    for fld_char in xml_doc.findall(f".//{{{W}}}fldChar"):
        fld_char_type = fld_char.get(f"{{{W}}}fldCharType")
        if fld_char_type != "begin":
            continue

        # Get the associated instruction
        instr_text = fld_char.getparent()
        if instr_text is None:
            continue
        parent = instr_text.getparent()
        if parent is None:
            continue

        # Find rInstr (instruction run)
        for r in parent.findall(f"{{{W}}}r"):
            for instr in r.findall(f"{{{W}}}instrText"):
                instruction = instr.text or ""
                if "TOC" not in instruction.upper():
                    continue

                # Extract level from instruction
                level_match = instruction.split(" \\l ")
                level = int(level_match[1].strip()) if len(level_match) > 1 else 1

                # Find bookmark anchor for this TOC entry
                bookmark_anchor = None
                # Look for _Toc bookmarks in the same paragraph
                para = fld_char
                while para is not None and etree.QName(para.tag).localname != "p":
                    para = para.getparent()
                if para is not None:
                    for bookmark_start in para.findall(f".//{{{W}}}bookmark"):
                        name = bookmark_start.get(f"{{{W}}}name")
                        if name and name.startswith("_Toc"):
                            bookmark_anchor = name
                            break

                # Extract text content
                text = ""
                for t in para.findall(f".//{{{W}}}t") if para is not None else []:
                    if t.text:
                        text += t.text[:200]

                if text or bookmark_anchor:
                    toc_entries.append({
                        "text": text.strip(),
                        "bookmark_anchor": bookmark_anchor,
                        "level": level,
                    })

    return toc_entries


def detect_front_matter_boundary(paragraph_sample: list[dict]) -> dict[str, Any]:
    """Layer 5: Detect front matter boundary.

    Heuristic: front matter = content before first body paragraph.
    Body paragraphs typically have "Body Text" or "Normal" style and
    are not headings (outline_level_xml is None or paragraph has no heading style).

    Returns last paraId before body content zone.
    """
    # Find first paragraph that looks like body text
    # (not a heading, has substantial text, common body style)
    body_start_index = len(paragraph_sample)
    for i, para in enumerate(paragraph_sample):
        style_name = (para.get("style_name") or "").lower()
        text = para.get("text", "")
        is_heading = any(kw in style_name for kw in ["heading", "chương", "điều", "mục", "phan"])

        if not is_heading and len(text.strip()) > 20:
            body_start_index = i
            break

    # Last paraId before body
    if body_start_index > 0:
        last_before_body = paragraph_sample[body_start_index - 1]
        return {
            "last_para_id": last_before_body.get("para_id"),
            "body_start_index": body_start_index,
            "description": f"last paragraph before body content zone (body starts at index {body_start_index})",
        }

    return {
        "last_para_id": None,
        "body_start_index": body_start_index,
        "description": "no clear front matter boundary detected",
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="docx_inspect: raw dump tool — zero heuristics, zero interpretation."
    )
    parser.add_argument("--template-file", required=True, help="Path to template .docx")
    parser.add_argument("--run-dir", required=True, help="Run directory for output artifacts")
    parser.add_argument(
        "--top-n-styles", type=int, default=None,
        help="Only dump top N styles (by appearance count in sample). "
             "Useful for large templates. This is a FILTERING parameter, not classification."
    )
    parser.add_argument(
        "--max-paragraphs", type=int, default=30,
        help="Number of paragraphs to sample (default: 30 per issue.md spec)"
    )
    args = parser.parse_args()

    template_path = Path(args.template_file)
    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    # Import python-docx here (after validation)
    from docx import Document

    doc = Document(str(template_path))

    print(f"[docx_inspect] Reading: {template_path}")

    # Layer 1: Styles — RAW
    print("[docx_inspect] Layer 1: styles_raw ...")
    styles_raw = dump_styles(doc)
    if args.top_n_styles and args.top_n_styles > 0:
        # Count style usage in paragraphs
        style_counts: dict[str, int] = {}
        for para in doc.paragraphs:
            sname = para.style.name if para.style else "None"
            style_counts[sname] = style_counts.get(sname, 0) + 1
        most_common = sorted(style_counts.items(), key=lambda x: -x[1])[:args.top_n_styles]
        keep_names = {name for name, _ in most_common}
        styles_raw = [s for s in styles_raw if s["name"] in keep_names]
    Path(run_dir, "docx_inspect_styles_raw.json").write_text(
        json.dumps(styles_raw, ensure_ascii=False, indent=2)
    )
    print(f"[docx_inspect]   → {len(styles_raw)} styles written")

    # Layer 2: Page layout — RAW twips
    print("[docx_inspect] Layer 2: page_layout_raw ...")
    page_layout = dump_page_layout(template_path)
    Path(run_dir, "docx_inspect_page_layout_raw.json").write_text(
        json.dumps(page_layout, ensure_ascii=False, indent=2)
    )
    print("[docx_inspect]   → page_layout written")

    # Layer 3: Sample paragraphs — RAW (default 30 per spec)
    print(f"[docx_inspect] Layer 3: paragraph_sample (max={args.max_paragraphs}) ...")
    para_sample = dump_paragraph_sample(doc, max_count=args.max_paragraphs)
    Path(run_dir, "docx_inspect_paragraph_sample.json").write_text(
        json.dumps(para_sample, ensure_ascii=False, indent=2)
    )
    print(f"[docx_inspect]   → {len(para_sample)} paragraphs written")

    # Layer 4: TOC entries — RAW
    print("[docx_inspect] Layer 4: toc_entries_raw ...")
    toc_entries = dump_toc_entries(template_path)
    Path(run_dir, "docx_inspect_toc_entries_raw.json").write_text(
        json.dumps(toc_entries, ensure_ascii=False, indent=2)
    )
    print(f"[docx_inspect]   → {len(toc_entries)} TOC entries written")

    # Layer 3b: ALL paragraph paraIds — full document (for validator)
    print("[docx_inspect] Layer 3b: all_para_ids (full document) ...")
    all_para_ids = dump_all_para_ids(doc)
    Path(run_dir, "docx_inspect_all_para_ids.json").write_text(
        json.dumps(all_para_ids, ensure_ascii=False, indent=2)
    )
    print(f"[docx_inspect]   → {len(all_para_ids)} total paragraphs written")

    # Layer 5: Front matter boundary
    print("[docx_inspect] Layer 5: front_matter_boundary ...")
    front_matter = detect_front_matter_boundary(para_sample)
    Path(run_dir, "docx_inspect_front_matter_boundary.json").write_text(
        json.dumps(front_matter, ensure_ascii=False, indent=2)
    )
    print(f"[docx_inspect]   → front_matter_boundary: {front_matter.get('description')}")

    # Build combined output matching issue.md schema exactly
    combined = {
        "source_file": str(template_path.resolve()),
        "extraction_timestamp": timestamp_utc(),
        "page_layout_raw": {
            "paper_w_twip": page_layout.get("paper_w_twip"),
            "paper_h_twip": page_layout.get("paper_h_twip"),
            "margin_top": page_layout.get("margin_top"),
            "margin_bottom": page_layout.get("margin_bottom"),
            "margin_left": page_layout.get("margin_left"),
            "margin_right": page_layout.get("margin_right"),
            "orientation": page_layout.get("paper_orientation", "portrait"),
        },
        "styles_raw": styles_raw,
        "paragraph_sample": para_sample,
        "all_para_ids": all_para_ids,
        "toc_entries_raw": toc_entries,
        "front_matter_boundary": front_matter,
    }
    Path(run_dir, "docx_inspect_output.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2)
    )

    # Also write individual layer files for debugging
    summary = {
        "template_file": str(template_path.resolve()),
        "extraction_timestamp": timestamp_utc(),
        "top_n_styles_filter": args.top_n_styles,
        "max_paragraphs": args.max_paragraphs,
        "layer_files": {
            "styles_raw": str(run_dir / "docx_inspect_styles_raw.json"),
            "page_layout_raw": str(run_dir / "docx_inspect_page_layout_raw.json"),
            "paragraph_sample": str(run_dir / "docx_inspect_paragraph_sample.json"),
            "toc_entries_raw": str(run_dir / "docx_inspect_toc_entries_raw.json"),
            "front_matter_boundary": str(run_dir / "docx_inspect_front_matter_boundary.json"),
        },
        "combined_output": str(run_dir / "docx_inspect_output.json"),
    }
    Path(run_dir, "docx_inspect_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2)
    )

    print(f"[docx_inspect] Done. All output in: {run_dir}")
    print("[docx_inspect] NEXT STEP: LLM reads docx_inspect_output.json → reasons → writes execution_ops.json")


if __name__ == "__main__":
    main()
