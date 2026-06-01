from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import read_json, write_json

from markitdown_support import (
    MarkItDownConversionError,
    MarkItDownDependencyError,
    load_style_map,
    normalize_source_markdown,
)
from parse_markdown import parse_markdown_blocks


def main() -> None:
    parser = argparse.ArgumentParser(description="Trích semantic sample từ tài liệu mẫu thành sample_content.md.")
    parser.add_argument("--sample-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--style-map-file", required=False)
    args = parser.parse_args()

    sample_file = Path(args.sample_file)
    run_dir = Path(args.run_dir)
    style_map_file = Path(args.style_map_file) if args.style_map_file else run_dir / "markitdown_style_map.txt"
    style_map = load_style_map(style_map_file)
    sample_content_file = run_dir / "sample_content.md"
    sample_outline_file = run_dir / "sample_outline.json"
    sample_report_file = run_dir / "sample_content_report.json"
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}

    try:
        markdown_text, summary = normalize_source_markdown(sample_file, style_map=style_map)
    except (MarkItDownDependencyError, MarkItDownConversionError) as exc:
        sample_content_file.unlink(missing_ok=True)
        sample_outline_file.unlink(missing_ok=True)
        run_state.setdefault("artifacts", {}).pop("sample_content", None)
        run_state.setdefault("artifacts", {}).pop("sample_outline", None)
        run_state.setdefault("artifacts", {})["sample_content_report"] = str(sample_report_file)
        write_json(
            sample_report_file,
            {
                "status": "failed",
                "sample_file": str(sample_file),
                "sample_content_file": str(sample_content_file),
                "sample_outline_file": str(sample_outline_file),
                "style_map_file": str(style_map_file) if style_map else None,
                "message": str(exc),
            },
        )
        write_json(run_dir / "run.json", run_state)
        return

    sample_content_file.write_text(markdown_text, encoding="utf-8")

    blocks, outline, metadata = parse_markdown_blocks(markdown_text)
    sample_outline_payload = {
        "source_file": str(sample_file),
        "heading_count": len(outline),
        "outline": outline,
        "parser": metadata.get("parser"),
    }
    sample_report = {
        "status": "completed",
        "sample_file": str(sample_file),
        "sample_content_file": str(sample_content_file),
        "sample_outline_file": str(sample_outline_file),
        "heading_count": len(outline),
        "mode": summary.get("mode"),
        "converter": summary.get("converter"),
        "style_map_used": summary.get("style_map_used", False),
    }

    run_state.setdefault("artifacts", {})["sample_content"] = str(sample_content_file)
    run_state.setdefault("artifacts", {})["sample_outline"] = str(sample_outline_file)
    run_state.setdefault("artifacts", {})["sample_content_report"] = str(sample_report_file)

    write_json(sample_outline_file, sample_outline_payload)
    write_json(sample_report_file, sample_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()