from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import ensure_officecli_available, normalize_text, officecli_get, officecli_query, officecli_validate, officecli_view, read_json, write_json


SEMANTIC_RESIDUE = ["# ", "```", "{{", "Click to add text", "Lorem ipsum"]


def placeholder_map(results: list[dict]) -> dict[int, dict[str, dict]]:
    payload: dict[int, dict[str, dict]] = {}
    for result in results:
        path = str(result.get("path") or "")
        if not path.startswith("/slide["):
            continue
        slide_index = int(path.split("]", 1)[0].split("[")[-1])
        keys: list[str] = []
        if "/placeholder[" in path:
            keys.append(path.split("/placeholder[", 1)[1].split("]", 1)[0])
        placeholder_format = result.get("format", {})
        ph_type = normalize_text(str(placeholder_format.get("phType") or ""))
        if placeholder_format.get("isTitle") is True or ph_type in {"TITLE", "CTRTITLE"}:
            keys.append("title")
        elif ph_type in {"BODY", "OBJ"}:
            keys.append("body")
        elif ph_type == "SUBTITLE":
            keys.append("subtitle")
        elif ph_type in {"DT", "DATE"}:
            keys.append("date")
        elif ph_type in {"FTR", "FOOTER"}:
            keys.append("footer")
        elif ph_type in {"SLDNUM", "SLIDENUM"}:
            keys.append("slidenum")
        for key in dict.fromkeys([key for key in keys if key]):
            payload.setdefault(slide_index, {})[key] = result
    return payload


def slide_texts(text_payload: dict) -> dict[int, list[str]]:
    return {
        int(slide.get("index", 0)): [str(text).strip() for text in slide.get("texts", []) if str(text).strip()]
        for slide in text_payload.get("slides", [])
    }


def title_text_from_placeholders(placeholders: dict[int, dict[str, dict]], slide_index: int) -> str:
    slide_placeholders = placeholders.get(slide_index, {})
    title_payload = slide_placeholders.get("title")
    if title_payload is None:
        return ""
    return str(title_payload.get("text") or "").strip()


def normalize_base_title(value: str) -> str:
    return normalize_text(re.sub(r"\s*\(TI[ẾE]P\s*\d+\)\s*$", "", value, flags=re.IGNORECASE))


def layout_mapping_ok(plan: dict) -> bool:
    return bool(plan.get("layout_mapping", {}).get("content_layout")) and all(bool(item.get("layout")) for item in plan.get("slide_specs", []))


def content_slide_indices(plan: dict) -> list[int]:
    start = int(plan.get("content_range", {}).get("target_start_index") or 2)
    return list(range(start, start + len(plan.get("slide_specs", []))))


def max_line_count_ok(plan: dict) -> bool:
    limit = int(plan.get("limits", {}).get("body_line_limit") or 0)
    return all(len(item.get("body_lines", [])) <= limit for item in plan.get("slide_specs", []))


def residue_hits(markers: list[str], content_text: str) -> list[str]:
    normalized_content = normalize_text(content_text)
    return [marker for marker in markers if marker and marker in normalized_content]


