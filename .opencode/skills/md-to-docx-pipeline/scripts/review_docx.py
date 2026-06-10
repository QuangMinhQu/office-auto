from __future__ import annotations

import argparse
import html
from collections import Counter
from pathlib import Path
from typing import Any

from officecli_native import ensure_officecli_available, officecli_query, read_json, write_json


def build_body_paragraphs(paragraph_results: list[dict]) -> list[dict]:
    """Inline replacement for legacy profile_template.build_body_paragraphs.
    
    Collects body paragraphs from query results with format profile extraction.
    """
    body_paragraphs: list[dict] = []
    for idx, result in enumerate(paragraph_results):
        path = str(result.get("path", ""))
        if not path.startswith("/body/"):
            continue
        
        text = str(result.get("text") or "").strip()
        fmt = result.get("format", {})
        style_name = fmt.get("styleName") or result.get("style") or fmt.get("style")
        style_id = fmt.get("styleId")
        
        format_profile = {
            "align": fmt.get("effective.align") or fmt.get("align"),
            "size": fmt.get("effective.size") or fmt.get("size"),
            "font": fmt.get("effective.font.ascii") or fmt.get("font.ascii") or fmt.get("font.latin"),
            "first_line_indent": fmt.get("effective.firstLineIndent") or fmt.get("firstLineIndent"),
            "line_spacing": fmt.get("effective.lineSpacing") or fmt.get("lineSpacing"),
            "space_before": fmt.get("effective.spaceBefore") or fmt.get("spaceBefore"),
            "space_after": fmt.get("effective.spaceAfter") or fmt.get("spaceAfter"),
            "list_style": fmt.get("effective.listStyle") or fmt.get("listStyle"),
        }
        
        bookmarks = {
            child.get("format", {}).get("name")
            for child in result.get("children", [])
            if child.get("type") == "bookmark" and child.get("format", {}).get("name")
        }
        
        body_paragraphs.append({
            "index": idx,
            "path": path,
            "text": text,
            "style": style_name,
            "style_id": style_id,
            "format_profile": format_profile,
            "bookmarks": bookmarks,
        })
    
    return body_paragraphs


DISPLAY_LIMIT = 40
SUMMARY_TOP_LIMIT = 8


def string_value(value: Any) -> str:
    if value in (None, ""):
        return "(none)"
    return str(value)


def normalized_counter(counter: Counter[str], limit: int = SUMMARY_TOP_LIMIT) -> list[dict]:
    return [
        {"value": value, "count": count}
        for value, count in counter.most_common(limit)
    ]


def first_run(prototype: dict) -> dict:
    return next((run for run in prototype.get("runs", []) if str(run.get("text") or "")), {})


def prototype_for_role(role: str, prototype_catalog: dict) -> dict:
    prototype = prototype_catalog.get(role) or {}
    if prototype:
        return prototype
    if role in {"body", "list", "reference", "blockquote", "code"}:
        return prototype_catalog.get("body", {})
    return {}


def expected_profile(operation: dict, prototype_catalog: dict) -> dict:
    role = str(operation.get("role") or "body")
    prototype = prototype_for_role(role, prototype_catalog)
    paragraph_format = prototype.get("paragraph_format", {})
    run = first_run(prototype)
    set_props = operation.get("set_props", {})

    expected = {
        "style": set_props.get("style") or operation.get("fallback_style") or prototype.get("style_id") or prototype.get("style_name"),
        "align": set_props.get("align") or paragraph_format.get("align"),
        "line_spacing": set_props.get("lineSpacing") or paragraph_format.get("line_spacing"),
        "space_before": set_props.get("spaceBefore") or paragraph_format.get("space_before"),
        "space_after": set_props.get("spaceAfter") or paragraph_format.get("space_after"),
        "size": set_props.get("size") or run.get("size") or paragraph_format.get("size"),
        "font": set_props.get("font") or run.get("font_ascii") or run.get("font_latin") or paragraph_format.get("font_ascii") or paragraph_format.get("font_latin"),
        "list_style": set_props.get("listStyle") or paragraph_format.get("list_style"),
    }
    return {key: value for key, value in expected.items() if value not in (None, "")}


