#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parents[1]
STATE_DIR = BASE / ".office-auto" / "state"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_path(path_value: str | None, *, default: Path | None = None) -> str | None:
    if path_value:
        candidate = Path(path_value)
        return str(candidate if candidate.is_absolute() else BASE / candidate)
    if default is not None:
        return str(default.resolve())
    return None


def latest_run_dir(state_dir: Path) -> Path | None:
    candidates = [
        path
        for path in state_dir.iterdir()
        if path.is_dir() and ((path / "pipeline_report.json").exists() or (path / "run.json").exists())
    ] if state_dir.exists() else []
    if not candidates:
        return None

    def sort_key(path: Path) -> float:
        pipeline_report = path / "pipeline_report.json"
        if pipeline_report.exists():
            return pipeline_report.stat().st_mtime
        return path.stat().st_mtime

    return max(candidates, key=sort_key)


def collect_summary(run_dir: Path) -> dict[str, Any]:
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
    pipeline_report = read_json(run_dir / "pipeline_report.json") if (run_dir / "pipeline_report.json").exists() else {}
    qa_report = read_json(run_dir / "qa_report.json") if (run_dir / "qa_report.json").exists() else {}
    review_report = read_json(run_dir / "review_report.json") if (run_dir / "review_report.json").exists() else {}
    artifacts = run_state.get("artifacts", {}) if isinstance(run_state.get("artifacts", {}), dict) else {}

    return {
        "run_dir": str(run_dir),
        "status": run_state.get("status") or pipeline_report.get("status") or "unknown",
        "pipeline_status": pipeline_report.get("status", "unknown"),
        "qa_status": qa_report.get("status", "unknown"),
        "review_status": review_report.get("status", "missing"),
        "target_file": resolve_path(run_state.get("target_file") or pipeline_report.get("target_file")),
        "failed_step": pipeline_report.get("failed_step"),
        "review_attention_count": ((review_report.get("inserted_paragraph_summary") or {}).get("paragraphs_with_attention")),
        "artifacts": {
            "pipeline_report": resolve_path(artifacts.get("pipeline_report"), default=run_dir / "pipeline_report.json"),
            "qa_report": resolve_path(artifacts.get("qa_report"), default=run_dir / "qa_report.json"),
            "review_report": resolve_path(artifacts.get("review_report"), default=run_dir / "review_report.json"),
            "review_markdown": resolve_path(artifacts.get("review_markdown"), default=run_dir / "review_report.md"),
            "review_html": resolve_path(artifacts.get("review_html"), default=run_dir / "review_screen.html"),
        },
    }


def render_text(summary: dict[str, Any]) -> str:
    artifact_lines = [
        f"- pipeline_report: {summary['artifacts'].get('pipeline_report')}",
        f"- qa_report: {summary['artifacts'].get('qa_report')}",
        f"- review_report: {summary['artifacts'].get('review_report')}",
        f"- review_markdown: {summary['artifacts'].get('review_markdown')}",
        f"- review_html: {summary['artifacts'].get('review_html')}",
    ]
    lines = [
        f"run_dir: {summary.get('run_dir')}",
        f"status: {summary.get('status')}",
        f"pipeline_status: {summary.get('pipeline_status')}",
        f"qa_status: {summary.get('qa_status')}",
        f"review_status: {summary.get('review_status')}",
        f"target_file: {summary.get('target_file')}",
        f"failed_step: {summary.get('failed_step') or '(none)'}",
        f"review_attention_count: {summary.get('review_attention_count') if summary.get('review_attention_count') is not None else '(unknown)'}",
        "artifacts:",
        *artifact_lines,
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="In nhanh artifact review mới nhất hoặc của một run cụ thể.")
    parser.add_argument("--run-dir", help="Run dir cụ thể dưới .office-auto/state hoặc absolute path.")
    parser.add_argument("--json", action="store_true", help="In JSON thay vì text.")
    args = parser.parse_args()

    if args.run_dir:
        candidate = Path(args.run_dir)
        run_dir = candidate if candidate.is_absolute() else BASE / args.run_dir
    else:
        run_dir = latest_run_dir(STATE_DIR)

    if run_dir is None or not run_dir.exists():
        raise SystemExit("Không tìm thấy run dir nào có pipeline/report artifact.")

    summary = collect_summary(run_dir)
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return
    print(render_text(summary))


if __name__ == "__main__":
    main()