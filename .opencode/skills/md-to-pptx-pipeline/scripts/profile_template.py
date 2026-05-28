from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import ensure_officecli_available, normalize_text, officecli_get, officecli_query, officecli_view, write_json


SLIDE_PATH_RE = re.compile(r"^/slide\[(\d+)\]")


def slide_index_from_path(path: str | None) -> int | None:
    if not path:
        return None
    match = SLIDE_PATH_RE.match(path)
    if match is None:
        return None
    return int(match.group(1))


def meaningful_texts(values: list[str]) -> list[str]:
    return [value.strip() for value in values if str(value).strip()]


def placeholder_key(result: dict) -> str:
    path = str(result.get("path") or "")
    match = re.search(r"/placeholder\[([^\]]+)\]", path)
    if match is not None:
        return match.group(1)
    ph_type = str(result.get("format", {}).get("phType") or "").strip()
    return ph_type or path


def build_placeholder_map(results: list[dict]) -> dict[int, dict[str, dict]]:
    payload: dict[int, dict[str, dict]] = {}
    for result in results:
        slide_index = slide_index_from_path(result.get("path"))
        if slide_index is None:
            continue
        payload.setdefault(slide_index, {})[placeholder_key(result)] = {
            "path": result.get("path"),
            "type": result.get("type"),
            "text": str(result.get("text") or ""),
            "format": result.get("format", {}),
        }
    return payload


def semantic_placeholder_paths(placeholders: dict[str, dict]) -> dict[str, str]:
    semantic: dict[str, str] = {}
    for key, value in placeholders.items():
        placeholder_format = value.get("format", {})
        path = value.get("path")
        ph_type = normalize_text(str(placeholder_format.get("phType") or ""))
        if placeholder_format.get("isTitle") is True or ph_type in {"TITLE", "CTRTITLE"}:
            semantic["title"] = path
        elif ph_type == "SUBTITLE":
            semantic["subtitle"] = path
        elif ph_type in {"DT", "DATE"}:
            semantic["date"] = path
        elif ph_type in {"FTR", "FOOTER"}:
            semantic["footer"] = path
        elif ph_type in {"SLDNUM", "SLIDENUM"}:
            semantic["slidenum"] = path
        elif ph_type in {"BODY", "OBJ"}:
            semantic["body"] = path
        elif key and key not in semantic:
            semantic[key] = path
    return semantic


def looks_like_title_slide(slide: dict, placeholders: dict[str, dict]) -> bool:
    if slide.get("index") != 1:
        return False
    layout_type = normalize_text(str(slide.get("layoutType") or slide.get("layout") or ""))
    if layout_type in {"TITLE", "CTR TITLE", "TITLE SLIDE"}:
        return True
    return any(str(item.get("format", {}).get("isTitle") or False).lower() == "true" for item in placeholders.values())


def looks_like_closing_slide(slide: dict, placeholders: dict[str, dict]) -> bool:
    texts = "\n".join(meaningful_texts(slide.get("texts", [])))
    normalized = normalize_text(texts)
    if any(token in normalized for token in ["THANK YOU", "CAM ON", "XIN CAM ON"]):
        return True
    title_text = str(placeholders.get("title", {}).get("text") or "").strip()
    body_text = str(placeholders.get("body", {}).get("text") or "").strip()
    return bool(title_text) and not body_text and len(meaningful_texts(slide.get("texts", []))) <= 4


def slide_profile(slide: dict, placeholders: dict[str, dict]) -> dict:
    return {
        "index": slide.get("index"),
        "path": slide.get("path"),
        "layout": slide.get("layout"),
        "layoutType": slide.get("layoutType"),
        "title": slide.get("title"),
        "texts": meaningful_texts(slide.get("texts", [])),
        "placeholder_keys": sorted(placeholders.keys()),
        "placeholder_paths": {key: value.get("path") for key, value in placeholders.items()},
    }