def actual_profile(paragraph: dict) -> dict:
    format_profile = paragraph.get("format_profile", {})
    return {
        "style": paragraph.get("style_id") or paragraph.get("style"),
        "align": format_profile.get("align"),
        "line_spacing": format_profile.get("line_spacing"),
        "space_before": format_profile.get("space_before"),
        "space_after": format_profile.get("space_after"),
        "size": format_profile.get("size"),
        "font": format_profile.get("font_ascii") or format_profile.get("font_latin"),
        "list_style": format_profile.get("list_style"),
    }


def style_matches(expected_style: Any, paragraph: dict) -> bool:
    if expected_style in (None, ""):
        return True
    candidates = {
        str(paragraph.get("style") or "").strip().upper(),
        str(paragraph.get("style_id") or "").strip().upper(),
    }
    return str(expected_style).strip().upper() in candidates


def compare_profiles(paragraph: dict, expected: dict) -> list[dict]:
    actual = actual_profile(paragraph)
    differences: list[dict] = []

    if expected.get("style") and not style_matches(expected.get("style"), paragraph):
        differences.append(
            {
                "field": "style",
                "expected": string_value(expected.get("style")),
                "actual": string_value(paragraph.get("style_id") or paragraph.get("style")),
            }
        )

    for field in ["align", "line_spacing", "space_before", "space_after", "size", "font", "list_style"]:
        expected_value = expected.get(field)
        if expected_value in (None, ""):
            continue
        actual_value = actual.get(field)
        if string_value(expected_value) != string_value(actual_value):
            differences.append(
                {
                    "field": field,
                    "expected": string_value(expected_value),
                    "actual": string_value(actual_value),
                }
            )

    return differences


def risk_flags_for_paragraph(role: str, paragraph: dict, differences: list[dict]) -> list[str]:
    flags: list[str] = []
    actual = actual_profile(paragraph)
    diff_fields = {item.get("field") for item in differences}

    if role in {"body", "list", "reference", "blockquote"} and str(actual.get("align") or "").lower() == "center":
        flags.append("body-centered")
    if "size" in diff_fields:
        flags.append("font-size-drift")
    if "line_spacing" in diff_fields:
        flags.append("line-spacing-drift")
    if "space_before" in diff_fields or "space_after" in diff_fields:
        flags.append("paragraph-spacing-drift")
    if "style" in diff_fields:
        flags.append("style-drift")
    if "font" in diff_fields:
        flags.append("font-family-drift")
    return flags


def summarize_document(paragraphs: list[dict], section_count: int, header_count: int, footer_count: int, toc_count: int, field_count: int) -> dict:
    style_counter: Counter[str] = Counter()
    align_counter: Counter[str] = Counter()
    size_counter: Counter[str] = Counter()
    line_spacing_counter: Counter[str] = Counter()

    for paragraph in paragraphs:
        format_profile = paragraph.get("format_profile", {})
        style_counter[string_value(paragraph.get("style_id") or paragraph.get("style"))] += 1
        align_counter[string_value(format_profile.get("align"))] += 1
        size_counter[string_value(format_profile.get("size"))] += 1
        line_spacing_counter[string_value(format_profile.get("line_spacing"))] += 1

    return {
        "paragraph_count": len(paragraphs),
        "section_count": section_count,
        "header_count": header_count,
        "footer_count": footer_count,
        "toc_count": toc_count,
        "field_count": field_count,
        "top_styles": normalized_counter(style_counter),
        "top_alignments": normalized_counter(align_counter),
        "top_font_sizes": normalized_counter(size_counter),
        "top_line_spacings": normalized_counter(line_spacing_counter),
    }


