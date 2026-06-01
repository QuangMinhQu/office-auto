from __future__ import annotations

import argparse
import re
from difflib import SequenceMatcher
from pathlib import Path

from officecli_native import normalize_text, read_json, write_json

from markitdown_support import MarkItDownConversionError, MarkItDownDependencyError, load_style_map, normalize_source_markdown
from parse_markdown import parse_markdown_blocks
from semantic_grounding import derive_render_window, filter_blocks, filter_outline


BACK_MATTER_MARKERS = {
    "references": {"TAI LIEU THAM KHAO", "REFERENCES", "BIBLIOGRAPHY"},
    "appendix": {"PHU LUC", "APPENDIX"},
}
INLINE_MATH_PATTERN = re.compile(r"(?<!\$)\$[^$\n]+\$(?!\$)")
BLOCK_MATH_PATTERN = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


def strip_heading_numbering(text: str) -> str:
    stripped = text.strip()
    stripped = re.sub(r"^(?:CHƯƠNG\s+\d+\.?\s*|CHUONG\s+\d+\.?\s*)", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"^(?:\d+(?:\.\d+)*\.?\s+)", "", stripped)
    stripped = re.sub(r"^(?:[IVXLCDM]+\.|[A-Z]\.)\s+", "", stripped)
    return stripped.strip()


def normalize_heading_text(text: str) -> str:
    return normalize_text(strip_heading_numbering(text))


def heading_zone(text: str) -> str | None:
    normalized = normalize_text(text)
    for zone_name, markers in BACK_MATTER_MARKERS.items():
        if normalized in markers:
            return zone_name
    return None


def is_subsequence(source: list[str], output: list[str]) -> bool:
    source_normalized = [normalize_heading_text(item) for item in source if item.strip()]
    output_normalized = [normalize_heading_text(item) for item in output if item.strip()]
    if not source_normalized:
        return True

    output_index = 0
    for source_item in source_normalized:
        while output_index < len(output_normalized) and output_normalized[output_index] != source_item:
            output_index += 1
        if output_index >= len(output_normalized):
            return False
        output_index += 1
    return True


def block_text(blocks: list[dict]) -> str:
    texts = [str(block.get("text") or "").strip() for block in blocks if str(block.get("text") or "").strip()]
    return "\n".join(texts)


def count_math_literals(text: str) -> dict:
    block_count = len(BLOCK_MATH_PATTERN.findall(text))
    inline_text = BLOCK_MATH_PATTERN.sub("", text)
    inline_count = len(INLINE_MATH_PATTERN.findall(inline_text))
    return {
        "inline": inline_count,
        "block": block_count,
        "total": inline_count + block_count,
    }


