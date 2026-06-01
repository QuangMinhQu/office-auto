from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from semantic_grounding import derive_render_window, filter_outline


MODE_ALIASES = {
    "rebuild-from-template-format": "preserve-template-scaffold",
    "append-to-template": "append-structured-section",
    "fill-template-placeholders": "fill-declared-placeholders",
}
BACK_MATTER_MARKERS = {
    "references": {"TAI LIEU THAM KHAO", "REFERENCES", "BIBLIOGRAPHY"},
    "appendix": {"PHU LUC", "APPENDIX"},
}


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    ascii_text = ascii_text.replace("Đ", "D").replace("đ", "d")
    return " ".join(ascii_text.upper().split())


def style_score(entry: dict, style_graph: dict, target_kind: str) -> tuple[int, int, int, int]:
    name = normalize_text(entry.get("name") or "")
    style_id = normalize_text(entry.get("style_id") or "")
    outline = entry.get("outline_level")
    qformat = 1 if entry.get("qformat") else 0
    custom = 1 if entry.get("custom") else 0
    graph_entry = style_graph.get(entry.get("style_id") or "", {})

    if target_kind == "body":
        default = 1 if entry.get("default") else 0
        normal_like = 1 if "NORMAL" in name or "NORMAL" in style_id else 0
        return (default, normal_like, qformat, custom)

    if target_kind == "list":
        list_like = 1 if graph_entry.get("list_like") else 0
        numbered_like = 1 if entry.get("num_id") not in (None, "", "0") else 0
        localized_like = 1 if "DANH SACH" in name or "LIST" in name or "LIST" in style_id else 0
        return (list_like, numbered_like, localized_like, qformat + custom)

    if target_kind == "reference":
        reference_like = 1 if any(token in name or token in style_id for token in ["REFERENCE", "BIBLIOGRAPHY", "TAILIEUTHAMKHAO", "TAI LIEU THAM KHAO"]) else 0
        numbered_like = 1 if entry.get("num_id") not in (None, "", "0") else 0
        list_like = 1 if graph_entry.get("list_like") else 0
        return (reference_like * 10 + numbered_like * 6 + list_like * 4, qformat, custom, 0)

    level = int(target_kind[1:]) - 1
    outline_match = 3 if outline is not None and str(outline) == str(level) else 0
    resolved_outline = 2 if str(graph_entry.get("resolved_outline_level")) == str(level) else 0
    exact_heading = 1 if re.search(rf"\bHEADING\s*{level + 1}\b", name) else 0
    exact_style_id = 1 if re.search(rf"\bHEADING\s*{level + 1}\b", style_id) else 0
    chapter_like = 1 if level == 0 and ("CHUONG" in name or "TIEU DE" in name or "TITLE" in name) else 0
    return (outline_match + resolved_outline, exact_heading + exact_style_id, chapter_like, qformat + custom)


def choose_style(style_catalog: list[dict], style_graph: dict, target_kind: str, fallback: str) -> str:
    paragraph_styles = [entry for entry in style_catalog if entry.get("style_id")]
    if not paragraph_styles:
        return fallback
    ranked = sorted(paragraph_styles, key=lambda entry: style_score(entry, style_graph, target_kind), reverse=True)
    best = ranked[0]
    if max(style_score(best, style_graph, target_kind)) <= 0:
        return fallback
    return best["style_id"]


def infer_style_map(profile: dict) -> dict:
    style_catalog = profile.get("style_catalog", [])
    style_graph = profile.get("style_graph", {})
    prototype_catalog = profile.get("prototype_catalog", {})

    def style_from_prototype(role: str, fallback_kind: str, fallback_value: str) -> str:
        prototype = prototype_catalog.get(role, {})
        style_id = prototype.get("style_id")
        return style_id or choose_style(style_catalog, style_graph, fallback_kind, fallback_value)

    body_style = style_from_prototype("body", "body", "Normal")
    reference_prototype = prototype_catalog.get("reference", {})
    reference_style = reference_prototype.get("style_id") or style_from_prototype("reference", "reference", body_style)
    style_map = {
        "h1": style_from_prototype("h1", "h1", "Heading1"),
        "h2": style_from_prototype("h2", "h2", "Heading2"),
        "h3": style_from_prototype("h3", "h3", "Heading3"),
        "body": body_style,
        "list": style_from_prototype("list", "list", body_style),
        "reference": reference_style,
        "blockquote": style_from_prototype("blockquote", "body", body_style),
        "code": style_from_prototype("code", "body", body_style),
    }

    for role, fallback_roles in {"h1": ["h2", "h3"], "h2": ["h3"]}.items():
        if style_map[role] != body_style:
            continue
        for fallback_role in fallback_roles:
            fallback_style = style_map[fallback_role]
            if fallback_style != body_style:
                style_map[role] = fallback_style
                break

    return style_map


