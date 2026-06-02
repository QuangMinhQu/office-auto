#!/usr/bin/env python3
"""Chạy pipeline preserve-template-scaffold để sinh report.docx an toàn."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
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


def patch_template_profile(run_dir: Path) -> bool:
    """Sửa prototype_catalog: TOC1/TOC2/TOC3 → Heading1/Heading2/Heading3.

    Template gốc có thể chứa TOC placeholder paragraphs tại paraId của
    h1/h2/h3 prototype. Khi profile_template.py đọc những paraId này,
    style_id sẽ là TOC1/TOC2/TOC3 thay vì Heading1/Heading2/Heading3,
    khiến plan_mapping ánh xạ sai heading role → QA fail (output_heading_count=0).

    Hàm này sửa template_profile.json sau khi profile_template.py chạy.
    """
    tp_path = run_dir / "template_profile.json"
    if not tp_path.exists():
        print("[patch_template_profile] template_profile.json không tồn tại, bỏ qua")
        return True

    with open(tp_path, "r", encoding="utf-8") as f:
        profile = json.load(f)

    prototype_catalog = profile.get("prototype_catalog", {})
    changes = 0
    # Map TOC styles → Heading styles
    toc_to_heading = {
        "TOC1": "Heading1",
        "TOC2": "Heading2",
        "TOC3": "Heading3",
        "toc 1": "heading 1",
        "toc 2": "heading 2",
        "toc 3": "heading 3",
    }
    heading_roles = {"h1", "h2", "h3", "legal_chuong", "legal_dieu", "legal_khoan"}
    for role in heading_roles:
        if role not in prototype_catalog:
            continue
        pc_entry = prototype_catalog[role]
        if not isinstance(pc_entry, dict):
            continue
        old_style = pc_entry.get("style_id", "")
        if old_style in toc_to_heading:
            new_style = toc_to_heading[old_style]
            pc_entry["style_id"] = new_style
            changes += 1
            print(f"[patch_template_profile] {role}: {old_style} → {new_style}")

    if changes > 0:
        with open(tp_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        print(f"[patch_template_profile] Đã sửa {changes} prototype entry(s)")
    else:
        print("[patch_template_profile] Không cần sửa")
    return True


def run_step(script_name: str, *arguments: str, attempt: int = 1) -> tuple[dict, subprocess.CalledProcessError | None]:
    script_path = PIPELINE / script_name
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
    parser = argparse.ArgumentParser(description="Chạy pipeline build DOCX an toàn theo contract preserve-template-scaffold.")
    parser.add_argument("--run-dir", default=str(BASE / ".office-auto/state/manual-run"))
    parser.add_argument("--source-file", default=str(BASE / "noidung.md"))
    parser.add_argument("--sample-file", default=None)
    parser.add_argument("--template-file", default=str(TEMPLATE))
    parser.add_argument("--target-file", default=str(TARGET))
    parser.add_argument("--mode", default="preserve-template-scaffold")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    pipeline_report_path = run_dir / "pipeline_report.json"
    started_at = timestamp_utc()
    wrapper_started = time.perf_counter()

    version = officecli_version()
    preflight = {
        "officecli_version": version,
        "mode": args.mode,
        "source_file": args.source_file,
        "sample_file": args.sample_file,
        "template_file": args.template_file,
        "source_template_file": args.template_file,
        "effective_template_file": args.template_file,
        "target_file": args.target_file,
        "started_at": started_at,
        "pipeline_report": str(pipeline_report_path),
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

    if not run_and_record("document_topology_detector.py", ["--template-file", args.template_file, "--run-dir", str(run_dir)]):
        pass
    elif not run_and_record("profile_template.py", ["--template-file", args.template_file, "--run-dir", str(run_dir)]):
        pass
    elif not patch_template_profile(run_dir):
        pass
    elif not run_and_record("template_suitability_report.py", ["--run-dir", str(run_dir)]):
        pass
    elif not run_and_record(
        "prepare_template_scaffold.py",
        ["--template-file", args.template_file, "--run-dir", str(run_dir)],
    ):
        pass
    else:
        preparation_report = json.loads((run_dir / "template_preparation_report.json").read_text(encoding="utf-8"))
        effective_template_file = preparation_report.get("effective_template_file", args.template_file)
        preflight["effective_template_file"] = effective_template_file
        write_json(run_dir / "preflight.json", preflight)

        if effective_template_file != args.template_file:
            if not run_and_record("document_topology_detector.py", ["--template-file", effective_template_file, "--run-dir", str(run_dir)]):
                pass
            elif not run_and_record("profile_template.py", ["--template-file", effective_template_file, "--run-dir", str(run_dir)]):
                pass
            elif not patch_template_profile(run_dir):
                pass
            elif not run_and_record("template_suitability_report.py", ["--run-dir", str(run_dir)]):
                pass

        if failed_step is None and not run_and_record("generate_pandoc_style_map.py", ["--run-dir", str(run_dir)]):
            pass
        if failed_step is None and not run_and_record(
            "input_processor.py",
            [
                "--source-file",
                args.source_file,
                "--run-dir",
                str(run_dir),
                "--style-spec-file",
                str(run_dir / "pandoc_style_spec.json"),
            ],
        ):
            pass
        sample_file = args.sample_file or effective_template_file
        preflight["sample_file"] = sample_file
        write_json(run_dir / "preflight.json", preflight)
        if failed_step is None and sample_file:
            if not run_and_record(
                "extract_sample_content.py",
                [
                    "--sample-file",
                    sample_file,
                    "--run-dir",
                    str(run_dir),
                    "--style-spec-file",
                    str(run_dir / "pandoc_style_spec.json"),
                ],
            ):
                pass
        if failed_step is None and not run_and_record("parse_markdown.py", ["--source-file", str(run_dir / "normalized.md"), "--run-dir", str(run_dir)]):
            pass
        if failed_step is None and not run_and_record(
            "plan_mapping.py",
            [
                "--mode",
                args.mode,
                "--run-dir",
                str(run_dir),
                "--source-file",
                args.source_file,
                "--template-file",
                effective_template_file,
                "--target-file",
                args.target_file,
            ],
        ):
            pass
        if failed_step is None and not run_and_record("compile_execution_plan.py", ["--run-dir", str(run_dir)]):
            pass
        if failed_step is None and not run_and_record("build_docx.py", ["--run-dir", str(run_dir)], retries=1):
            pass
        if failed_step is None and not run_and_record("post_process_docx.py", ["--run-dir", str(run_dir)]):
            pass
        if failed_step is None and not run_and_record(
            "roundtrip_pandoc.py",
            [
                "--run-dir",
                str(run_dir),
                "--style-spec-file",
                str(run_dir / "pandoc_style_spec.json"),
            ],
        ):
            pass
        if failed_step is None:
            run_and_record("qa_docx.py", ["--run-dir", str(run_dir)])
        if failed_step is None:
            run_and_record("review_docx.py", ["--run-dir", str(run_dir)])

    pipeline_report = {
        "status": "failed" if failed_step else "completed",
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
        print(f"Pipeline dừng tại bước: {failed_step}")
        print(f"Kiểm tra artifact: {pipeline_report_path}")
        raise SystemExit(exit_code)

    print(f"Đã chạy xong pipeline tại: {run_dir}")
    print(f"OfficeCLI version: {version}")
    print(f"Kiểm tra artifact: {run_dir / 'plan.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'build_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'roundtrip_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'qa_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'preflight.json'}")
    print(f"Kiểm tra artifact: {pipeline_report_path}")



if __name__ == "__main__":
    main()
