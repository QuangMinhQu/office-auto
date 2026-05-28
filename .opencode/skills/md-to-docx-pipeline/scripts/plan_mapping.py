from __future__ import annotations

import argparse
import json
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


def infer_style_map(profile: dict) -> dict:
    style_names = {name.lower(): name for name in profile.get("style_names", [])}
    return {
        "h1": style_names.get("heading 1") or style_names.get("heading1") or "Heading 1",
        "h2": style_names.get("heading 2") or style_names.get("heading2") or "Heading 2",
        "h3": style_names.get("heading 3") or style_names.get("heading3") or "Heading 3",
        "body": style_names.get("normal") or "Normal",
        "list": style_names.get("list paragraph") or style_names.get("listparagraph") or style_names.get("normal") or "Normal",
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