from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path


MODE_ALIASES = {
    "rebuild-from-template-format": "preserve-template-scaffold",
    "append-to-template": "append-structured-section",
    "fill-template-placeholders": "fill-declared-placeholders",
}

SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?;:])\s+|\n+")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.upper().split())


def normalize_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def compact_whitespace(value: str) -> str:
    return " ".join(value.replace("\n", " ").split()).strip()


def truncate_text(value: str, max_chars: int) -> str:
    text = compact_whitespace(value)
    if len(text) <= max_chars:
        return text
    truncated = text[: max_chars - 1].rsplit(" ", 1)[0].strip()
    return (truncated or text[: max_chars - 1].strip()) + "..."


def block_text(block: dict) -> str:
    if block.get("type") == "table_row":
        return " | ".join(block.get("cells", []))
    return str(block.get("text", "")).strip()


def split_sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in SENTENCE_SPLIT_RE.split(text) if chunk.strip()]


def render_block_lines(block: dict, max_chars: int) -> list[str]:
    block_type = block.get("type")
    if block_type == "thematic_break":
        return []
    if block_type == "heading":
        level = int(block.get("level", 1))
        if level <= 2:
            return []
        return [truncate_text(f"Tiểu mục: {block_text(block)}", max_chars)]
    if block_type == "paragraph":
        sentences = split_sentences(block_text(block))
        if not sentences:
            return []
        return [truncate_text(sentence, max_chars) for sentence in sentences[:2]]
    if block_type == "list_item":
        prefix = f"{block.get('ordinal', 1)}." if block.get("ordered") else "•"
        return [truncate_text(f"{prefix} {block_text(block)}", max_chars)]
    if block_type == "blockquote":
        return [truncate_text(f"Trích dẫn: {block_text(block)}", max_chars)]
    if block_type == "table_row":
        return [truncate_text(f"Bảng: {block_text(block)}", max_chars)]
    if block_type == "code_block":
        first_line = next((line.strip() for line in block_text(block).splitlines() if line.strip()), "")
        return [truncate_text(f"CLI/Code: {first_line}", max_chars)] if first_line else []
    if block_type == "reference":
        ordinal = block.get("ordinal")
        prefix = f"[{ordinal}]" if ordinal is not None else "Tài liệu"
        return [truncate_text(f"{prefix} {block_text(block)}", max_chars)]
    text = block_text(block)
    return [truncate_text(text, max_chars)] if text else []


def collect_sections(blocks: list[dict]) -> tuple[str, list[dict]]:
    deck_title = None
    sections: list[dict] = []
    current_section: dict | None = None
    current_subsection: dict | None = None

    for block in blocks:
        if block.get("type") == "heading":
            level = int(block.get("level", 1))
            if deck_title is None and level == 1:
                deck_title = str(block.get("text") or "").strip()
                continue
            if level == 1:
                current_section = {
                    "title": str(block.get("text") or "").strip(),
                    "intro_blocks": [],
                    "subsections": [],
                }
                sections.append(current_section)
                current_subsection = None
                continue
            if level == 2:
                if current_section is None:
                    current_section = {"title": "Nội dung", "intro_blocks": [], "subsections": []}
                    sections.append(current_section)
                current_subsection = {"title": str(block.get("text") or "").strip(), "blocks": []}
                current_section["subsections"].append(current_subsection)
                continue

        if current_subsection is not None:
            current_subsection["blocks"].append(block)
        elif current_section is not None:
            current_section["intro_blocks"].append(block)

    return deck_title or "Báo cáo", sections


def chunk_lines(lines: list[str], chunk_size: int) -> list[list[str]]:
    if not lines:
        return [[]]
    return [lines[index : index + chunk_size] for index in range(0, len(lines), chunk_size)]


