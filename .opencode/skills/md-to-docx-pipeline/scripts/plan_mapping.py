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


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_text.upper().split())


def style_score(entry: dict, target_kind: str) -> tuple[int, int, int]:
    name = normalize_text(entry.get("name") or "")
    style_id = normalize_text(entry.get("style_id") or "")
    outline = entry.get("outline_level")
    qformat = 1 if entry.get("qformat") else 0
    custom = 1 if entry.get("custom") else 0

    if target_kind == "body":
        default = 1 if entry.get("default") else 0
        normal_like = 1 if "NORMAL" in name or "NORMAL" in style_id else 0
        return (default, normal_like, qformat)

    if target_kind == "list":
        list_like = 1 if "LIST" in name or "LIST" in style_id else 0
        numbered_like = 1 if "NUMBER" in name or "DANH SACH" in name else 0
        return (list_like, numbered_like, qformat)

    level = int(target_kind[1:]) - 1
    outline_match = 2 if outline is not None and str(outline) == str(level) else 0
    exact_heading = 1 if re.search(rf"\bHEADING\s*{level + 1}\b", name) else 0
    exact_style_id = 1 if re.search(rf"\bHEADING\s*{level + 1}\b", style_id) else 0
    chapter_like = 1 if level == 0 and ("CHUONG" in name or "TIEU DE" in name or "TITLE" in name) else 0
    return (outline_match + exact_heading + exact_style_id, qformat + custom, chapter_like)


def choose_style(style_catalog: list[dict], target_kind: str, fallback: str) -> str:
    paragraph_styles = [entry for entry in style_catalog if entry.get("style_id")]
    if not paragraph_styles:
        return fallback
    ranked = sorted(paragraph_styles, key=lambda entry: style_score(entry, target_kind), reverse=True)
    best = ranked[0]
    if max(style_score(best, target_kind)) <= 0:
        return fallback
    return best["style_id"]


def infer_style_map(profile: dict) -> dict:
    style_catalog = profile.get("style_catalog", [])
    return {
        "h1": choose_style(style_catalog, "h1", "Heading1"),
        "h2": choose_style(style_catalog, "h2", "Heading2"),
        "h3": choose_style(style_catalog, "h3", "Heading3"),
        "body": choose_style(style_catalog, "body", "Normal"),
        "list": choose_style(style_catalog, "list", choose_style(style_catalog, "body", "Normal")),
    }


def normalize_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập plan mapping giữa Markdown và template profile.")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-file", required=False)
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--target-file", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    outline_payload = read_json(run_dir / "content_outline.json") if (run_dir / "content_outline.json").exists() else {}
    profile_payload = read_json(run_dir / "template_profile.json")
    style_map = infer_style_map(profile_payload)
    normalized_mode = normalize_mode(args.mode)
    preserve_defaults = profile_payload.get("preserve_defaults", [])
    replace_ranges = profile_payload.get("document_profile", {}).get("replace_range_candidates", [])
    replace_ranges_resolved = any(item.get("status") == "resolved" for item in replace_ranges)

    plan = {
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "heading_count": outline_payload.get("heading_count", 0),
        "style_map": style_map,
        "has_numbering": profile_payload.get("has_numbering", False),
        "preserve": preserve_defaults,
        "replace_ranges": replace_ranges,
        "post_conditions": [
            "headers-footers-preserved",
            "section-breaks-preserved",
            "heading-style-mapped-to-template",
            "no-template-body-residue-inside-replaced-range",
        ],
        "execution_strategy": "replace-body-range-in-document-xml",
        "status": "ready-for-execution" if normalized_mode == "preserve-template-scaffold" and replace_ranges_resolved else "blocked",
        "error_contract": {
            "blocked_means_do_not_build": True,
            "builder_must_write_blocked_report": True,
            "qa_must_fail_if_build_runs_without_resolved_range": True,
        },
        "steps": [
            "Đọc content_ast.json",
            "Áp style_map cho heading và body",
            "Giữ header/footer, page setup và các field cấu trúc từ template khi phù hợp",
            "Chỉ thay bounded range đã resolve",
            "Đánh dấu TOC, danh mục hình/bảng và references cần QA sau build"
        ],
        "blocking_reasons": [] if replace_ranges_resolved or normalized_mode != "preserve-template-scaffold" else [
            "Không resolve được replace_ranges cho mode preserve-template-scaffold."
        ],
    }
    run_state = {
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "preserve": preserve_defaults,
        "replace_ranges": replace_ranges,
        "artifacts": {
            "content_ast": str(run_dir / "content_ast.json"),
            "content_outline": str(run_dir / "content_outline.json"),
            "template_profile": str(run_dir / "template_profile.json"),
            "plan": str(run_dir / "plan.json")
        },
        "status": "planned" if plan["status"] == "ready-for-execution" else "blocked"
    }

    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()