def content_residue_markers(slides: list[dict], start_index: int, end_index: int) -> list[str]:
    markers: set[str] = set()
    ignored = {
        "",
        "TIME-SERIES",
        "NỘI DUNG",
        "NOI DUNG",
        "THANK YOU!",
        "TRONG-NGHIA NGUYEN",
        "‹#›",
        "<#>",
    }
    for slide in slides:
        slide_index = int(slide.get("index", 0))
        if slide_index < start_index or slide_index > end_index:
            continue
        for text in slide.get("texts", []):
            normalized = normalize_text(text)
            if normalized in ignored or len(normalized) < 6:
                continue
            markers.add(normalized)
    return sorted(markers)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lập profile ngắn cho template PPTX.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    template_file = Path(args.template_file)
    run_dir = Path(args.run_dir)

    officecli_version = ensure_officecli_available()
    root_tree = officecli_get(template_file, "/", depth=2) or {}
    outline_view = officecli_view(template_file, "outline") or {}
    stats_view = officecli_view(template_file, "stats") or {}
    text_view = officecli_view(template_file, "text") or {}
    slide_results = officecli_query(template_file, "slide")
    placeholder_results = officecli_query(template_file, "placeholder")
    master_results = officecli_query(template_file, "slidemaster")
    notes_results = officecli_query(template_file, "notes")

    placeholder_map = build_placeholder_map(placeholder_results)
    slides = []
    for entry in (text_view.get("slides") or []):
        index = int(entry.get("index", 0))
        slide_meta = next((result for result in slide_results if slide_index_from_path(result.get("path")) == index), {})
        slides.append(
            {
                "index": index,
                "path": entry.get("path") or slide_meta.get("path"),
                "title": entry.get("title"),
                "layout": slide_meta.get("format", {}).get("layout"),
                "layoutType": slide_meta.get("format", {}).get("layoutType"),
                "texts": entry.get("texts") or [],
            }
        )

    title_slide_index = 1 if slides and looks_like_title_slide(slides[0], placeholder_map.get(1, {})) else None
    closing_slide_index = None
    if slides:
        last_slide = slides[-1]
        if looks_like_closing_slide(last_slide, placeholder_map.get(int(last_slide.get("index", 0)), {})):
            closing_slide_index = int(last_slide["index"])

    prototype_slide = next(
        (
            slide
            for slide in slides
            if int(slide.get("index", 0)) > (title_slide_index or 0)
            and (closing_slide_index is None or int(slide.get("index", 0)) < closing_slide_index)
            and {"title", "body"}.issubset(set(semantic_placeholder_paths(placeholder_map.get(int(slide.get("index", 0)), {})).keys()))
        ),
        None,
    )

    content_start = (title_slide_index or 0) + 1
    content_end = (closing_slide_index - 1) if closing_slide_index is not None else len(slides)
    replace_ranges = []
    if prototype_slide is not None and content_start <= content_end:
        remove_paths = [f"/slide[{index}]" for index in range(content_start, content_end + 1)]
        replace_ranges.append(
            {
                "name": "after-title-slide-to-before-closing-slide" if closing_slide_index is not None else "after-title-slide-to-end-of-main-story",
                "strategy": "after-title-slide-to-end-of-main-story",
                "status": "resolved",
                "slide_start_index": content_start,
                "slide_end_index": content_end,
                "remove_paths": remove_paths,
                "insert_before_path": f"/slide[{closing_slide_index}]" if closing_slide_index is not None else None,
                "prototype_slide_path": prototype_slide.get("path"),
                "prototype_layout": prototype_slide.get("layout"),
                "prototype_layout_type": prototype_slide.get("layoutType"),
                "preserves_title_slide": bool(title_slide_index),
                "preserves_closing_slide": bool(closing_slide_index),
            }
        )
    else:
        replace_ranges.append(
            {
                "name": "after-title-slide-to-end-of-main-story",
                "strategy": "after-title-slide-to-end-of-main-story",
                "status": "unresolved",
                "slide_start_index": None,
                "slide_end_index": None,
                "remove_paths": [],
                "insert_before_path": f"/slide[{closing_slide_index}]" if closing_slide_index is not None else None,
                "prototype_slide_path": None,
                "prototype_layout": None,
                "prototype_layout_type": None,
                "preserves_title_slide": bool(title_slide_index),
                "preserves_closing_slide": bool(closing_slide_index),
            }
        )

    presentation_format = root_tree.get("results", [{}])[0].get("format", {}) if root_tree.get("results") else {}
    preserve_defaults = [
        "title-slide",
        "slide-masters-and-layouts",
        "theme-colors-fonts",
        "slide-size-and-background",
        "placeholder-bindings",
        "layout-placeholder-regions-and-content-slots",
        "headers-footers-and-slide-numbers",
        "presentation-structure",
    ]
    if notes_results:
        preserve_defaults.append("notes-pages-if-present")

    payload = {
        "template_file": str(template_file),
        "officecli_version": officecli_version,
        "outline_snapshot": outline_view,
        "stats_snapshot": stats_view,
        "presentation_profile": {
            "slide_width": presentation_format.get("slideWidth"),
            "slide_height": presentation_format.get("slideHeight"),
            "default_font": presentation_format.get("defaultFont"),
            "theme": {key: value for key, value in presentation_format.items() if str(key).startswith("theme.")},
            "total_slides": len(slides),
            "master_count": len(master_results),
            "layout_count": sum(int(result.get("format", {}).get("layoutCount") or 0) for result in master_results),
            "notes_count": len(notes_results),
        },
        "preserve_defaults": sorted(set(preserve_defaults)),
        "title_slide": {
            "index": title_slide_index,
            "profile": slide_profile(slides[0], placeholder_map.get(1, {})) if title_slide_index and slides else None,
            "placeholder_paths": {key: value.get("path") for key, value in placeholder_map.get(1, {}).items()},
            "semantic_placeholder_paths": semantic_placeholder_paths(placeholder_map.get(1, {})),
        },
        "closing_slide": {
            "index": closing_slide_index,
            "profile": slide_profile(slides[-1], placeholder_map.get(int(slides[-1].get("index", 0)), {})) if closing_slide_index and slides else None,
        },
        "content_prototype": {
            "index": None if prototype_slide is None else prototype_slide.get("index"),
            "path": None if prototype_slide is None else prototype_slide.get("path"),
            "layout": None if prototype_slide is None else prototype_slide.get("layout"),
            "layout_type": None if prototype_slide is None else prototype_slide.get("layoutType"),
            "texts": [] if prototype_slide is None else prototype_slide.get("texts", []),
            "placeholder_paths": {} if prototype_slide is None else {key: value.get("path") for key, value in placeholder_map.get(int(prototype_slide.get("index", 0)), {}).items()},
            "semantic_placeholder_paths": {} if prototype_slide is None else semantic_placeholder_paths(placeholder_map.get(int(prototype_slide.get("index", 0)), {})),
            "required_placeholder_types": [] if prototype_slide is None else sorted(semantic_placeholder_paths(placeholder_map.get(int(prototype_slide.get("index", 0)), {})).keys()),
        },
        "slides": [slide_profile(slide, placeholder_map.get(int(slide.get("index", 0)), {})) for slide in slides],
        "replace_range_candidates": replace_ranges,
        "residue_markers": content_residue_markers(slides, content_start, content_end) if content_start <= content_end else [],
    }

    write_json(run_dir / "template_profile.json", payload)


if __name__ == "__main__":
    main()