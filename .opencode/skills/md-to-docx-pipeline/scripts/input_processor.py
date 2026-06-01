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


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuẩn hóa input nguồn thành normalized.md cho pipeline DOCX.")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--style-map-file", required=False)
    args = parser.parse_args()

    source_file = Path(args.source_file)
    run_dir = Path(args.run_dir)
    style_map_file = Path(args.style_map_file) if args.style_map_file else run_dir / "markitdown_style_map.txt"
    style_map = load_style_map(style_map_file)
    input_report_file = run_dir / "input_report.json"
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}

    try:
        markdown_text, summary = normalize_source_markdown(source_file, style_map=style_map)
    except (MarkItDownDependencyError, MarkItDownConversionError) as exc:
        normalized_file = run_dir / "normalized.md"
        normalized_file.unlink(missing_ok=True)
        run_state.setdefault("artifacts", {}).pop("normalized_markdown", None)
        run_state.setdefault("artifacts", {})["input_report"] = str(input_report_file)
        write_json(
            input_report_file,
            {
                "status": "failed",
                "source_file": str(source_file),
                "normalized_file": str(normalized_file),
                "source_extension": source_file.suffix.lower(),
                "style_map_file": str(style_map_file) if style_map else None,
                "message": str(exc),
            },
        )
        write_json(run_dir / "run.json", run_state)
        raise SystemExit(str(exc))

    normalized_file = run_dir / "normalized.md"
    normalized_file.write_text(markdown_text, encoding="utf-8")

    input_report = {
        "status": "completed",
        "source_file": str(source_file),
        "normalized_file": str(normalized_file),
        "source_extension": summary.get("source_extension"),
        "mode": summary.get("mode"),
        "converter": summary.get("converter"),
        "style_map_used": summary.get("style_map_used", False),
        "style_map_file": str(style_map_file) if style_map else None,
    }

    run_state.setdefault("artifacts", {})["normalized_markdown"] = str(normalized_file)
    run_state.setdefault("artifacts", {})["input_report"] = str(input_report_file)
    write_json(input_report_file, input_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()