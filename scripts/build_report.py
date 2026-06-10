#!/usr/bin/env python3
"""build_report.py — deterministic pipeline (issue.md architecture).

Pipeline:
  1. docx_inspect.py          → raw dump (zero heuristics)
      ↓ docx_inspect_output.json
  2. source_packet.py         → deterministic markdown parser
      ↓ source_packet.json
  3. source_packet_to_ops.py  → deterministic compiler (zero LLM)
      ↓ execution_ops.json, style_map.json, replace_range.json
  4. validate_ops_strict.py   → strict validation (hard block on high severity)
      ↓ strict_validation.json
  5. execute_execution_ops.py → mechanical executor (OfficeCLI)
      ↓ report.docx
  6. docx_read_result.py      → read back result for verification
      ↓ result_readback.json
  7. qa_docx.py / review_docx.py → metrics & summary

Legacy LLM-as-reasoning flow is preserved in --phase legacy_inspect / legacy_execute.

Usage:
    python build_report.py --phase inspect        # Step 1: raw dump
    python build_report.py --phase compile        # Steps 2-4: source_packet → compile → validate
    python build_report.py --phase execute        # Step 5: apply ops
    python build_report.py --phase qa             # Steps 6-7: QA metrics
    python build_report.py --phase all            # Full deterministic pipeline (all phases)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import os
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TEMPLATE = BASE / "format_template.docx"
TARGET = BASE / "report.docx"
PIPELINE = BASE / ".opencode/skills/md-to-docx-pipeline/scripts"


def timestamp_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_step(script_name: str, *arguments: str, attempt: int = 1) -> tuple[dict, subprocess.CalledProcessError | None]:
    """Run a pipeline script and record the result."""
    script_path = PIPELINE / script_name
    if not script_path.exists():
        return {
            "script": script_name,
            "attempt": attempt,
            "status": "failed",
            "returncode": -1,
            "error": f"Script not found: {script_path}",
        }, RuntimeError(f"Script not found: {script_path}")

    command = [sys.executable, str(script_path), *arguments]
    started_at = timestamp_utc()
    start_time = time.perf_counter()
    print(f"[{script_name}] bắt đầu" if attempt == 1 else f"[{script_name}] bắt đầu lần thử {attempt}")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        duration_seconds = round(time.perf_counter() - start_time, 3)
        return {
            "script": script_name,
            "attempt": attempt,
            "command": command,
            "started_at": started_at,
            "finished_at": timestamp_utc(),
            "duration_seconds": duration_seconds,
            "status": "failed",
            "returncode": exc.returncode,
        }, exc

    duration_seconds = round(time.perf_counter() - start_time, 3)
    return {
        "script": script_name,
        "attempt": attempt,
        "command": command,
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "duration_seconds": duration_seconds,
        "status": "completed",
        "returncode": 0,
    }, None


def officecli_version() -> str:
    result = subprocess.run(["officecli", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Không gọi được officecli --version")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="New pipeline: inspect → (LLM) → execute → QA."
    )
    parser.add_argument("--run-dir", default=str(BASE / ".office-auto/state/manual-run"))
    parser.add_argument("--source-file", default=str(BASE / "noidung.md"))
    parser.add_argument("--template-file", default=str(TEMPLATE))
    parser.add_argument("--target-file", default=str(TARGET))
    parser.add_argument(
        "--phase",
        choices=["inspect", "compile", "execute", "validate", "qa", "all",
                 "legacy_inspect", "legacy_execute"],
        default="inspect",
        help="Pipeline phase to run. 'inspect' runs docx_inspect. "
             "'compile' runs source_packet → source_packet_to_ops → validate_ops_strict. "
             "'execute' applies execution_ops.json. 'qa' runs QA checks. "
             "'all' runs full deterministic pipeline. "
             "'legacy_inspect'/'legacy_execute' use old LLM-writes-ops flow.",
    )
    parser.add_argument("--top-n-styles", type=int, default=None, help="Only dump top N styles (filtering, not classification)")
    parser.add_argument(
        "--skeleton-cache-dir", default=None,
        help="Cache dir for skeleton. If provided, auto-build skeleton before inspect."
    )
    parser.add_argument(
        "--force-skeleton", action="store_true",
        help="Force skeleton rebuild even if cache exists."
    )
    args = parser.parse_args()
    args.run_dir = os.path.abspath(args.run_dir)

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pipeline_report_path = run_dir / "pipeline_report.json"
    started_at = timestamp_utc()
    wrapper_started = time.perf_counter()

    version = officecli_version()
    preflight = {
        "officecli_version": version,
        "phase": args.phase,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "started_at": started_at,
    }
    write_json(run_dir / "preflight.json", preflight)

    step_reports: list[dict] = []
    failed_step: str | None = None
    exit_code = 0

    def run_and_record(script_name: str, step_args: list[str], *, retries: int = 0) -> bool:
        nonlocal failed_step, exit_code
        for attempt in range(1, retries + 2):
            step_report, error = run_step(script_name, *step_args, attempt=attempt)
            step_reports.append(step_report)
            if error is None:
                return True
            if attempt <= retries:
                print(f"[{script_name}] thất bại ở lần {attempt}, thử lại...")
                continue
            failed_step = script_name
            exit_code = error.returncode or 1
            return False
        return False

    # === PHASE: INSPECT ===
    # Raw dump of template structure — no reasoning, no heuristics
    if args.phase in ("inspect", "all", "legacy_inspect", "legacy_execute"):
        inspect_args = ["--template-file", args.template_file, "--run-dir", str(run_dir)]
        if args.top_n_styles:
            inspect_args.extend(["--top-n-styles", str(args.top_n_styles)])
        if args.skeleton_cache_dir:
            inspect_args.extend(["--skeleton-cache-dir", args.skeleton_cache_dir])
        if args.force_skeleton:
            inspect_args.append("--force-skeleton")

        success = run_and_record("docx_inspect.py", inspect_args)
        if not success:
            failed_step = "docx_inspect.py"
        else:
            print("\n" + "=" * 70)
            print("[build_report] ✅ docx_inspect.py hoàn tất.")
            print("[build_report] raw dump đã ghi tại:")
            inspect_summary_path = run_dir / "docx_inspect_summary.json"
            if inspect_summary_path.exists():
                summary = json.loads(inspect_summary_path.read_text(encoding="utf-8"))
                for layer, fpath in summary.get("layer_files", {}).items():
                    print(f"  - {layer}: {fpath}")

            if args.phase == "legacy_inspect":
                print("\n[build_report] TIẾP THEO: LLM (session này) đọc raw dump →")
                print("[build_report] tự suy luận style inheritance, classify headings,")
                print("[build_report] map markdown → styles, và viết execution_ops.json")
                print("=" * 70)
                write_json(run_dir / "pipeline_state.json", {
                    "phase": "inspect_completed_waiting_for_llm",
                    "template_file": args.template_file,
                    "source_file": args.source_file,
                    "target_file": args.target_file,
                })
            else:
                print("\n[build_report] Tiếp theo: compile (source_packet → source_packet_to_ops → validate)")
                print("=" * 70)

    # === PHASE: COMPILE (deterministic, zero LLM) ===
    # source_packet.py → source_packet_to_ops.py → validate_ops_strict.py
    if args.phase in ("compile", "all"):
        if failed_step:
            print(f"\n[build_report] ⏭️  Skipping compile: previous step failed")
        else:
            # Step 2: source_packet.py — deterministic markdown parser
            success = run_and_record(
                "source_packet.py",
                ["--source", args.source_file, "--run-dir", str(run_dir)]
            )
            if success:
                print("\n[build_report] ✅ source_packet.py hoàn tất.")
            else:
                failed_step = "source_packet.py"

        if not failed_step:
            # Step 3: source_packet_to_ops.py — deterministic compiler
            compile_args = ["--run-dir", str(run_dir)]
            success = run_and_record("source_packet_to_ops.py", compile_args)
            if success:
                print("\n[build_report] ✅ source_packet_to_ops.py hoàn tất.")
                ops_file = run_dir / "execution_ops.json"
                if ops_file.exists():
                    ops_data = json.loads(ops_file.read_text(encoding="utf-8"))
                    ops_list = ops_data.get("ops", ops_data) if isinstance(ops_data, dict) else ops_data
                    insert_count = sum(1 for op in ops_list if op.get("op") != "remove")
                    remove_count = sum(1 for op in ops_list if op.get("op") == "remove")
                    print(f"[build_report]   {insert_count} insert ops, {remove_count} remove ops")
            else:
                failed_step = "source_packet_to_ops.py"

        if not failed_step:
            # Step 4: validate_ops_strict.py — hard block on high severity
            success = run_and_record(
                "validate_ops_strict.py",
                ["--run-dir", str(run_dir), "--ops-file", str(run_dir / "execution_ops.json")]
            )
            if success:
                strict_report_path = run_dir / "strict_validation.json"
                if strict_report_path.exists():
                    strict_data = json.loads(strict_report_path.read_text(encoding="utf-8"))
                    valid = strict_data.get("valid", False)
                    high_count = strict_data.get("high_severity_count", 0)
                    warn_count = strict_data.get("warning_count", 0)
                    print(f"\n[build_report] ✅ validate_ops_strict.py hoàn tất. Valid: {valid}, High: {high_count}, Warnings: {warn_count}")
                    if not valid:
                        print("[build_report] ❌ Strict validation FAILED — blocking errors found")
                        blocking = strict_data.get("blocking_errors", [])
                        for idx, err in enumerate(blocking[:10], 1):
                            print(f"[build_report]   {idx}. {err}")
                        failed_step = "validate_ops_strict.py"
                        exit_code = 1
            else:
                failed_step = "validate_ops_strict.py"

    # === LEGACY PHASE: VALIDATE (warn-only, for LLM flow) ===
    if args.phase in ("legacy_execute", "validate"):
        ops_file = run_dir / "execution_ops.json"
        if not ops_file.exists():
            print(f"\n[build_report] ❌ execution_ops.json không tồn tại tại {run_dir}")
            print("[build_report] Chạy 'python build_report.py --phase legacy_inspect' trước,")
            print("[build_report] rồi để LLM viết execution_ops.json.")
            failed_step = "docx_validate_ops.py"
            exit_code = 1
        else:
            success = run_and_record(
                "docx_validate_ops.py",
                ["--run-dir", str(run_dir)]
            )
            if success:
                print("\n[build_report] ✅ docx_validate_ops.py hoàn tất.")
                validation_report = run_dir / "execution_ops_validation.json"
                if validation_report.exists():
                    val_data = json.loads(validation_report.read_text(encoding="utf-8"))
                    warning_count = val_data.get("warning_count", 0)
                    high_count = val_data.get("high_severity_count", 0)
                    print(f"[build_report]   Warnings: {warning_count} (high: {high_count})")
                    
                    # BLOCKING: High-severity warnings must be fixed before execute
                    if high_count > 0:
                        print("\n" + "=" * 70)
                        print("[build_report] ❌ Validation found HIGH-SEVERITY warnings — BLOCKING execute")
                        print(f"[build_report] {high_count} high-severity issue(s) in execution_ops.json:")
                        warnings_list = val_data.get("warnings", [])
                        high_warnings = [w for w in warnings_list if w.get("severity") == "high"]
                        for idx, warn in enumerate(high_warnings[:10], 1):  # Show first 10
                            print(f"[build_report]   {idx}. Op #{warn.get('op_index', '?')}: {warn.get('message', 'Unknown')}")
                        if len(high_warnings) > 10:
                            print(f"[build_report]   ... and {len(high_warnings) - 10} more")
                        print("[build_report]")
                        print("[build_report] TIẾP THEO: LLM fix execution_ops.json and run again:")
                        print(f"[build_report]   python build_report.py --phase legacy_execute --run-dir {run_dir}")
                        print("=" * 70)
                        failed_step = "docx_validate_ops.py"
                        exit_code = 1
                    elif warning_count > 0:
                        print("[build_report] ⚠️  LLM nên review medium/low warnings trước khi execute")
            else:
                # Validation script itself failed
                print(f"\n[build_report] ⚠️  docx_validate_ops.py execution có lỗi (continue to execute)")

    # === PHASE: EXECUTE ===
    # Apply execution_ops.json mechanically (deterministic compiler already generated ops)
    if args.phase in ("execute", "all", "legacy_execute"):
        # Check if validation failed (high-severity warnings blocking)
        if failed_step:
            print(f"\n[build_report] ⏭️  Skipping execute: previous step failed")
        else:
            # Check if execution_ops.json exists
            ops_file = run_dir / "execution_ops.json"
            if not ops_file.exists():
                print(f"\n[build_report] ❌ execution_ops.json không tồn tại tại {run_dir}")
                if args.phase == "legacy_execute":
                    print("[build_report] Chạy 'python build_report.py --phase legacy_inspect' trước,")
                    print("[build_report] rồi để LLM viết execution_ops.json.")
                else:
                    print("[build_report] Chạy 'python build_report.py --phase compile' trước.")
                failed_step = "execute_execution_ops.py"
                exit_code = 1
            else:
                success = run_and_record(
                    "execute_execution_ops.py",
                    ["--run-dir", str(run_dir), "--template-file", args.template_file, "--target-file", args.target_file, "--fail-fast"]
                )
                if not success:
                    failed_step = "execute_execution_ops.py"
                else:
                    print("\n[build_report] ✅ execute_execution_ops.py hoàn tất.")

    # === PHASE: READ RESULT ===
    # Read back the result DOCX to verify execution
    if args.phase in ("execute", "read_result", "all", "legacy_execute"):
        if not failed_step and (run_dir / "execute_ops_report.json").exists():
            exec_report = json.loads((run_dir / "execute_ops_report.json").read_text(encoding="utf-8"))
            if exec_report.get("status") == "completed":
                run_and_record(
                    "docx_read_result.py",
                    ["--run-dir", str(run_dir), "--file", args.target_file]
                )
                print("\n[build_report] ✅ docx_read_result.py hoàn tất.")

    # === PHASE: QA ===
    # Metrics collection only (no intelligence — just measurement)
    if args.phase in ("qa", "all", "legacy_execute"):
        if not failed_step:
            # Check if target was built
            if (run_dir / "execute_ops_report.json").exists():
                exec_report = json.loads((run_dir / "execute_ops_report.json").read_text(encoding="utf-8"))
                if exec_report.get("status") == "failed":
                    failed_step = "execute_execution_ops.py"

        if not failed_step:
            run_and_record("qa_docx.py", ["--run-dir", str(run_dir)])
            run_and_record("review_docx.py", ["--run-dir", str(run_dir)])
            # Update pipeline state
            write_json(run_dir / "pipeline_state.json", {
                "phase": "qa_completed",
            })

    # === PIPELINE REPORT ===
    pipeline_report = {
        "status": "failed" if failed_step else "completed",
        "phase": args.phase,
        "started_at": started_at,
        "finished_at": timestamp_utc(),
        "duration_seconds": round(time.perf_counter() - wrapper_started, 3),
        "officecli_version": version,
        "run_dir": str(run_dir),
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
        "failed_step": failed_step,
        "steps": step_reports,
    }
    write_json(pipeline_report_path, pipeline_report)

    if failed_step:
        print(f"\nPipeline dừng tại bước: {failed_step}")
        print(f"Kiểm tra artifact: {pipeline_report_path}")
        raise SystemExit(exit_code)

    print(f"\nĐã chạy xong pipeline tại: {run_dir}")
    print(f"OfficeCLI version: {version}")
    print(f"Kiểm tra artifact: {run_dir / 'execute_ops_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'qa_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'preflight.json'}")


if __name__ == "__main__":
    main()
