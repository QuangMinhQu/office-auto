#!/usr/bin/env python3
"""final_gate.py — code-level final gate. Runs AFTER all phases complete.

Checks ALL required artifacts exist and pass quality thresholds.
Now supports manifest-based checks with SHA256 verification and event-sourced state awareness.
Returns `passed: true` only if every check succeeds.
This replaces the prompt-based final gate in orchestrator.md.

Usage:
    python3 final_gate.py --run-dir <path>
    python3 final_gate.py --run-dir <path> --check-manifest
    python3 final_gate.py --run-dir <path> --check-manifest --check-event-log
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from typing import Any, Optional

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

MANIFEST_FILE = "artifacts.json"
EVENT_LOG_FILE = "events.jsonl"


def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def check_artifact_exists(run_dir: Path, name: str) -> bool:
    """Check if artifact file exists on disk."""
    return (run_dir / name).exists()


def load_manifest(run_dir: Path) -> Optional[dict]:
    """Load the artifact manifest if present."""
    manifest_path = run_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return None
    return read_json(manifest_path)


def check_artifact_via_manifest(run_dir: Path, name: str) -> dict:
    """Check artifact using manifest: file exists + manifest entry + checksum match."""
    result = {"name": name, "found_on_disk": False, "in_manifest": False, "checksum_match": None, "ok": False}

    file_path = run_dir / name
    result["found_on_disk"] = file_path.exists()

    manifest = load_manifest(run_dir)
    if manifest is None:
        result["error"] = "No manifest found"
        return result

    entries = manifest.get("entries", {})
    entry = entries.get(name)
    if entry is None:
        # Try matching by basename without extension
        key = name.replace(".json", "")
        entry = entries.get(key)

    result["in_manifest"] = entry is not None

    if entry and file_path.exists():
        expected_sha = entry.get("sha256", "")
        actual_sha = compute_sha256(file_path)
        result["checksum_match"] = expected_sha == actual_sha
        result["expected_sha256"] = expected_sha[:12] + "..." if expected_sha else "missing"
        result["actual_sha256"] = actual_sha[:12] + "..."
        result["producer"] = entry.get("created_by", "unknown")
        result["phase"] = entry.get("phase", "unknown")

    result["ok"] = result["found_on_disk"] and result["in_manifest"] and result["checksum_match"] is not False
    return result


def load_event_log(run_dir: Path) -> list[dict]:
    """Load and parse the append-only event log."""
    events_path = run_dir / EVENT_LOG_FILE
    if not events_path.exists():
        return []
    events = []
    for line in events_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                events.append(__import__("json").loads(line))
            except Exception:
                pass
    return events


def check_event_log_validity(run_dir: Path) -> dict:
    """Verify events.jsonl contains a coherent pipeline run."""
    result = {"ok": False, "event_count": 0, "phases_completed": [], "last_phase": None, "run_id": None}

    events = load_event_log(run_dir)
    result["event_count"] = len(events)

    if len(events) == 0:
        result["error"] = "Event log is empty or missing"
        return result

    # Extract phases and run_id from events
    for ev in events:
        ev_type = ev.get("type", "")
        if ev_type == "RunCreated":
            result["run_id"] = ev.get("run_id")
        if ev_type == "PhaseCompleted":
            phase = ev.get("phase")
            if phase:
                result["phases_completed"].append(phase)

    if result["phases_completed"]:
        result["last_phase"] = result["phases_completed"][-1]

    has_created = any(e.get("type") == "RunCreated" for e in events)
    has_complete = any(e.get("type") == "RunCompleted" for e in events)

    result["ok"] = has_created and len(result["phases_completed"]) > 0
    result["run_completed"] = has_complete

    return result


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


def run_final_gate(run_dir: Path, check_manifest: bool = False, check_event_log: bool = False) -> dict:
    """Run all final gate checks. Returns gate verdict.

    Args:
        run_dir: Run directory path.
        check_manifest: If True, validates artifacts via manifest + checksum, not just file existence.
        check_event_log: If True, validates events.jsonl for coherent pipeline run.
    """
    artifacts: dict[str, Any] = {}

    if check_manifest:
        # Manifest-based: file exists + manifest entry + checksum match
        for name in REQUIRED_ARTIFACTS:
            artifacts[name] = check_artifact_via_manifest(run_dir, name)
        for name in OPTIONAL_ARTIFACTS:
            artifacts[name] = check_artifact_via_manifest(run_dir, name)
    else:
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

    # Event log validity
    event_log_state = None
    if check_event_log:
        event_log_state = check_event_log_validity(run_dir)

    # Determine if all required artifacts passed
    if check_manifest:
        all_artifacts_present = all(
            isinstance(artifacts.get(a), dict) and artifacts[a].get("ok", False)
            for a in REQUIRED_ARTIFACTS
        )
    else:
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

    if check_event_log and event_log_state:
        checks["event_log_valid"] = event_log_state.get("ok", False)

    all_checks_passed = all(checks.values())

    result = {
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
        "missing_artifacts": (
            [a for a in REQUIRED_ARTIFACTS if (
                isinstance(artifacts.get(a), dict) and not artifacts[a].get("ok", False)
            ) or (
                not isinstance(artifacts.get(a), dict) and not artifacts.get(a, False)
            )]
        ),
        "failed_checks": [k for k, v in checks.items() if not v],
    }

    if check_manifest:
        result["manifest_used"] = True
        # Add manifest summary
        manifest = load_manifest(run_dir)
        if manifest:
            result["manifest"] = {
                "total_entries": len(manifest.get("entries", {})),
                "updated_at": manifest.get("updated_at"),
            }
        # Collect checksum failures
        checksum_failures = []
        for name, check in artifacts.items():
            if isinstance(check, dict) and not check.get("ok") and check.get("found_on_disk") and not check.get("checksum_match"):
                checksum_failures.append({
                    "name": name,
                    "expected": check.get("expected_sha256", ""),
                    "actual": check.get("actual_sha256", ""),
                })
        if checksum_failures:
            result["checksum_failures"] = checksum_failures

    if check_event_log and event_log_state:
        result["event_log"] = event_log_state

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="final_gate: code-level final gate — no LLM involvement."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--output", default=None, help="Output path (default: <run-dir>/final_gate.json)")
    parser.add_argument("--check-manifest", action="store_true", help="Validate artifacts via manifest + checksum (not just file existence)")
    parser.add_argument("--check-event-log", action="store_true", help="Validate events.jsonl for coherent pipeline run")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(f"[final_gate] ERROR: run_dir not found: {run_dir}")
        raise SystemExit(1)

    gate = run_final_gate(run_dir, check_manifest=args.check_manifest, check_event_log=args.check_event_log)

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
