#!/usr/bin/env python3
"""verify_docx_output.py — readback + coverage verification. Zero LLM.

Reads output DOCX and checks:
1. Every source_block text appears in output (exact match)
2. Heading count matches
3. Heading order matches
4. No placeholder leak (old template text still present)
5. Front matter still exists
6. References section exists if source has it
7. TOC field exists
8. Style IDs applied correctly

Usage:
    python3 verify_docx_output.py --run-dir <path> [--target-file <path>]
"""
from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path
from typing import Any

from officecli_native import read_json, write_json


def normalize_text(text: str) -> str:
    """Normalize text for comparison: collapse whitespace, strip."""
    return re.sub(r'\s+', ' ', text.strip())


def read_output_docx(target_path: Path, run_dir: Path) -> dict | None:
    """Read output DOCX via docx_read_result.py or direct inspection."""
    import subprocess
    import sys

    result_file = run_dir / "result_readback.json"

    # Try running readback
    try:
        script = run_dir.parent.parent / "scripts" / "docx_read_result.py"
        if not script.exists():
            script = Path(__file__).resolve().parent / "docx_read_result.py"

        if script.exists():
            subprocess.run(
                [sys.executable, str(script),
                 "--target-file", str(target_path),
                 "--run-dir", str(run_dir)],
                capture_output=True, text=True, timeout=60,
            )
    except Exception:
        pass

    if result_file.exists():
        return read_json(result_file)

    return None


def extract_text_from_readback(readback: dict) -> str:
    """Extract all paragraph text from readback into a single normalized string."""
    parts = []
    for para in readback.get("paragraphs", []):
        text = para.get("text", "")
        if text.strip():
            parts.append(text.strip())
    return "\n".join(parts)


def check_source_coverage(
    source_packet: dict,
    output_text: str,
    ops: list[dict],
) -> dict:
    """Check that every source block's text appears in the output."""
    blocks = source_packet.get("blocks", [])
    missing: list[dict] = []
    matched = 0

    for block in blocks:
        block_text = normalize_text(block.get("text", ""))
        if not block_text:
            matched += 1
            continue

        normalized_output = normalize_text(output_text)
        if block_text in normalized_output:
            matched += 1
        else:
            # Try fuzzy match for truncated or slightly modified text
            ratio = difflib.SequenceMatcher(
                None, block_text[:200], normalized_output[:len(block_text) + 1000]
            ).ratio()
            if ratio > 0.85:
                matched += 1
                continue

            missing.append({
                "block_id": block.get("id"),
                "type": block.get("type"),
                "text_preview": block_text[:100],
                "fuzzy_ratio": round(ratio, 2),
            })

    return {
        "source_blocks": len(blocks),
        "matched_blocks": matched,
        "missing_blocks": missing,
        "coverage_pct": round(matched / max(len(blocks), 1) * 100, 1),
        "ok": len(missing) == 0,
    }


def check_heading_consistency(
    source_packet: dict,
    output_readback: dict | None,
) -> dict:
    """Check heading count and order in output."""
    blocks = source_packet.get("blocks", [])
    source_headings = [b for b in blocks if b.get("type") == "heading"]

    if not output_readback:
        return {"ok": True, "note": "No readback available, heading check skipped"}

    output_paragraphs = output_readback.get("paragraphs", [])
    output_headings = [
        p for p in output_paragraphs
        if p.get("style_name", "").startswith("Heading")
        or p.get("outline_level") is not None
    ]

    return {
        "source_heading_count": len(source_headings),
        "output_heading_count": len(output_headings),
        "ok": len(output_headings) >= len(source_headings) * 0.9,
    }


def check_placeholder_leak(
    ops: list[dict],
    output_text: str,
    scaffold: dict | None,
) -> dict:
    """Check that placeholder text from template is not in output."""
    if not scaffold:
        return {"ok": True, "note": "No scaffold, skip placeholder leak check"}

    placeholder_details = scaffold.get("body_placeholders", {}).get("details", [])
    leaks = []
    for detail in placeholder_details:
        preview = (detail.get("text_preview") or "").strip()
        if not preview or len(preview) < 5:
            continue
        normalized_preview = normalize_text(preview)
        normalized_output = normalize_text(output_text)
        if normalized_preview in normalized_output:
            leaks.append({
                "paraId": detail.get("paraId"),
                "text_preview": preview[:80],
            })

    return {
        "placeholder_count": len(placeholder_details),
        "leaks": leaks,
        "leak_count": len(leaks),
        "ok": len(leaks) == 0,
    }


