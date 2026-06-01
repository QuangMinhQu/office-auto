from __future__ import annotations

import argparse
from pathlib import Path

from officecli_native import read_json, write_json
from plan_mapping import assess_template_guardrails


def count_missing_prototypes(prototype_catalog: dict) -> dict:
    required_roles = ["h1", "h2", "h3", "body", "list", "reference"]
    missing = [role for role in required_roles if role not in prototype_catalog or not prototype_catalog.get(role)]
    return {
        "required_role_count": len(required_roles),
        "missing_roles": missing,
        "missing_count": len(missing),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-flight template suitability report for multi-topology pipeline.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    profile = read_json(run_dir / "template_profile.json")
    selected_range = None
    for candidate in profile.get("document_profile", {}).get("replace_range_candidates", []):
        if candidate.get("status") == "resolved":
            selected_range = candidate
            break

    guardrails = assess_template_guardrails(profile, selected_range)
    topology = profile.get("topology") or {}
    prototype_catalog = profile.get("prototype_catalog") or {}
    prototype_health = count_missing_prototypes(prototype_catalog)

    suitability = {
        "status": "ready" if guardrails.get("build_allowed", False) else "needs-template-adjustment",
        "topology": {
            "recommended_path": topology.get("recommended_path"),
            "reason": topology.get("recommended_path_reason"),
            "has_toc_field": topology.get("has_toc_field"),
            "has_pageref": topology.get("has_pageref"),
            "has_tables": topology.get("has_tables"),
            "has_multiple_sections": topology.get("has_multiple_sections"),
            "section_count": topology.get("section_count"),
            "style_discipline_ratio": topology.get("style_discipline_ratio"),
        },
        "replace_range": {
            "selected_name": selected_range.get("name") if selected_range else None,
            "status": selected_range.get("status") if selected_range else "missing",
            "remove_count": len((selected_range or {}).get("remove_paths", [])),
        },
        "guardrails": guardrails,
        "prototype_health": prototype_health,
        "recommendations": [],
    }

    recommendations: list[str] = []
    if prototype_health["missing_count"] > 0:
        recommendations.append("Add explicit prototype examples or style_spec mappings for missing semantic roles.")
    if "whole-body-rewrite" in guardrails.get("risk_flags", []):
        recommendations.append("Avoid whole-body delete strategy; use structural_preserve or hybrid bounded replacement.")
    if topology.get("recommended_path") == "semantic_style" and topology.get("style_discipline_ratio", 0) < 0.85:
        recommendations.append("Style discipline is weak; switch to hybrid mode and rely on structure-aware replacement.")
    if topology.get("recommended_path") in {"structural_preserve", "hybrid"}:
        recommendations.append("Preserve TOC/bookmarks/sections and only mutate selected replace ranges.")

    suitability["recommendations"] = recommendations

    report_file = run_dir / "template_suitability_report.json"
    write_json(report_file, suitability)

    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    run_state.setdefault("artifacts", {})["template_suitability_report"] = str(report_file)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()