def build_slide_specs(blocks: list[dict], line_limit: int, max_chars: int, layout_name: str) -> tuple[str, str, list[str], list[dict]]:
    deck_title, sections = collect_sections(blocks)
    top_level_titles = [section["title"] for section in sections if section.get("title")]
    title_slide_summary = "Tien do, van de va ke hoach tuan tiep theo"

    slide_specs: list[dict] = []
    if top_level_titles:
        slide_specs.append(
            {
                "kind": "agenda",
                "title": "Nội dung",
                "body_lines": [truncate_text(f"• {item}", max_chars) for item in top_level_titles[:line_limit]],
                "layout": layout_name,
                "source_headings": top_level_titles,
            }
        )

    for section in sections:
        section_title = section.get("title") or "Nội dung"
        intro_lines: list[str] = []
        for block in section.get("intro_blocks", []):
            intro_lines.extend(render_block_lines(block, max_chars))

        subsections = section.get("subsections", [])
        if not subsections:
            content_lines = intro_lines or ["• Nội dung đang được cập nhật."]
            for chunk_index, chunk in enumerate(chunk_lines(content_lines, line_limit), start=1):
                title = section_title if chunk_index == 1 else f"{section_title} (tiếp {chunk_index - 1})"
                slide_specs.append(
                    {
                        "kind": "content",
                        "title": title,
                        "body_lines": chunk,
                        "layout": layout_name,
                        "section": section_title,
                        "source_headings": [section_title],
                    }
                )
            continue

        for subsection in subsections:
            subsection_title = subsection.get("title") or section_title
            lines: list[str] = []
            if intro_lines:
                lines.append(truncate_text(f"Phần: {section_title}", max_chars))
                lines.extend(intro_lines[:1])
            for block in subsection.get("blocks", []):
                lines.extend(render_block_lines(block, max_chars))
            lines = lines or ["• Nội dung đang được cập nhật."]
            for chunk_index, chunk in enumerate(chunk_lines(lines, line_limit), start=1):
                title = subsection_title if chunk_index == 1 else f"{subsection_title} (tiếp {chunk_index - 1})"
                slide_specs.append(
                    {
                        "kind": "content",
                        "title": title,
                        "body_lines": chunk,
                        "layout": layout_name,
                        "section": section_title,
                        "source_headings": [section_title, subsection_title],
                    }
                )

    return deck_title, title_slide_summary, top_level_titles, slide_specs


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập plan mapping giữa Markdown và template profile cho PPTX.")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-file", required=False)
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--target-file", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    content_ast = read_json(run_dir / "content_ast.json")
    outline_payload = read_json(run_dir / "content_outline.json") if (run_dir / "content_outline.json").exists() else {}
    template_profile = read_json(run_dir / "template_profile.json")
    normalized_mode = normalize_mode(args.mode)
    replace_ranges = template_profile.get("replace_range_candidates", [])
    resolved_range = next((item for item in replace_ranges if item.get("status") == "resolved"), None)
    layout_name = template_profile.get("content_prototype", {}).get("layout") or "OBJECT"
    line_limit = 6
    max_chars = 120
    deck_title, title_slide_summary, top_level_titles, slide_specs = build_slide_specs(content_ast.get("blocks", []), line_limit, max_chars, layout_name)

    title_slide_paths = template_profile.get("title_slide", {}).get("semantic_placeholder_paths", {})
    plan = {
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "heading_count": outline_payload.get("heading_count", 0),
        "preserve": template_profile.get("preserve_defaults", []),
        "replace_ranges": replace_ranges,
        "post_conditions": [
            "title-slide-still-present-if-template-had-it",
            "masters-and-layouts-preserved",
            "placeholder-bindings-not-broken",
            "layout-mapping-resolved-in-plan",
            "slide-order-matches-source-outline",
            "no-template-slide-residue-inside-replaced-range",
            "no-offslide-or-overflow-text-in-final-deck",
        ],
        "presentation_title": deck_title,
        "title_slide_update": {
            "title_path": title_slide_paths.get("title"),
            "subtitle_path": title_slide_paths.get("subtitle"),
            "title_text": deck_title,
            "subtitle_text": truncate_text(title_slide_summary, 120),
        },
        "content_range": {
            "target_start_index": (template_profile.get("title_slide", {}).get("index") or 0) + 1,
            "target_end_before_closing": template_profile.get("closing_slide", {}).get("index"),
            "prototype_slide_path": None if resolved_range is None else resolved_range.get("prototype_slide_path"),
            "insert_before_path": None if resolved_range is None else resolved_range.get("insert_before_path"),
        },
        "layout_mapping": {
            "title_slide": template_profile.get("title_slide", {}).get("profile", {}).get("layout"),
            "content_layout": layout_name,
            "prototype_placeholders": template_profile.get("content_prototype", {}).get("required_placeholder_types", []),
        },
        "slide_specs": slide_specs,
        "limits": {
            "body_line_limit": line_limit,
            "max_chars_per_line": max_chars,
        },
        "execution_strategy": "officecli-resident-clone-fill-remove",
        "status": "ready-for-execution" if normalized_mode == "preserve-template-scaffold" and resolved_range and slide_specs else "blocked",
        "blocking_reasons": [] if normalized_mode == "preserve-template-scaffold" and resolved_range and slide_specs else [
            "Không resolve được replace range hoặc không lập được slide plan cho PPTX."
        ],
        "error_contract": {
            "blocked_means_do_not_build": True,
            "builder_must_write_blocked_report": True,
            "qa_must_fail_if_build_runs_without_resolved_range": True,
        },
    }

    run_state = {
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "preserve": template_profile.get("preserve_defaults", []),
        "replace_ranges": replace_ranges,
        "artifacts": {
            "content_ast": str(run_dir / "content_ast.json"),
            "content_outline": str(run_dir / "content_outline.json"),
            "template_profile": str(run_dir / "template_profile.json"),
            "plan": str(run_dir / "plan.json"),
        },
        "status": "planned" if plan["status"] == "ready-for-execution" else "blocked",
    }

    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()