def document_snapshot(document: Path) -> dict:
    paragraph_results = officecli_query(document, "paragraph")
    body_paragraphs = build_body_paragraphs(paragraph_results)
    section_results = officecli_query(document, "section")
    header_results = officecli_query(document, "header")
    footer_results = officecli_query(document, "footer")
    toc_results = officecli_query(document, "toc")
    field_results = officecli_query(document, "field")

    return {
        "file": str(document),
        "paragraphs": body_paragraphs,
        "summary": summarize_document(
            body_paragraphs,
            section_count=len(section_results),
            header_count=len(header_results),
            footer_count=len(footer_results),
            toc_count=len(toc_results),
            field_count=len(field_results),
        ),
    }


def inserted_paragraph_reviews(execution_ops: dict, build_report: dict, target_snapshot: dict, prototype_catalog: dict) -> tuple[list[dict], dict]:
    """Review inserted paragraphs from execution_ops (new pipeline schema).
    
    execution_ops can be:
    - New schema: {"version": "2", "ops": [...]}
    - Legacy schema: {"render_ops": [...]}
    - Legacy list: [...]
    """
    target_by_path = {str(paragraph.get("path")): paragraph for paragraph in target_snapshot.get("paragraphs", [])}
    
    # Handle new pipeline schema
    if isinstance(execution_ops, dict):
        render_ops = execution_ops.get("ops", [])
    elif isinstance(execution_ops, list):
        render_ops = execution_ops
    else:
        render_ops = execution_ops.get("render_ops", [])
    
    inserted_paths = build_report.get("inserted_paths", [])
    review_items: list[dict] = []
    risk_counter: Counter[str] = Counter()

    for index, operation in enumerate(render_ops):
        if operation.get("op") != "insert_paragraph_after" and operation.get("op") != "insert_paragraph_before":
            continue
        if index >= len(inserted_paths):
            continue
        inserted_path = str(inserted_paths[index])
        paragraph = target_by_path.get(inserted_path)
        if not paragraph:
            continue

        expected = expected_profile(operation, prototype_catalog)
        differences = compare_profiles(paragraph, expected)
        flags = risk_flags_for_paragraph(str(operation.get("role") or "body"), paragraph, differences)
        for flag in flags:
            risk_counter[flag] += 1

        review_items.append(
            {
                "index": len(review_items),
                "path": inserted_path,
                "role": operation.get("role"),
                "block_type": operation.get("op"),
                "text": str(paragraph.get("text") or "")[:220],
                "expected": expected,
                "actual": actual_profile(paragraph),
                "differences": differences,
                "risk_flags": flags,
            }
        )

    return review_items, {
        "inserted_paragraph_count": len(review_items),
        "paragraphs_with_differences": len([item for item in review_items if item.get("differences")]),
        "paragraphs_with_attention": len([item for item in review_items if item.get("differences") or item.get("risk_flags")]),
        "risk_flags": normalized_counter(risk_counter, limit=20),
    }


def summary_table(items: list[dict], key_label: str, value_label: str) -> str:
    if not items:
        return "| Value | Count |\n| --- | ---: |\n| (none) | 0 |\n"
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for item in items:
        lines.append(f"| {item.get('value')} | {item.get('count')} |")
    return "\n".join(lines) + "\n"


