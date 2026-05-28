from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from officecli_native import (
    ensure_officecli_available,
    normalize_text,
    officecli_add,
    officecli_close,
    officecli_open,
    officecli_query,
    officecli_remove,
    officecli_save,
    officecli_set,
    read_json,
    write_json,
)


def semantic_keys(result: dict) -> list[str]:
    keys: list[str] = []
    path = str(result.get("path") or "")
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
    return list(dict.fromkeys([key for key in keys if key]))


def placeholder_map(results: list[dict]) -> dict[int, dict[str, dict]]:
    payload: dict[int, dict[str, dict]] = {}
    for result in results:
        path = str(result.get("path") or "")
        if not path.startswith("/slide["):
            continue
        slide_index = int(path.split("]", 1)[0].split("[")[-1])
        for key in semantic_keys(result):
            payload.setdefault(slide_index, {})[key] = result
    return payload


def cleanup_markers(template_profile: dict) -> set[str]:
    markers = set(template_profile.get("residue_markers", []))
    ignored = {"", "TRONG-NGHIA NGUYEN", "<#>", "‹#›"}
    for key in ["content_prototype", "closing_slide"]:
        profile = template_profile.get(key, {})
        texts = profile.get("texts") or profile.get("profile", {}).get("texts", [])
        for text in texts:
            normalized = normalize_text(str(text or ""))
            if normalized and normalized not in ignored:
                markers.add(normalized)
    return markers


def cleanup_generated_slide(target_file: Path, slide_index: int, markers: set[str]) -> None:
    for shape in officecli_query(target_file, f"slide[{slide_index}] > shape"):
        shape_format = shape.get("format", {})
        ph_type = normalize_text(str(shape_format.get("phType") or ""))
        if shape_format.get("isTitle") is True or ph_type in {"TITLE", "CTRTITLE", "BODY", "OBJ", "DT", "DATE", "FTR", "FOOTER", "SLDNUM", "SLIDENUM"}:
            continue
        normalized_text = normalize_text(str(shape.get("text") or ""))
        if normalized_text and normalized_text in markers:
            officecli_remove(target_file, str(shape.get("path")))


def clone_content_slides(target_file: Path, prototype_path: str, slide_count: int, insert_before_path: str | None) -> None:
    for _ in range(slide_count):
        officecli_add(target_file, "/", from_path=prototype_path, before=insert_before_path)


def remove_original_range(target_file: Path, remove_paths: list[str]) -> None:
    for path in reversed(remove_paths):
        officecli_remove(target_file, path)


def fill_slide(target_file: Path, slide_index: int, slide_spec: dict, placeholders: dict[int, dict[str, dict]]) -> None:
    slide_placeholders = placeholders.get(slide_index, {})
    title_path = slide_placeholders.get("title", {}).get("path")
    body_path = slide_placeholders.get("body", {}).get("path")
    if title_path:
        officecli_set(target_file, title_path, props={"text": slide_spec.get("title", "")})
    if body_path:
        officecli_set(target_file, body_path, props={"text": "\n".join(slide_spec.get("body_lines", []))})
    if slide_spec.get("notes"):
        officecli_set(target_file, f"/slide[{slide_index}]", props={"notes": slide_spec["notes"]})


def update_title_slide(target_file: Path, title_update: dict) -> bool:
    changed = False
    if title_update.get("title_path") and title_update.get("title_text"):
        officecli_set(target_file, title_update["title_path"], props={"text": title_update["title_text"]})
        changed = True
    if title_update.get("subtitle_path") and title_update.get("subtitle_text"):
        officecli_set(target_file, title_update["subtitle_path"], props={"text": title_update["subtitle_text"]})
        changed = True
    return changed


def build_deck(template_file: Path, target_file: Path, plan: dict, template_profile: dict) -> dict:
    shutil.copy2(template_file, target_file)

    resolved_range = next(item for item in plan.get("replace_ranges", []) if item.get("status") == "resolved")
    slide_specs = plan.get("slide_specs", [])
    content_start_index = int(plan.get("content_range", {}).get("target_start_index") or 2)
    residue_cleanup = cleanup_markers(template_profile)

    officecli_open(target_file)
    try:
        clone_content_slides(
            target_file,
            prototype_path=resolved_range.get("prototype_slide_path"),
            slide_count=len(slide_specs),
            insert_before_path=resolved_range.get("insert_before_path"),
        )
        remove_original_range(target_file, list(resolved_range.get("remove_paths", [])))
        title_slide_updated = update_title_slide(target_file, plan.get("title_slide_update", {}))
        placeholders = placeholder_map(officecli_query(target_file, "placeholder"))
        for offset, slide_spec in enumerate(slide_specs, start=content_start_index):
            fill_slide(target_file, offset, slide_spec, placeholders)
            cleanup_generated_slide(target_file, offset, residue_cleanup)
        officecli_save(target_file)
    finally:
        officecli_close(target_file)

    return {
        "cloned_slide_count": len(slide_specs),
        "removed_slide_count": len(resolved_range.get("remove_paths", [])),
        "generated_slide_titles": [item.get("title") for item in slide_specs],
        "content_start_index": content_start_index,
        "title_slide_updated": title_slide_updated,
        "body_replaced": bool(slide_specs),
        "resident_mode": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh build_report.json cho pipeline PPTX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    plan = read_json(run_dir / "plan.json")
    run_state = read_json(run_dir / "run.json")
    template_profile = read_json(run_dir / "template_profile.json")
    target_file = Path(plan.get("target_file"))
    template_file = Path(plan.get("template_file"))
    officecli_version = ensure_officecli_available()
    resolved_range = next((item for item in plan.get("replace_ranges", []) if item.get("status") == "resolved"), None)

    if plan.get("mode") != "preserve-template-scaffold":
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Script build hiện chỉ cho phép mode preserve-template-scaffold trong workflow PPTX an toàn.",
            "body_replaced": False,
            "officecli_version": officecli_version,
        }
        run_state["status"] = "blocked"
    elif resolved_range is None or not plan.get("slide_specs"):
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Không resolve được replace_ranges hoặc slide_specs nên build bị chặn để tránh làm mất scaffold của template.",
            "body_replaced": False,
            "officecli_version": officecli_version,
        }
        run_state["status"] = "blocked"
    else:
        replacement_stats = build_deck(template_file, target_file, plan, template_profile)
        build_report = {
            "status": "completed",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "officecli_version": officecli_version,
            "replace_range": resolved_range,
            "preserve": plan.get("preserve", []),
            "layout_mapping": plan.get("layout_mapping", {}),
            "template_master_count": template_profile.get("presentation_profile", {}).get("master_count", 0),
            "template_layout_count": template_profile.get("presentation_profile", {}).get("layout_count", 0),
            **replacement_stats,
            "message": "Đã thay vùng slide nội dung bằng clone-fill-remove theo bounded range và giữ scaffold của template ở ngoài phạm vi thay.",
        }
        run_state["status"] = "built"

    run_state["artifacts"]["build_report"] = str(run_dir / "build_report.json")
    write_json(run_dir / "build_report.json", build_report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()