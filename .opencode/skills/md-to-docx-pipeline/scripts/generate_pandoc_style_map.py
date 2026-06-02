from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import read_json, write_json


def profile_has_explicit_legal_prototypes(profile: dict) -> bool:
    prototype_catalog = profile.get("prototype_catalog") or {}
    fallback_roles = {
        "legal_chuong": "h1",
        "legal_dieu": "h2",
        "legal_khoan": "body",
    }

    for role, fallback_role in fallback_roles.items():
        prototype = prototype_catalog.get(role)
        if not isinstance(prototype, dict):
            continue
        fallback = prototype_catalog.get(fallback_role) or {}
        if prototype.get("path") and prototype.get("path") != fallback.get("path"):
            return True
        if prototype.get("style_id") and prototype.get("style_id") != fallback.get("style_id"):
            return True
    return False


def build_style_spec(profile: dict) -> dict:
    style_graph = profile.get("style_graph") or {}
    style_catalog = profile.get("style_catalog") or []
    prototype_catalog = profile.get("prototype_catalog") or {}

    outline_to_role = {
        "0": "h1",
        "1": "h2",
        "2": "h3",
    }
    role_map: dict[str, str] = {}

    catalog_by_id = {entry.get("style_id"): entry for entry in style_catalog if entry.get("style_id")}
    for style_id, graph_entry in style_graph.items():
        role = outline_to_role.get(str(graph_entry.get("resolved_outline_level")))
        if role and role not in role_map:
            role_map[role] = style_id

    body_proto = prototype_catalog.get("body") or {}
    role_map.setdefault("body", body_proto.get("style_id") or "Normal")
    role_map.setdefault("list", (prototype_catalog.get("list") or {}).get("style_id") or role_map["body"])
    role_map.setdefault("reference", (prototype_catalog.get("reference") or {}).get("style_id") or role_map["body"])
    role_map.setdefault("blockquote", (prototype_catalog.get("blockquote") or {}).get("style_id") or role_map["body"])
    role_map.setdefault("code", (prototype_catalog.get("code") or {}).get("style_id") or role_map["body"])
    role_map.setdefault("h1", (prototype_catalog.get("h1") or {}).get("style_id") or "Heading1")
    role_map.setdefault("h2", (prototype_catalog.get("h2") or {}).get("style_id") or "Heading2")
    role_map.setdefault("h3", (prototype_catalog.get("h3") or {}).get("style_id") or "Heading3")
    if profile_has_explicit_legal_prototypes(profile):
        role_map.setdefault("legal_chuong", (prototype_catalog.get("legal_chuong") or {}).get("style_id") or role_map["h1"])
        role_map.setdefault("legal_dieu", (prototype_catalog.get("legal_dieu") or {}).get("style_id") or role_map["h2"])
        role_map.setdefault("legal_khoan", (prototype_catalog.get("legal_khoan") or {}).get("style_id") or role_map["body"])

    return {
        "template_file": profile.get("template_file"),
        "style_map": role_map,
        "style_names": {
            role: (catalog_by_id.get(style_id, {}) or {}).get("name")
            for role, style_id in role_map.items()
        },
        "notes": [
            "Dùng styleId (không dùng display name) để tránh Word fallback về Normal.",
            "Pandoc input DOCX dùng -f docx+styles để giữ custom-style metadata khi roundtrip semantic QA.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh pandoc_style_spec.json từ template_profile.json.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    profile = read_json(run_dir / "template_profile.json")
    style_spec = build_style_spec(profile)

    output_file = run_dir / "pandoc_style_spec.json"
    write_json(output_file, style_spec)

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["pandoc_style_spec"] = str(output_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