def normalize_mode(mode: str) -> str:
    return MODE_ALIASES.get(mode, mode)


def source_zone_markers(outline_payload: dict) -> set[str]:
    markers: set[str] = set()
    for item in outline_payload.get("outline", []):
        normalized = normalize_text(str(item.get("text") or ""))
        for marker_name, values in BACK_MATTER_MARKERS.items():
            if normalized in values:
                markers.add(marker_name)
    return markers


def is_normal_like_style(style_id: str | None, style_name: str | None) -> bool:
    token = normalize_text(f"{style_id or ''} {style_name or ''}")
    if not token:
        return True
    return any(keyword in token for keyword in ["NORMAL", "MAC DINH", "DEFAULT"])


def assess_template_guardrails(profile: dict, selected_range: dict | None) -> dict:
    document_profile = profile.get("document_profile", {})
    field_graph = profile.get("field_graph", {})
    prototype_catalog = profile.get("prototype_catalog", {})

    direct_body_child_count = int(document_profile.get("direct_body_child_count") or 0)
    remove_paths = (selected_range or {}).get("remove_paths", [])
    remove_count = len(remove_paths)
    remove_ratio = 0.0 if direct_body_child_count <= 0 else round(remove_count / direct_body_child_count, 4)

    preserve_part_signal_count = 0
    if int(profile.get("header_count") or 0) > 0:
        preserve_part_signal_count += 1
    if int(profile.get("footer_count") or 0) > 0:
        preserve_part_signal_count += 1
    if field_graph.get("has_toc"):
        preserve_part_signal_count += 1
    if field_graph.get("has_list_of_figures"):
        preserve_part_signal_count += 1
    if field_graph.get("has_list_of_tables"):
        preserve_part_signal_count += 1
    if field_graph.get("pageref_anchors"):
        preserve_part_signal_count += 1

    weak_heading_roles = []
    for role in ["h1", "h2", "h3"]:
        prototype = prototype_catalog.get(role, {})
        if is_normal_like_style(prototype.get("style_id"), prototype.get("style_name")):
            weak_heading_roles.append(role)

    risk_flags: list[str] = []
    if direct_body_child_count >= 2000:
        risk_flags.append("oversized-template-body")
    if remove_count >= 500 and remove_ratio >= 0.85:
        risk_flags.append("whole-body-rewrite")
    if preserve_part_signal_count == 0 and remove_count >= 500 and remove_ratio >= 0.85:
        risk_flags.append("full-document-template-disguised-as-format")
    if len(weak_heading_roles) >= 2:
        risk_flags.append("weak-heading-prototypes")

    blocking_reasons: list[str] = []
    if "whole-body-rewrite" in risk_flags and "full-document-template-disguised-as-format" in risk_flags:
        blocking_reasons.append(
            "Template hiện tại đang buộc pipeline xóa gần toàn bộ body nhưng không có đủ preserve-part signals; cần template scaffold mỏng hơn hoặc strategy rewrite khác."
        )

    return {
        "direct_body_child_count": direct_body_child_count,
        "selected_range_remove_count": remove_count,
        "selected_range_remove_ratio": remove_ratio,
        "preserve_part_signal_count": preserve_part_signal_count,
        "weak_heading_roles": weak_heading_roles,
        "risk_flags": risk_flags,
        "build_allowed": not blocking_reasons,
        "blocking_reasons": blocking_reasons,
    }


def candidate_sort_key(candidate: dict) -> tuple[int, int]:
    end_index = candidate.get("paragraph_end_index")
    remove_count = len(candidate.get("remove_paths", []))
    return (999999 if end_index is None else int(end_index), remove_count)