def allowed_plan_markers(plan: dict) -> set[str]:
    allowed: set[str] = set()
    for item in [plan.get("presentation_title", "")]:
        normalized = normalize_text(str(item or ""))
        if normalized:
            allowed.add(normalized)
    for slide in plan.get("slide_specs", []):
        title = normalize_text(str(slide.get("title") or ""))
        if title:
            allowed.add(title)
        for line in slide.get("body_lines", []):
            normalized = normalize_text(str(line or ""))
            if normalized:
                allowed.add(normalized)
    return allowed


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh qa_report.json cho pipeline PPTX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_state = read_json(run_dir / "run.json")
    plan = read_json(run_dir / "plan.json")
    build_report = read_json(run_dir / "build_report.json") if (run_dir / "build_report.json").exists() else {}
    template_profile = read_json(run_dir / "template_profile.json")
    target_file = Path(run_state.get("target_file"))
    target_exists = target_file.exists()

    officecli_version = ensure_officecli_available() if target_exists else None
    validate_payload = officecli_validate(target_file) if target_exists else {"success": False}
    root_payload = officecli_get(target_file, "/", depth=1) if target_exists else {}
    placeholder_results = officecli_query(target_file, "placeholder") if target_exists else []
    master_results = officecli_query(target_file, "slidemaster") if target_exists else []
    notes_results = officecli_query(target_file, "notes") if target_exists else []
    issues_payload = officecli_view(target_file, "issues") if target_exists else {"issues": []}
    text_payload = officecli_view(target_file, "text") if target_exists else {"slides": []}

    placeholders = placeholder_map(placeholder_results)
    texts_by_slide = slide_texts(text_payload)
    generated_indices = content_slide_indices(plan)
    generated_titles = [title_text_from_placeholders(placeholders, index) for index in generated_indices]
    planned_titles = [str(item.get("title") or "") for item in plan.get("slide_specs", [])]
    root_format = root_payload.get("results", [{}])[0].get("format", {}) if root_payload.get("results") else {}
    normalized_document_text = "\n".join(text for values in texts_by_slide.values() for text in values)
    normalized_content_text = "\n".join(text for index, values in texts_by_slide.items() if index in generated_indices for text in values)
    residue_markers = template_profile.get("residue_markers", [])
    allowed_markers = allowed_plan_markers(plan)
    severe_issues = [issue for issue in issues_payload.get("issues", []) if int(issue.get("severity", 0)) >= 2]

    title_slide_index = template_profile.get("title_slide", {}).get("index")
    title_slide_ok = bool(title_slide_index) and title_slide_index in texts_by_slide
    title_placeholder_keys = set(template_profile.get("title_slide", {}).get("semantic_placeholder_paths", {}).keys())
    title_placeholder_ok = title_placeholder_keys.issubset(set(placeholders.get(int(title_slide_index or 0), {}).keys())) if title_slide_index else False
    prototype_placeholders = set(plan.get("layout_mapping", {}).get("prototype_placeholders", []))
    content_placeholders_ok = all(prototype_placeholders.issubset(set(placeholders.get(index, {}).keys())) for index in generated_indices)

    masters_and_layouts_preserved = (
        len(master_results) >= int(template_profile.get("presentation_profile", {}).get("master_count") or 0)
        and root_format.get("slideWidth") == template_profile.get("presentation_profile", {}).get("slide_width")
        and root_format.get("slideHeight") == template_profile.get("presentation_profile", {}).get("slide_height")
        and root_format.get("theme.name") == template_profile.get("presentation_profile", {}).get("theme", {}).get("theme.name")
    )
    notes_ok = int(template_profile.get("presentation_profile", {}).get("notes_count") or 0) == 0 or len(notes_results) >= int(template_profile.get("presentation_profile", {}).get("notes_count") or 0)
    replace_ranges_resolved = any(item.get("status") == "resolved" for item in plan.get("replace_ranges", []))
    slide_order_matches_source_outline = [normalize_text(item) for item in generated_titles] == [normalize_text(item) for item in planned_titles]
    layout_ok = layout_mapping_ok(plan)
    filtered_residue_hits = [
        marker
        for marker in residue_hits(residue_markers, normalized_content_text)
        if marker not in allowed_markers and not any(marker in allowed or allowed in marker for allowed in allowed_markers)
    ]
    residue_ok = not filtered_residue_hits
    semantic_ok = all(pattern not in normalized_document_text for pattern in SEMANTIC_RESIDUE)
    overflow_ok = max_line_count_ok(plan) and not severe_issues
    duplicate_titles = []
    for previous, current in zip(generated_titles, generated_titles[1:]):
        if normalize_base_title(previous) == normalize_base_title(current) and "TIEP" not in normalize_text(current):
            duplicate_titles.append(current)
    duplicate_ok = not duplicate_titles

    qa_report = {
        "status": "passed" if all([
            target_exists,
            bool(validate_payload.get("success")),
            title_slide_ok,
            title_placeholder_ok,
            masters_and_layouts_preserved,
            content_placeholders_ok,
            notes_ok,
            replace_ranges_resolved,
            layout_ok,
            slide_order_matches_source_outline,
            residue_ok,
            semantic_ok,
            overflow_ok,
            duplicate_ok,
        ]) else "failed",
        "officecli_version": officecli_version,
        "required_preserve": plan.get("preserve", []),
        "checks": {
            "validate": bool(validate_payload.get("success")),
            "title_slide": title_slide_ok,
            "title_placeholder_bindings": title_placeholder_ok,
            "masters_and_layouts": masters_and_layouts_preserved,
            "content_placeholder_bindings": content_placeholders_ok,
            "notes_pages": notes_ok,
            "replace_ranges_resolved": replace_ranges_resolved,
            "layout_mapping_resolved": layout_ok,
            "slide_order_matches_source_outline": slide_order_matches_source_outline,
            "no_template_slide_residue": residue_ok,
            "no_semantic_residue": semantic_ok,
            "overflow_or_severe_issues": overflow_ok,
            "duplicate_titles": duplicate_ok,
        },
        "generated_slide_count": len(generated_indices),
        "planned_slide_count": len(plan.get("slide_specs", [])),
        "generated_titles": generated_titles,
        "planned_titles": planned_titles,
        "residue_hits": filtered_residue_hits,
        "duplicate_titles": duplicate_titles,
        "severe_issue_count": len(severe_issues),
        "message": "QA đã kiểm package, scaffold, layout, residue và semantic gate cho contract preserve-template-scaffold của PPTX.",
    }

    run_state["artifacts"]["qa_report"] = str(run_dir / "qa_report.json")
    run_state["status"] = "ready" if qa_report["status"] == "passed" else "needs-repair"
    write_json(run_dir / "qa_report.json", qa_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()