def review_markdown(report: dict) -> str:
    baseline = report.get("comparison_baseline", {})
    baseline_summary = baseline.get("summary", {})
    target_summary = report.get("target_summary", {})
    inserted_summary = report.get("inserted_paragraph_summary", {})
    suspicious = [
        item
        for item in report.get("inserted_paragraph_reviews", [])
        if item.get("differences") or item.get("risk_flags")
    ][:DISPLAY_LIMIT]

    parts = [
        "# DOCX Screen Review",
        "",
        f"- Baseline review file: `{baseline.get('file')}`",
        f"- Original template file: `{report.get('source_template_file')}`",
        f"- Target file: `{report.get('target_file')}`",
        f"- QA status: `{report.get('qa_status')}`",
        f"- Review baseline reason: {baseline.get('reason')}",
        "",
        "## Document Summary",
        "",
        f"- Baseline paragraphs: {baseline_summary.get('paragraph_count', 0)}",
        f"- Output paragraphs: {target_summary.get('paragraph_count', 0)}",
        f"- Inserted paragraphs reviewed: {inserted_summary.get('inserted_paragraph_count', 0)}",
        f"- Inserted paragraphs with format differences: {inserted_summary.get('paragraphs_with_differences', 0)}",
        f"- Inserted paragraphs needing attention: {inserted_summary.get('paragraphs_with_attention', 0)}",
        "",
        "### Baseline Alignments",
        "",
        summary_table(baseline_summary.get('top_alignments', []), "Alignment", "Count"),
        "### Output Alignments",
        "",
        summary_table(target_summary.get('top_alignments', []), "Alignment", "Count"),
        "### Review Risk Flags",
        "",
        summary_table(inserted_summary.get('risk_flags', []), "Risk Flag", "Count"),
        "## Suspicious Inserted Paragraphs",
        "",
    ]

    if not suspicious:
        parts.append("Không thấy paragraph mới nào có drift rõ ràng theo các tín hiệu align/spacing/size/style đã kiểm.")
        return "\n".join(parts) + "\n"

    for item in suspicious:
        parts.extend(
            [
                f"### [{item.get('index')}] {item.get('role')} - {item.get('path')}",
                "",
                f"Text: {item.get('text')}",
                "",
                f"- Risk flags: {', '.join(item.get('risk_flags') or ['none'])}",
                f"- Expected: {item.get('expected')}",
                f"- Actual: {item.get('actual')}",
                "",
            ]
        )
        if item.get("differences"):
            parts.append("| Field | Expected | Actual |")
            parts.append("| --- | --- | --- |")
            for difference in item.get("differences", []):
                parts.append(
                    f"| {difference.get('field')} | {difference.get('expected')} | {difference.get('actual')} |"
                )
            parts.append("")

    return "\n".join(parts) + "\n"


def summary_list_html(items: list[dict]) -> str:
    if not items:
        return "<li>(none)</li>"
    return "".join(
        f"<li><span class=\"pill\">{html.escape(str(item.get('value')))}</span> <strong>{item.get('count')}</strong></li>"
        for item in items
    )