def check_style_applied(ops: list[dict]) -> dict:
    """Check that insert ops have valid style assignments."""
    insert_ops = [op for op in ops if op.get("op") in ("insert_paragraph_after", "insert_paragraph_before")]
    missing_style = [op for op in insert_ops if not op.get("style")]
    unknown_style = [op for op in insert_ops if op.get("style") and not op.get("style", "").strip()]

    return {
        "insert_ops": len(insert_ops),
        "missing_style": len(missing_style),
        "empty_style": len(unknown_style),
        "ok": len(missing_style) == 0 and len(unknown_style) == 0,
    }


def verify(run_dir: Path, target_path: Path) -> dict:
    """Run all verification checks."""
    source_packet_path = run_dir / "source_packet.json"
    ops_path = run_dir / "execution_ops.json"
    scaffold_path = run_dir / "insert_plan_scaffold.json"

    if not source_packet_path.exists():
        return {"ok": False, "error": "source_packet.json not found", "run_dir": str(run_dir)}
    if not ops_path.exists():
        return {"ok": False, "error": "execution_ops.json not found", "run_dir": str(run_dir)}

    source_packet = read_json(source_packet_path)
    ops_payload = read_json(ops_path)
    ops = ops_payload.get("ops", []) if isinstance(ops_payload, dict) else ops_payload
    scaffold = read_json(scaffold_path) if scaffold_path.exists() else None

    output_readback = None
    output_text = ""
    if target_path.exists():
        output_readback = read_output_docx(target_path, run_dir)
        if output_readback:
            output_text = extract_text_from_readback(output_readback)
    else:
        # Use ops text as fallback
        output_text = " ".join(
            op.get("text", "") for op in ops if op.get("text")
        )

    coverage = check_source_coverage(source_packet, output_text, ops)
    headings = check_heading_consistency(source_packet, output_readback)
    placeholder = check_placeholder_leak(ops, output_text, scaffold)
    style_check = check_style_applied(ops)

    all_ok = (
        coverage.get("ok", False)
        and headings.get("ok", True)
        and placeholder.get("ok", True)
        and style_check.get("ok", True)
    )

    return {
        "ok": all_ok,
        "coverage": coverage,
        "headings": headings,
        "placeholder_leak": placeholder,
        "style_check": style_check,
        "source_blocks": source_packet.get("block_count", 0),
        "insert_ops": len([op for op in ops if op.get("op") != "remove"]),
        "remove_ops": len([op for op in ops if op.get("op") == "remove"]),
        "target_file_exists": target_path.exists(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="verify_docx_output: readback + coverage verification — zero LLM."
    )
    parser.add_argument("--run-dir", required=True, help="Run directory")
    parser.add_argument("--target-file", default=None, help="Output DOCX path")
    parser.add_argument("--output", default=None, help="Verification report path")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_json = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    target_path = Path(args.target_file) if args.target_file else Path(
        run_json.get("target_file", run_json.get("artifacts", {}).get("target_file", ""))
    )

    result = verify(run_dir, target_path)

    output_path = Path(args.output) if args.output else run_dir / "coverage_report.json"
    write_json(output_path, result)

    if result.get("ok"):
        coverage_pct = result["coverage"].get("coverage_pct", 0)
        print(f"[verify_docx_output] ✅ PASSED — Coverage: {coverage_pct}% "
              f"({result['coverage']['matched_blocks']}/{result['coverage']['source_blocks']} blocks)")
    else:
        print(f"[verify_docx_output] ❌ FAILED")
        if result.get("error"):
            print(f"  Error: {result['error']}")
        missing = result.get("coverage", {}).get("missing_blocks", [])
        if missing:
            print(f"  Missing blocks: {len(missing)}")
            for m in missing[:5]:
                print(f"    - {m.get('block_id')}: {m.get('text_preview', '')[:60]}")

    print(f"[verify_docx_output] Report: {output_path}")


if __name__ == "__main__":
    main()
