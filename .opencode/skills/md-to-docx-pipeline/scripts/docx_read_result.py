from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import officecli_query, officecli_view, read_json, write_json


DIRECT_BODY_CHILD_PATTERN = re.compile(r"^/body/(?:p|tbl)(?:\[\d+\]|\[@paraId=[0-9A-Fa-f]+\])$")


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


def paragraph_entry(result: dict) -> dict:
    paragraph_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "text": result.get("text"),
        "style_id": paragraph_format.get("styleId") or paragraph_format.get("style"),
        "style_name": paragraph_format.get("styleName") or result.get("style") or paragraph_format.get("style"),
        "format": paragraph_format,
    }


def toc_entry(result: dict) -> dict:
    toc_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "instruction": toc_format.get("instruction") or result.get("text"),
        "levels": toc_format.get("levels"),
        "hyperlinks": toc_format.get("hyperlinks"),
    }


def field_entry(result: dict) -> dict:
    field_format = result.get("format", {}) or {}
    return {
        "path": result.get("path"),
        "field_type": field_format.get("fieldType"),
        "instruction": field_format.get("instruction") or result.get("text"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Đọc output DOCX thành snapshot cấu trúc/text để LLM review.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--file", required=False)
    parser.add_argument("--output-file", default="result_readback.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    target_file = Path(args.file) if args.file else Path(run_state.get("target_file"))

    outline_view = officecli_view(target_file, "outline") or {}
    stats_view = officecli_view(target_file, "stats") or {}
    text_view = officecli_view(target_file, "text") or {}
    paragraph_results = officecli_query(target_file, "paragraph")
    toc_results = officecli_query(target_file, "toc")
    field_results = officecli_query(target_file, "field")

    payload = {
        "target_file": str(target_file),
        "outline_snapshot": outline_view,
        "stats_snapshot": stats_view,
        "body_children": direct_body_children(text_view),
        "body_paragraphs": [
            paragraph_entry(result)
            for result in paragraph_results
            if str(result.get("path", "")).startswith("/body/")
        ],
        "toc_entries": [toc_entry(result) for result in toc_results],
        "field_entries": [field_entry(result) for result in field_results],
    }
    write_json(run_dir / args.output_file, payload)

    run_state.setdefault("artifacts", {})["result_readback"] = str(run_dir / args.output_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()