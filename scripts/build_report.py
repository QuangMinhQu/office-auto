#!/usr/bin/env python3
"""Chạy pipeline preserve-template-scaffold để sinh report.docx an toàn."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BASE = Path("/home/minhquang/office-auto")
TEMPLATE = BASE / "format_template.docx"
TARGET = BASE / "report.docx"
PIPELINE = BASE / ".opencode/skills/md-to-docx-pipeline/scripts"


def run_step(script_name: str, *arguments: str) -> None:
    script_path = PIPELINE / script_name
    command = [sys.executable, str(script_path), *arguments]
    subprocess.run(command, check=True)


def officecli_version() -> str:
    result = subprocess.run(["officecli", "--version"], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Không gọi được officecli --version")
    return result.stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chạy pipeline build DOCX an toàn theo contract preserve-template-scaffold.")
    parser.add_argument("--run-dir", default=str(BASE / ".office-auto/state/manual-run"))
    parser.add_argument("--source-file", default=str(BASE / "chuong_2.md"))
    parser.add_argument("--template-file", default=str(TEMPLATE))
    parser.add_argument("--target-file", default=str(TARGET))
    parser.add_argument("--mode", default="preserve-template-scaffold")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    version = officecli_version()
    preflight = {
        "officecli_version": version,
        "mode": args.mode,
        "source_file": args.source_file,
        "template_file": args.template_file,
        "target_file": args.target_file,
    }
    (run_dir / "preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run_step("parse_markdown.py", "--source-file", args.source_file, "--run-dir", str(run_dir))
    run_step("profile_template.py", "--template-file", args.template_file, "--run-dir", str(run_dir))
    run_step(
        "plan_mapping.py",
        "--mode",
        args.mode,
        "--run-dir",
        str(run_dir),
        "--source-file",
        args.source_file,
        "--template-file",
        args.template_file,
        "--target-file",
        args.target_file,
    )
    run_step("build_docx.py", "--run-dir", str(run_dir))
    run_step("qa_docx.py", "--run-dir", str(run_dir))

    print(f"Đã chạy xong pipeline tại: {run_dir}")
    print(f"OfficeCLI version: {version}")
    print(f"Kiểm tra artifact: {run_dir / 'plan.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'build_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'qa_report.json'}")
    print(f"Kiểm tra artifact: {run_dir / 'preflight.json'}")



if __name__ == "__main__":
    main()