def review_html(report: dict) -> str:
    baseline = report.get("comparison_baseline", {})
    suspicious = [
        item
        for item in report.get("inserted_paragraph_reviews", [])
        if item.get("differences") or item.get("risk_flags")
    ][:DISPLAY_LIMIT]
    target_summary = report.get("target_summary", {})
    baseline_summary = baseline.get("summary", {})
    inserted_summary = report.get("inserted_paragraph_summary", {})

    cards = []
    for item in suspicious:
        rows = "".join(
            "<tr>"
            f"<td>{html.escape(str(difference.get('field')))}</td>"
            f"<td>{html.escape(str(difference.get('expected')))}</td>"
            f"<td>{html.escape(str(difference.get('actual')))}</td>"
            "</tr>"
            for difference in item.get("differences", [])
        )
        cards.append(
            "<section class=\"card\">"
            f"<h3>#{item.get('index')} {html.escape(str(item.get('role')))} <span class=\"path\">{html.escape(str(item.get('path')))}</span></h3>"
            f"<p class=\"text\">{html.escape(str(item.get('text')))}</p>"
            f"<p><strong>Risk flags:</strong> {html.escape(', '.join(item.get('risk_flags') or ['none']))}</p>"
            f"<p><strong>Expected:</strong> {html.escape(str(item.get('expected')))}</p>"
            f"<p><strong>Actual:</strong> {html.escape(str(item.get('actual')))}</p>"
            "<table><thead><tr><th>Field</th><th>Expected</th><th>Actual</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            "</section>"
        )

    if not cards:
        cards.append("<section class=\"card\"><h3>No suspicious inserted paragraphs</h3><p>The review script did not detect alignment, spacing, size, font, or style drift in inserted paragraphs.</p></section>")

    return f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <title>DOCX Screen Review</title>
  <style>
    :root {{
      --bg: #f3efe6;
      --panel: #fffdf8;
      --ink: #1e1a16;
      --muted: #6d6257;
      --line: #d7cbbd;
      --accent: #9f3a22;
      --warn: #a05a00;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #efe7db 0%, var(--bg) 100%); color: var(--ink); }}
    main {{ max-width: 1200px; margin: 0 auto; padding: 32px 24px 80px; }}
    h1, h2, h3 {{ margin: 0 0 12px; }}
    .hero {{ background: var(--panel); border: 1px solid var(--line); padding: 24px; border-radius: 18px; box-shadow: 0 18px 40px rgba(80, 56, 32, 0.08); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 20px; }}
    .metric, .card {{ background: var(--panel); border: 1px solid var(--line); border-radius: 16px; padding: 18px; box-shadow: 0 14px 26px rgba(80, 56, 32, 0.06); }}
    .metric strong {{ display: block; font-size: 28px; margin-bottom: 6px; }}
    .muted, .path {{ color: var(--muted); }}
    .pill {{ display: inline-block; padding: 2px 8px; border: 1px solid var(--line); border-radius: 999px; margin-right: 8px; background: #fbf6ef; }}
    ul {{ margin: 10px 0 0; padding-left: 18px; }}
    .cards {{ display: grid; gap: 16px; margin-top: 24px; }}
    .text {{ white-space: pre-wrap; line-height: 1.5; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 14px; }}
    th, td {{ padding: 10px 8px; border-top: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .warning {{ color: var(--warn); }}
    .accent {{ color: var(--accent); }}
  </style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <h1>DOCX Screen Review</h1>
      <p class=\"muted\">A post-build visual review layer for format drift between the generated DOCX and the template baseline.</p>
      <p><strong>Baseline review file:</strong> {html.escape(str(baseline.get('file')))}</p>
      <p><strong>Original template file:</strong> {html.escape(str(report.get('source_template_file')))}</p>
      <p><strong>Target file:</strong> {html.escape(str(report.get('target_file')))}</p>
      <p><strong>QA status:</strong> <span class=\"accent\">{html.escape(str(report.get('qa_status')))}</span></p>
      <p><strong>Baseline reason:</strong> {html.escape(str(baseline.get('reason')))}</p>
    </section>
    <section class=\"grid\">
      <div class=\"metric\"><strong>{baseline_summary.get('paragraph_count', 0)}</strong><span class=\"muted\">Baseline paragraphs</span></div>
      <div class=\"metric\"><strong>{target_summary.get('paragraph_count', 0)}</strong><span class=\"muted\">Output paragraphs</span></div>
      <div class=\"metric\"><strong>{inserted_summary.get('inserted_paragraph_count', 0)}</strong><span class=\"muted\">Inserted paragraphs reviewed</span></div>
            <div class=\"metric\"><strong>{inserted_summary.get('paragraphs_with_differences', 0)}</strong><span class=\"muted\">Inserted paragraphs with drift</span></div>
            <div class=\"metric\"><strong>{inserted_summary.get('paragraphs_with_attention', 0)}</strong><span class=\"muted\">Inserted paragraphs needing attention</span></div>
    </section>
        <section class=\"grid\" style=\"margin-top: 18px;\">
      <div class=\"card\">
        <h2>Baseline Alignments</h2>
        <ul>{summary_list_html(baseline_summary.get('top_alignments', []))}</ul>
      </div>
      <div class=\"card\">
        <h2>Output Alignments</h2>
        <ul>{summary_list_html(target_summary.get('top_alignments', []))}</ul>
      </div>
      <div class=\"card\">
        <h2>Risk Flags</h2>
        <ul>{summary_list_html(inserted_summary.get('risk_flags', []))}</ul>
      </div>
    </section>
    <section class=\"cards\">
      <h2>Suspicious Inserted Paragraphs</h2>
      {''.join(cards)}
    </section>
  </main>
</body>
</html>
"""


def choose_review_baseline(preflight: dict, preparation_report: dict) -> tuple[Path, str, str]:
    source_template_file = str(preparation_report.get("source_template_file") or preflight.get("template_file"))
    effective_template_file = str(preparation_report.get("effective_template_file") or preflight.get("effective_template_file") or preflight.get("template_file"))

    if effective_template_file and Path(effective_template_file).exists() and effective_template_file != source_template_file:
        return Path(effective_template_file), source_template_file, "Using effective template as visual baseline because the source template contains historical main-story content."

    return Path(source_template_file), source_template_file, "Using source template as visual baseline."


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh review artifact cho DOCX output sau build.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state_file = run_dir / "run.json"
    run_state = read_json(run_state_file) if run_state_file.exists() else {"artifacts": {}}
    
    # New pipeline: read execution_ops.json (versioned schema)
    execution_ops = read_json(run_dir / "execution_ops.json") if (run_dir / "execution_ops.json").exists() else {}
    
    # New pipeline: read execute_ops_report.json
    build_report = read_json(run_dir / "execute_ops_report.json") if (run_dir / "execute_ops_report.json").exists() else {}
    
    # Legacy fallbacks
    preflight = read_json(run_dir / "preflight.json") if (run_dir / "preflight.json").exists() else {}
    plan = read_json(run_dir / "plan.json") if (run_dir / "plan.json").exists() else {}
    execution_plan = read_json(run_dir / "execution_plan.json") if (run_dir / "execution_plan.json").exists() else {}
    legacy_build_report = read_json(run_dir / "build_report.json") if (run_dir / "build_report.json").exists() else {}
    qa_report = read_json(run_dir / "qa_report.json") if (run_dir / "qa_report.json").exists() else {}
    template_profile = read_json(run_dir / "template_profile.json") if (run_dir / "template_profile.json").exists() else {}
    preparation_report = read_json(run_dir / "template_preparation_report.json") if (run_dir / "template_preparation_report.json").exists() else {}

    def _safe_resolve_target(*candidates: Any) -> Path | None:
        for c in candidates:
            if c and str(c).strip() not in ("", "None", "null"):
                p = Path(str(c))
                if p.exists():
                    return p
        return None

    target_file = _safe_resolve_target(
        run_state.get("target_file"),
        build_report.get("target_file"),
        legacy_build_report.get("target_file"),
        plan.get("target_file"),
    )
    if target_file is None or not target_file.exists():
        review_report = {
            "status": "blocked",
            "message": "Không thể review vì target_file chưa tồn tại.",
            "target_file": str(target_file),
        }
        write_json(run_dir / "review_report.json", review_report)
        return

    ensure_officecli_available()
    baseline_file, source_template_file, baseline_reason = choose_review_baseline(preflight, preparation_report)
    baseline_snapshot = document_snapshot(baseline_file)
    target_snapshot = document_snapshot(target_file)
    inserted_reviews, inserted_summary = inserted_paragraph_reviews(
        execution_ops,
        build_report,
        target_snapshot,
        template_profile.get("prototype_catalog", {}),
    )

    review_report = {
        "status": "completed",
        "target_file": str(target_file),
        "source_template_file": source_template_file,
        "qa_status": qa_report.get("status", "unknown"),
        "comparison_baseline": {
            "file": str(baseline_file),
            "reason": baseline_reason,
            "summary": baseline_snapshot.get("summary", {}),
        },
        "target_summary": target_snapshot.get("summary", {}),
        "inserted_paragraph_summary": inserted_summary,
        "inserted_paragraph_reviews": inserted_reviews,
        "selected_replace_range": (execution_plan.get("selected_replace_range") or {}),
        "style_map": plan.get("style_map", {}),
        "message": "Review artifact đã so baseline template với output và soi drift formatting trên các paragraph mới được render.",
    }

    review_report_file = run_dir / "review_report.json"
    review_markdown_file = run_dir / "review_report.md"
    review_html_file = run_dir / "review_screen.html"

    write_json(review_report_file, review_report)
    review_markdown_file.write_text(review_markdown(review_report), encoding="utf-8")
    review_html_file.write_text(review_html(review_report), encoding="utf-8")

    run_state.setdefault("artifacts", {})["review_report"] = str(review_report_file)
    run_state.setdefault("artifacts", {})["review_markdown"] = str(review_markdown_file)
    run_state.setdefault("artifacts", {})["review_html"] = str(review_html_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()