def build_roundtrip_report(
    source_ast: dict,
    source_outline: dict,
    roundtrip_markdown: str,
    *,
    target_file: str,
    style_map_used: bool,
    source_render_window: dict | None = None,
    sample_content_file: str | None = None,
) -> dict:
    roundtrip_blocks, roundtrip_outline, _ = parse_markdown_blocks(roundtrip_markdown)
    output_render_window = derive_render_window(roundtrip_blocks, sample_content_file=sample_content_file)
    source_blocks = filter_blocks(source_ast.get("blocks", []), source_render_window)
    source_headings = [str(item.get("text") or "") for item in filter_outline(source_outline.get("outline", []), source_render_window)]
    roundtrip_blocks = filter_blocks(roundtrip_blocks, output_render_window)
    roundtrip_headings = [str(item.get("text") or "") for item in filter_outline(roundtrip_outline, output_render_window)]

    source_normalized = {normalize_heading_text(item) for item in source_headings if item.strip()}
    roundtrip_normalized = {normalize_heading_text(item) for item in roundtrip_headings if item.strip()}
    missing_headings = [item for item in source_headings if normalize_heading_text(item) not in roundtrip_normalized]
    extra_headings = [item for item in roundtrip_headings if normalize_heading_text(item) not in source_normalized]

    source_markers = sorted({marker for marker in (heading_zone(item) for item in source_headings) if marker})
    roundtrip_markers = sorted({marker for marker in (heading_zone(item) for item in roundtrip_headings) if marker})

    source_table_count = len([block for block in source_blocks if block.get("type") == "table"])
    roundtrip_table_count = len([block for block in roundtrip_blocks if block.get("type") == "table"])

    source_text = block_text(source_blocks)
    roundtrip_text = block_text(roundtrip_blocks)
    similarity_ratio = SequenceMatcher(None, normalize_text(source_text), normalize_text(roundtrip_text)).ratio()

    heading_subsequence_ok = is_subsequence(source_headings, roundtrip_headings)
    references_ok = "references" not in source_markers or "references" in roundtrip_markers
    appendix_ok = "appendix" not in source_markers or "appendix" in roundtrip_markers
    tables_ok = source_table_count == roundtrip_table_count

    status = "passed" if all([heading_subsequence_ok, references_ok, appendix_ok, tables_ok]) else "failed"
    return {
        "status": status,
        "target_file": target_file,
        "heading_subsequence_ok": heading_subsequence_ok,
        "missing_headings": missing_headings,
        "extra_headings": extra_headings,
        "table_count_source": source_table_count,
        "table_count_roundtrip": roundtrip_table_count,
        "source_zone_markers": source_markers,
        "roundtrip_zone_markers": roundtrip_markers,
        "body_text_similarity_summary": {
            "source_length": len(source_text),
            "roundtrip_length": len(roundtrip_text),
            "ratio": round(similarity_ratio, 4),
        },
        "math_literal_count_source": count_math_literals(source_text),
        "math_literal_count_roundtrip": count_math_literals(roundtrip_markdown),
        "style_map_used": style_map_used,
        "source_render_window": source_render_window or {},
        "output_render_window": output_render_window,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Roundtrip output DOCX qua MarkItDown để làm semantic QA.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--style-map-file", required=False)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    plan = read_json(run_dir / "plan.json")
    build_report = read_json(run_dir / "build_report.json") if (run_dir / "build_report.json").exists() else {}
    source_ast = read_json(run_dir / "content_ast.json")
    source_outline = read_json(run_dir / "content_outline.json")
    target_file = Path(plan.get("target_file"))
    semantic_grounding = plan.get("semantic_grounding") or {}
    style_map_file = Path(args.style_map_file) if args.style_map_file else run_dir / "markitdown_style_map.txt"
    style_map = load_style_map(style_map_file)
    roundtrip_markdown_file = run_dir / "roundtrip.md"
    roundtrip_report_file = run_dir / "roundtrip_report.json"

    if build_report.get("status") != "completed" or not target_file.exists():
        report = {
            "status": "blocked",
            "target_file": str(target_file),
            "message": "Build chưa hoàn tất nên chưa thể roundtrip DOCX qua MarkItDown.",
        }
        write_json(roundtrip_report_file, report)
        run_state.setdefault("artifacts", {})["roundtrip_report"] = str(roundtrip_report_file)
        write_json(run_dir / "run.json", run_state)
        return

    try:
        roundtrip_markdown, summary = normalize_source_markdown(target_file, style_map=style_map)
        roundtrip_markdown_file.write_text(roundtrip_markdown, encoding="utf-8")
        report = build_roundtrip_report(
            source_ast,
            source_outline,
            roundtrip_markdown,
            target_file=str(target_file),
            style_map_used=summary.get("style_map_used", False),
            source_render_window=semantic_grounding.get("source_render_window"),
            sample_content_file=semantic_grounding.get("sample_content"),
        )
        report["converter"] = summary.get("converter")
        run_state.setdefault("artifacts", {})["roundtrip_markdown"] = str(roundtrip_markdown_file)
    except (MarkItDownDependencyError, MarkItDownConversionError) as exc:
        roundtrip_markdown_file.unlink(missing_ok=True)
        run_state.setdefault("artifacts", {}).pop("roundtrip_markdown", None)
        report = {
            "status": "failed",
            "target_file": str(target_file),
            "message": str(exc),
        }

    write_json(roundtrip_report_file, report)
    run_state.setdefault("artifacts", {})["roundtrip_report"] = str(roundtrip_report_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()