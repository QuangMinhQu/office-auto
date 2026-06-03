from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from officecli_native import (
    ensure_officecli_available,
    read_json,
    officecli_get,
    officecli_query,
    officecli_view,
    write_json,
)


DIRECT_BODY_CHILD_PATTERN = re.compile(r"^/body/(?:p|tbl)(?:\[\d+\]|\[@paraId=[0-9A-Fa-f]+\])$")


def summarize_tree(tree: Any) -> dict:
    if not isinstance(tree, dict):
        return {}
    return {
        "path": tree.get("path"),
        "type": tree.get("type"),
        "child_count": tree.get("childCount"),
    }


def style_entry(result: dict) -> dict:
    style_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "style_id": style_format.get("id"),
        "name": style_format.get("name") or result.get("text"),
        "type": style_format.get("type"),
        "based_on": style_format.get("basedOn"),
        "custom": style_format.get("customStyle"),
        "default": style_format.get("default"),
        "format": style_format,
    }


def paragraph_entry(result: dict) -> dict:
    paragraph_format = result.get("format", {}) or {}
    bookmarks = []
    for child in result.get("children", []):
        if child.get("type") != "bookmark":
            continue
        bookmark_format = child.get("format", {}) or {}
        if bookmark_format.get("name"):
            bookmarks.append({
                "name": bookmark_format.get("name"),
                "id": bookmark_format.get("id"),
            })
    return {
        "path": result.get("path"),
        "text": result.get("text"),
        "style_id": paragraph_format.get("styleId") or paragraph_format.get("style"),
        "style_name": paragraph_format.get("styleName") or result.get("style") or paragraph_format.get("style"),
        "format": paragraph_format,
        "bookmarks": bookmarks,
    }


def direct_body_children(text_view: dict) -> list[dict]:
    children: list[dict] = []
    for element in (text_view or {}).get("elements", []):
        path = str(element.get("path") or "")
        if not DIRECT_BODY_CHILD_PATTERN.match(path):
            continue
        children.append(
            {
                "path": path,
                "type": element.get("type"),
                "text": element.get("text"),
                "style": element.get("style"),
                "level": element.get("level"),
            }
        )
    return children


def toc_entry(result: dict) -> dict:
    toc_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "instruction": toc_format.get("instruction") or result.get("text"),
        "levels": toc_format.get("levels"),
        "hyperlinks": toc_format.get("hyperlinks"),
        "format": toc_format,
    }


def field_entry(result: dict) -> dict:
    field_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "field_type": field_format.get("fieldType"),
        "instruction": field_format.get("instruction") or result.get("text"),
        "format": field_format,
    }


def body_elements_sample(text_view: dict, *, limit: int = 20) -> list[dict]:
    elements = []
    for element in (text_view or {}).get("elements", []):
        path = str(element.get("path") or "")
        if not path.startswith("/body/"):
            continue
        elements.append(
            {
                "path": path,
                "type": element.get("type"),
                "text": element.get("text"),
                "style": element.get("style"),
                "level": element.get("level"),
            }
        )
        if len(elements) >= limit:
            break
    return elements


def query_sample(results: list[dict], *, limit: int = 20) -> list[dict]:
    sample: list[dict] = []
    for result in results[:limit]:
        sample.append(
            {
                "path": result.get("path"),
                "type": result.get("type"),
                "text": result.get("text"),
                "style": result.get("style"),
                "format": result.get("format", {}),
            }
        )
    return sample


def build_raw_inspection_payload(
    *,
    template_file: Path,
    officecli_version: str,
    outline_view: dict | None,
    stats_view: dict | None,
    text_view: dict | None,
    styles_tree: dict | None,
    numbering_tree: dict | None,
    section_results: list[dict],
    style_results: list[dict],
    paragraph_results: list[dict],
    header_results: list[dict],
    footer_results: list[dict],
    toc_results: list[dict],
    field_results: list[dict],
) -> dict:
    body_paragraph_results = [result for result in paragraph_results if str(result.get("path", "")).startswith("/body/")]
    return {
        "template_file": str(template_file),
        "officecli_version": officecli_version,
        "outline_snapshot": outline_view or {},
        "stats_snapshot": stats_view or {},
        "styles_tree": summarize_tree(styles_tree),
        "numbering_tree": summarize_tree(numbering_tree),
        "counts": {
            "sections": len(section_results),
            "styles": len(style_results),
            "paragraphs": len(paragraph_results),
            "body_paragraphs": len(body_paragraph_results),
            "headers": len(header_results),
            "footers": len(footer_results),
            "tocs": len(toc_results),
            "fields": len(field_results),
        },
        "style_catalog": [style_entry(result) for result in style_results if result.get("type") == "style"],
        "body_children": direct_body_children(text_view or {}),
        "body_paragraphs": [paragraph_entry(result) for result in body_paragraph_results],
        "toc_entries": [toc_entry(result) for result in toc_results],
        "field_entries": [field_entry(result) for result in field_results],
        "body_elements_sample": body_elements_sample(text_view or {}),
        "section_sample": query_sample(section_results),
        "style_sample": query_sample(style_results),
        "paragraph_sample": query_sample(paragraph_results),
        "header_sample": query_sample(header_results),
        "footer_sample": query_sample(footer_results),
        "toc_sample": query_sample(toc_results),
        "field_sample": query_sample(field_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Dump inspection thô của template DOCX không qua heuristic.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output-file", default="template_inspection_raw.json")
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

    payload = build_raw_inspection_payload(
        template_file=template_file,
        officecli_version=officecli_version,
        outline_view=outline_view,
        stats_view=stats_view,
        text_view=text_view,
        styles_tree=styles_tree,
        numbering_tree=numbering_tree,
        section_results=section_results,
        style_results=style_results,
        paragraph_results=paragraph_results,
        header_results=header_results,
        footer_results=footer_results,
        toc_results=toc_results,
        field_results=field_results,
    )
    write_json(run_dir / args.output_file, payload)

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["template_inspection_raw"] = str(run_dir / args.output_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()