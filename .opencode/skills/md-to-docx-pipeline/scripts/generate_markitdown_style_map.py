from __future__ import annotations

import argparse
import re
from pathlib import Path

from officecli_native import read_json, write_json


ROLE_TARGETS = {
    "h1": "h1:fresh",
    "h2": "h2:fresh",
    "h3": "h3:fresh",
    "body": "p:fresh",
    "reference": "p:fresh",
    "blockquote": "blockquote:fresh",
    "code": "pre:fresh",
}
OUTLINE_TARGETS = {
    "0": "h1:fresh",
    "1": "h2:fresh",
    "2": "h3:fresh",
}
HEADING_TARGETS = tuple(OUTLINE_TARGETS.values())
BODY_LIKE_TARGETS = {"p:fresh"}
STYLE_ID_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")


def escape_style_name(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def add_mapping(lines: list[str], seen: set[str], matcher: str | None, target: str | None) -> None:
    if not matcher or not target:
        return
    line = f"{matcher} => {target}"
    if line in seen:
        return
    seen.add(line)
    lines.append(line)


def style_name_matcher(style_name: str | None) -> str | None:
    if not style_name:
        return None
    return f"p[style-name='{escape_style_name(style_name)}']"


def style_id_matcher(style_id: str | None) -> str | None:
    if not style_id or not STYLE_ID_PATTERN.match(style_id):
        return None
    return f"p.{style_id}"


def resolve_style_name_target(targets: list[str]) -> str | None:
    unique_targets = list(dict.fromkeys(targets))
    if len(unique_targets) == 1:
        return unique_targets[0]
    for target in unique_targets:
        if target in BODY_LIKE_TARGETS:
            return target
    non_heading_targets = [target for target in unique_targets if target not in HEADING_TARGETS]
    if len(non_heading_targets) == 1:
        return non_heading_targets[0]
    heading_targets = [target for target in unique_targets if target in HEADING_TARGETS]
    if len(heading_targets) == 1 and not non_heading_targets:
        return heading_targets[0]
    return None


def build_style_map_text(profile: dict) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    style_graph = profile.get("style_graph", {})
    style_name_targets: dict[str, list[str]] = {}

    for entry in profile.get("style_catalog", []):
        style_id = entry.get("style_id")
        graph_entry = style_graph.get(style_id or "", {})
        resolved_outline = graph_entry.get("resolved_outline_level")
        target = OUTLINE_TARGETS.get(str(resolved_outline))
        if target:
            add_mapping(lines, seen, style_id_matcher(style_id), target)
            matcher = style_name_matcher(entry.get("name"))
            if matcher:
                style_name_targets.setdefault(matcher, []).append(target)

    for role, target in ROLE_TARGETS.items():
        prototype = (profile.get("prototype_catalog") or {}).get(role, {})
        matcher = style_name_matcher(prototype.get("style_name"))
        if matcher:
            style_name_targets.setdefault(matcher, []).append(target)

    for matcher, targets in style_name_targets.items():
        add_mapping(lines, seen, matcher, resolve_style_name_target(targets))

    return "\n".join(lines) + ("\n" if lines else "")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh markitdown_style_map.txt từ template_profile.json.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    profile = read_json(run_dir / "template_profile.json")
    style_map_text = build_style_map_text(profile)
    output_file = run_dir / "markitdown_style_map.txt"
    output_file.write_text(style_map_text, encoding="utf-8")

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["markitdown_style_map"] = str(output_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()