from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import read_json, write_json
from pandoc_support import PandocConversionError, PandocDependencyError, load_style_spec, normalize_source_markdown


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuẩn hóa input nguồn thành normalized.md cho pipeline DOCX qua Pandoc.")
    parser.add_argument("--source-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--style-spec-file", required=False)
    parser.add_argument("--style-map-file", required=False)
    args = parser.parse_args()

    source_file = Path(args.source_file)
    run_dir = Path(args.run_dir)
    style_spec_file = (
        Path(args.style_spec_file)
        if args.style_spec_file
        else (Path(args.style_map_file) if args.style_map_file else run_dir / "pandoc_style_spec.json")
    )
    style_spec = load_style_spec(style_spec_file)
    input_report_file = run_dir / "input_report.json"
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}

    try:
        markdown_text, summary = normalize_source_markdown(source_file, style_spec=style_spec)
    except (PandocDependencyError, PandocConversionError) as exc:
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
                "style_spec_file": str(style_spec_file) if style_spec else None,
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
        "style_spec_used": summary.get("style_spec_used", False),
        "style_spec_file": str(style_spec_file) if style_spec else None,
    }

    run_state.setdefault("artifacts", {})["normalized_markdown"] = str(normalized_file)
    run_state.setdefault("artifacts", {})["input_report"] = str(input_report_file)
    write_json(input_report_file, input_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()