def choose_replace_range(profile: dict, outline_payload: dict) -> tuple[dict | None, str]:
    candidates = [candidate for candidate in profile.get("document_profile", {}).get("replace_range_candidates", []) if candidate.get("status") == "resolved"]
    if not candidates:
        return None, "Không có replace_range resolved từ template compiler."

    source_markers = source_zone_markers(outline_payload)
    preferred_names: list[str] = []
    if "references" not in source_markers:
        preferred_names.append("after-front-matter-before-references")
    if "appendix" not in source_markers:
        preferred_names.append("after-front-matter-before-appendix")
    preferred_names.append("after-front-matter-to-end-of-main-story")

    for name in preferred_names:
        matching = [candidate for candidate in candidates if candidate.get("name") == name]
        if matching:
            chosen = sorted(matching, key=candidate_sort_key)[0]
            if name != "after-front-matter-to-end-of-main-story":
                return chosen, f"Chọn bounded range `{name}` để giữ scaffold hậu kỳ không xuất hiện trong outline nguồn."
            return chosen, "Chọn full main-story range vì outline nguồn bao phủ toàn bộ vùng nội dung chính."

    chosen = sorted(candidates, key=candidate_sort_key)[0]
    return chosen, f"Fallback sang candidate resolved ngắn nhất: `{chosen.get('name')}`."


