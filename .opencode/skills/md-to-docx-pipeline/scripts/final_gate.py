#!/usr/bin/env python3
"""final_gate.py — code-level final gate. Runs AFTER all phases complete.

Checks ALL required artifacts exist and pass quality thresholds.
Returns `passed: true` only if every check succeeds.
This replaces the prompt-based final gate in orchestrator.md.

Usage:
    python3 final_gate.py --run-dir <path>
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from officecli_native import read_json, write_json


REQUIRED_ARTIFACTS = [
    "execution_ops.json",
    "execution_ops_validation.json",
    "planning_report.json",
    "execute_ops_report.json",
    "qa_report.json",
    "review_report.json",
    "post_process_report.json",
    "source_packet.json",
    "style_map.json",
    "replace_range.json",
]

OPTIONAL_ARTIFACTS = [
    "docx_inspect_output.json",
    "insert_plan_scaffold.json",
]


def check_artifact_exists(run_dir: Path, name: str) -> bool:
    return (run_dir / name).exists()


def check_source_coverage(run_dir: Path) -> dict:
    """Check that all source blocks were inserted into output."""
    result = {"ok": False, "source_blocks": 0, "matched_blocks": 0, "missing_blocks": []}

    source_packet_path = run_dir / "source_packet.json"
    if not source_packet_path.exists():
        result["error"] = "source_packet.json not found"
        return result

    source_packet = read_json(source_packet_path)
    blocks = source_packet.get("blocks", [])
    result["source_blocks"] = len(blocks)

    exec_ops_path = run_dir / "execution_ops.json"
    if not exec_ops_path.exists():
        result["error"] = "execution_ops.json not found"
        return result

    exec_ops = read_json(exec_ops_path)
    ops = exec_ops.get("ops", [])

    inserted_block_ids = {
        op.get("source_block_id", "") for op in ops
        if op.get("op") in ("insert_paragraph_after", "insert_paragraph_before")
        and op.get("source_block_id")
    }

    all_block_ids = {b.get("id", "") for b in blocks if b.get("id")}
    missing = all_block_ids - inserted_block_ids - {""}
    result["matched_blocks"] = len(inserted_block_ids & all_block_ids)
    result["missing_blocks"] = sorted(missing)
    result["ok"] = len(missing) == 0

    return result


def check_placeholder_leak(run_dir: Path) -> dict:
    """Check that no placeholder text remains in output."""
    result = {"ok": True, "leaks": []}

    qa_path = run_dir / "qa_report.json"
    if qa_path.exists():
        qa = read_json(qa_path)
        placeholder_ok = qa.get("placeholder_ok")
        if placeholder_ok is False:
            result["ok"] = False
            result["leaks"] = qa.get("placeholder_leaks", [])
        return result

    result["ok"] = False
    result["error"] = "qa_report.json not found"
    return result


def check_references_ok(run_dir: Path) -> dict:
    """Check that reference section was preserved."""
    result = {"ok": True}

    qa_path = run_dir / "qa_report.json"
    if qa_path.exists():
        qa = read_json(qa_path)
        refs_ok = qa.get("references_ok")
        if refs_ok is False:
            result["ok"] = False
            result["reason"] = "References check failed in QA"
        return result

    result["ok"] = False
    result["error"] = "qa_report.json not found"
    return result


def check_front_matter_preserved(run_dir: Path) -> dict:
    """Check front matter was not accidentally removed."""
    result = {"ok": True}

    ops_path = run_dir / "execution_ops.json"
    scaffold_path = run_dir / "insert_plan_scaffold.json"

    if not ops_path.exists():
        result["ok"] = False
        result["error"] = "execution_ops.json not found"
        return result

    exec_ops = read_json(ops_path)
    ops = exec_ops.get("ops", [])

    if scaffold_path.exists():
        scaffold = read_json(scaffold_path)
        front_matter_boundary = scaffold.get("front_matter_last_para_id", "")
        front_matter = scaffold.get("front_matter", {})

        # Check no remove op targets front matter
        remove_paths = [
            op.get("path", "") for op in ops if op.get("op") == "remove"
        ]
        for rpath in remove_paths:
            if front_matter_boundary and front_matter_boundary in str(rpath):
                result["ok"] = False
                result["reason"] = f"Remove op targets front matter boundary: {rpath}"
                return result

    return result


def check_toc_ok(run_dir: Path) -> dict:
    """Check TOC was refreshed or marked dirty."""
    result = {"ok": False, "toc_refreshed": False, "toc_marked_dirty": False}

    pp_path = run_dir / "post_process_report.json"
    if pp_path.exists():
        pp = read_json(pp_path)
        result["toc_refreshed"] = pp.get("toc_refreshed", False)
        result["toc_marked_dirty"] = pp.get("toc_marked_dirty", False)
        result["ok"] = result["toc_refreshed"] or result["toc_marked_dirty"]
        return result

    result["error"] = "post_process_report.json not found"
    return result


def check_review_passed(run_dir: Path) -> dict:
    """Check that reviewer passed the output."""
    result = {"ok": False, "passed": False}

    review_path = run_dir / "review_report.json"
    if review_path.exists():
        review = read_json(review_path)
        result["passed"] = review.get("passed", False)
        result["ok"] = result["passed"]
        if not result["passed"]:
            result["issues"] = review.get("issues", [])
        return result

    result["error"] = "review_report.json not found"
    return result


def check_ops_applied(run_dir: Path) -> dict:
    """Check that ops were applied successfully."""
    result = {"ok": False, "succeeded": 0, "failed": 0}

    report_path = run_dir / "execute_ops_report.json"
    if report_path.exists():
        report = read_json(report_path)
        result["succeeded"] = report.get("succeeded", 0)
        result["failed"] = report.get("failed", 0)
        result["ok"] = result["failed"] == 0
        return result

    result["error"] = "execute_ops_report.json not found"
    return result


def run_final_gate(run_dir: Path) -> dict:
    """Run all final gate checks. Returns gate verdict."""
    artifacts: dict[str, bool] = {}
    for name in REQUIRED_ARTIFACTS:
        artifacts[name] = check_artifact_exists(run_dir, name)
    for name in OPTIONAL_ARTIFACTS:
        artifacts[name] = check_artifact_exists(run_dir, name)

    coverage = check_source_coverage(run_dir)
    placeholder = check_placeholder_leak(run_dir)
    references = check_references_ok(run_dir)
    front_matter = check_front_matter_preserved(run_dir)
    toc = check_toc_ok(run_dir)
    review = check_review_passed(run_dir)
    ops_applied = check_ops_applied(run_dir)

    all_artifacts_present = all(artifacts.get(a, False) for a in REQUIRED_ARTIFACTS)

    checks = {
        "all_required_artifacts_present": all_artifacts_present,
        "source_coverage_ok": coverage.get("ok", False),
        "placeholder_leak_ok": placeholder.get("ok", False),
        "references_ok": references.get("ok", False),
        "front_matter_preserved": front_matter.get("ok", False),
        "toc_ok": toc.get("ok", False),
        "review_passed": review.get("ok", False),
        "ops_applied_ok": ops_applied.get("ok", False),
    }

    all_checks_passed = all(checks.values())

    return {
        "passed": all_checks_passed,
        "required_artifacts": artifacts,
        "checks": checks,
        "details": {
            "source_coverage": coverage,
            "placeholder_leak": placeholder,
            "references": references,
            "front_matter": front_matter,
            "toc": toc,
            "review": review,
            "ops_applied": ops_applied,
        },
        "missing_artifacts": [a for a in REQUIRED_ARTIFACTS if not artifacts.get(a, False)],
        "failed_checks": [k for k, v in checks.items() if not v],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="final_gate: code-level final gate — no LLM involvement."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--output", default=None, help="Output path (default: <run-dir>/final_gate.json)")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"[final_gate] ERROR: run_dir not found: {run_dir}")
        raise SystemExit(1)

    gate = run_final_gate(run_dir)

    output_path = Path(args.output) if args.output else run_dir / "final_gate.json"
    write_json(output_path, gate)

    if gate["passed"]:
        print("[final_gate] ✅ PASSED — All checks passed")
    else:
        print(f"[final_gate] ❌ FAILED — {len(gate['failed_checks'])} check(s) failed")
        for check in gate["failed_checks"]:
            print(f"  - {check}")
        if gate["missing_artifacts"]:
            print(f"  Missing artifacts: {gate['missing_artifacts']}")

    print(f"[final_gate] Output: {output_path}")

    if not gate["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