def summarize_prototypes(profile: dict) -> dict:
    summary: dict[str, dict] = {}
    for role, prototype in (profile.get("prototype_catalog") or {}).items():
        summary[role] = {
            "path": prototype.get("path"),
            "style_id": prototype.get("style_id"),
            "direct_body_path": prototype.get("direct_body_path"),
            "fallback_role": prototype.get("fallback_role"),
            "num_id": prototype.get("num_id"),
            "ilvl": prototype.get("ilvl"),
        }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập plan mapping giữa Markdown và template profile.")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--source-file", required=False)
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--target-file", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    existing_run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    existing_artifacts = dict(existing_run_state.get("artifacts") or {})
    content_ast = read_json(run_dir / "content_ast.json") if (run_dir / "content_ast.json").exists() else {"blocks": []}
    outline_payload = read_json(run_dir / "content_outline.json") if (run_dir / "content_outline.json").exists() else {}
    profile_payload = read_json(run_dir / "template_profile.json")
    source_render_window = derive_render_window(
        content_ast.get("blocks", []),
        sample_content_file=existing_artifacts.get("sample_content"),
    )
    grounded_outline = filter_outline(outline_payload.get("outline", []), source_render_window)
    grounded_outline_payload = {
        "source_file": outline_payload.get("source_file"),
        "heading_count": len(grounded_outline),
        "outline": grounded_outline,
    }
    style_map = infer_style_map(profile_payload)
    normalized_mode = normalize_mode(args.mode)
    preserve_defaults = profile_payload.get("preserve_defaults", [])
    selected_range, range_reason = choose_replace_range(profile_payload, grounded_outline_payload)
    replace_ranges = profile_payload.get("document_profile", {}).get("replace_range_candidates", [])
    replace_ranges_resolved = selected_range is not None and selected_range.get("status") == "resolved"
    source_markers = sorted(source_zone_markers(grounded_outline_payload))
    template_guardrails = assess_template_guardrails(profile_payload, selected_range)

    selected_preserve_zones = []
    preserve_zones_by_name = {
        zone.get("name"): zone
        for zone in profile_payload.get("document_profile", {}).get("preserve_zones", [])
        if zone.get("name")
    }
    for zone_name in (selected_range or {}).get("preserve_zones", []):
        zone = preserve_zones_by_name.get(zone_name)
        if zone is not None:
            selected_preserve_zones.append(zone)

    render_roles = {
        "heading_level_1": "h1",
        "heading_level_2": "h2",
        "heading_level_3_plus": "h3",
        "paragraph": "body",
        "list_item": "list",
        "reference": "reference",
        "blockquote": "blockquote",
        "code_block": "code",
        "table": "table",
    }

    blocking_reasons = []
    if normalized_mode == "preserve-template-scaffold" and not replace_ranges_resolved:
        blocking_reasons.append("Không resolve được selected_replace_range cho mode preserve-template-scaffold.")
    blocking_reasons.extend(template_guardrails.get("blocking_reasons", []))

    plan = {
        "contract_version": "2.0",
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "heading_count": len(grounded_outline),
        "source_heading_count_raw": outline_payload.get("heading_count", 0),
        "style_map": style_map,
        "prototype_roles": summarize_prototypes(profile_payload),
        "render_roles": render_roles,
        "has_numbering": profile_payload.get("has_numbering", False),
        "preserve": preserve_defaults,
        "preserve_zones": selected_preserve_zones,
        "replace_ranges": replace_ranges,
        "selected_replace_range": selected_range,
        "field_dependencies": profile_payload.get("field_graph", {}),
        "bookmark_dependencies": profile_payload.get("bookmark_graph", {}),
        "post_conditions": [
            "headers-footers-preserved",
            "section-breaks-preserved",
            "heading-style-mapped-to-template",
            "prototype-driven-rendering-used-for-paragraph-blocks",
            "no-template-body-residue-inside-replaced-range",
            "toc-fields-preserved-or-rewritten-for-refresh",
            "replace-range-operates-on-direct-body-children",
        ],
        "execution_strategy": "officecli-operation-graph",
        "execution_artifacts": {
            "template_profile": str(run_dir / "template_profile.json"),
            "content_ast": str(run_dir / "content_ast.json"),
            "execution_plan": str(run_dir / "execution_plan.json"),
        },
        "template_guardrails": template_guardrails,
        "semantic_grounding": {
            key: value
            for key, value in {
                "normalized_markdown": existing_artifacts.get("normalized_markdown"),
                "markitdown_style_map": existing_artifacts.get("markitdown_style_map"),
                "sample_content": existing_artifacts.get("sample_content"),
                "sample_outline": existing_artifacts.get("sample_outline"),
                "source_render_window": source_render_window,
            }.items()
            if value
        },
        "status": "ready-for-execution" if normalized_mode == "preserve-template-scaffold" and replace_ranges_resolved and not blocking_reasons else "blocked",
        "error_contract": {
            "blocked_means_do_not_build": True,
            "builder_must_write_blocked_report": True,
            "qa_must_fail_if_build_runs_without_selected_resolved_range": True,
        },
        "planner_diagnostics": {
            "source_zone_markers": source_markers,
            "range_reason": range_reason,
            "replace_range_resolved": replace_ranges_resolved,
            "selected_range_remove_count": template_guardrails.get("selected_range_remove_count", 0),
            "selected_range_remove_ratio": template_guardrails.get("selected_range_remove_ratio", 0.0),
            "risk_flags": template_guardrails.get("risk_flags", []),
            "source_render_window": source_render_window,
        },
        "steps": [
            "Đọc content_ast.json từ parser token-based",
            "Dùng sample_content.md trích từ template để nhận diện prefix front matter của source đã được scaffold cover sẵn",
            "Dùng template_profile.json để resolve style graph, prototype catalog và direct-body replace ranges",
            "Chọn selected_replace_range theo outline nguồn và preserve zones của template",
            "Compile execution_plan.json thành operation graph deterministic",
            "Thực thi remove trực tiếp trên direct body children, sau đó render block bằng prototype phù hợp",
            "Rewrite TOC field và kiểm QA dependency graph sau build",
        ],
        "blocking_reasons": blocking_reasons,
    }
    run_state = {
        **existing_run_state,
        "mode_requested": args.mode,
        "mode": normalized_mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "preserve": preserve_defaults,
        "replace_ranges": replace_ranges,
        "selected_replace_range": selected_range,
        "artifacts": {
            **existing_artifacts,
            "content_ast": str(run_dir / "content_ast.json"),
            "content_outline": str(run_dir / "content_outline.json"),
            "template_profile": str(run_dir / "template_profile.json"),
            "plan": str(run_dir / "plan.json"),
            "execution_plan": str(run_dir / "execution_plan.json"),
        },
        "status": "planned" if plan["status"] == "ready-for-execution" else "blocked",
    }

    write_json(run_dir / "plan.json", plan)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()