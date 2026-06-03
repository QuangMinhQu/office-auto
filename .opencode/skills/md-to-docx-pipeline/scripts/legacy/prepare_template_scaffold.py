from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from officecli_native import officecli_batch_commands, read_json, write_json
from plan_mapping import assess_template_guardrails


DEFAULT_CHUNK_SIZE = 200


def template_cache_key(template_file: Path) -> str:
    digest = hashlib.sha1()
    with template_file.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()[:16]


def main_story_candidate(profile: dict) -> dict | None:
    for candidate in profile.get("document_profile", {}).get("replace_range_candidates", []):
        if candidate.get("name") == "after-front-matter-to-end-of-main-story" and candidate.get("status") == "resolved":
            return candidate
    return None


def should_prepare_effective_template(profile: dict, candidate: dict | None) -> tuple[bool, dict]:
    guardrails = assess_template_guardrails(profile, candidate)
    risk_flags = set(guardrails.get("risk_flags", []))
    should_prepare = (
        candidate is not None
        and "whole-body-rewrite" in risk_flags
        and "full-document-template-disguised-as-format" in risk_flags
    )
    return should_prepare, guardrails


def choose_scaffold_strategy(profile: dict, candidate: dict | None) -> tuple[str, dict, bool]:
    should_prepare, guardrails = should_prepare_effective_template(profile, candidate)
    recommended_path = str((profile.get("topology") or {}).get("recommended_path") or "")

    if recommended_path == "structural_preserve":
        return "structural_preserve", guardrails, False
    if recommended_path == "hybrid":
        return "hybrid", guardrails, False
    if should_prepare and candidate is not None:
        return "semantic_style", guardrails, True
    return "pass_through", guardrails, False


def execute_remove_batch(document: Path, commands: list[dict], chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
    if not commands:
        return {"summary": {"total": 0, "executed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "chunks": 0}, "results": []}

    total_succeeded = 0
    total_failed = 0
    total_chunks = 0
    all_results: list[dict] = []
    for index in range(0, len(commands), chunk_size):
        chunk = commands[index:index + chunk_size]
        total_chunks += 1
        try:
            payload = officecli_batch_commands(document, chunk, stop_on_error=True)
            batch_data = payload.get("data") if isinstance(payload, dict) and payload.get("data") is not None else payload
            if isinstance(batch_data, dict):
                summary = batch_data.get("summary", {})
                total_succeeded += summary.get("succeeded", len(chunk))
                total_failed += summary.get("failed", 0)
                all_results.extend(batch_data.get("results", []))
            else:
                total_succeeded += len(chunk)
        except Exception as exc:
            total_failed += len(chunk)
            all_results.append({"error": str(exc)})

    return {
        "summary": {
            "total": len(commands),
            "executed": len(commands),
            "succeeded": total_succeeded,
            "failed": total_failed,
            "skipped": 0,
            "chunks": total_chunks,
        },
        "results": all_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Chuẩn hóa full historical DOCX thành scaffold template hiệu dụng khi cần.")
    parser.add_argument("--template-file", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--prepared-template-file", required=False)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    template_file = Path(args.template_file)
    prepared_template_file = Path(args.prepared_template_file) if args.prepared_template_file else run_dir / "effective_template.docx"
    report_file = run_dir / "template_preparation_report.json"
    source_profile_file = run_dir / "source_template_profile.json"
    cache_dir = run_dir.parent / "template-cache"
    run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {"artifacts": {}}
    profile = read_json(run_dir / "template_profile.json")

    candidate = main_story_candidate(profile)
    strategy, guardrails, should_prepare = choose_scaffold_strategy(profile, candidate)

    report = {
        "status": "pass-through",
        "source_template_file": str(template_file),
        "effective_template_file": str(template_file),
        "selected_candidate": None if candidate is None else candidate.get("name"),
        "guardrails": guardrails,
        "strategy": strategy,
        "message": "Template hiện tại đã đủ gần scaffold; không cần derive effective template.",
    }

    run_state.setdefault("artifacts", {})["template_preparation_report"] = str(report_file)

    if strategy in {"structural_preserve", "hybrid"}:
        shutil.copy2(template_file, prepared_template_file)
        report = {
            "status": "pass-through",
            "source_template_file": str(template_file),
            "effective_template_file": str(prepared_template_file),
            "selected_candidate": None if candidate is None else candidate.get("name"),
            "guardrails": guardrails,
            "strategy": strategy,
            "message": "Topology yêu cầu preserve structure; bỏ qua bước thin-scaffold để tránh phá TOC/bookmark/section.",
        }
        run_state.setdefault("artifacts", {})["effective_template"] = str(prepared_template_file)

    elif should_prepare and candidate is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = template_cache_key(template_file)
        cached_template_file = cache_dir / f"{template_file.stem}-{cache_key}.docx"
        source_profile_file.write_text((run_dir / "template_profile.json").read_text(encoding="utf-8"), encoding="utf-8")
        if cached_template_file.exists():
            shutil.copy2(cached_template_file, prepared_template_file)
            report = {
                "status": "prepared",
                "source_template_file": str(template_file),
                "effective_template_file": str(prepared_template_file),
                "selected_candidate": candidate.get("name"),
                "removed_child_count": len(candidate.get("remove_paths", [])),
                "remove_batch_summary": {"cached": True},
                "guardrails": guardrails,
                "strategy": strategy,
                "cache_key": cache_key,
                "cache_hit": True,
                "message": "Đã reuse scaffold template từ cache cho cùng source template.",
            }
        else:
            shutil.copy2(template_file, prepared_template_file)
            remove_commands = [{"command": "remove", "path": path} for path in reversed(candidate.get("remove_paths", []))]
            remove_batch_result = execute_remove_batch(prepared_template_file, remove_commands)
            if (remove_batch_result.get("summary") or {}).get("failed", 0):
                report = {
                    "status": "failed",
                    "source_template_file": str(template_file),
                    "effective_template_file": str(prepared_template_file),
                    "selected_candidate": candidate.get("name"),
                    "guardrails": guardrails,
                    "strategy": strategy,
                    "remove_batch_summary": remove_batch_result.get("summary", {}),
                    "cache_key": cache_key,
                    "cache_hit": False,
                    "message": "Không derive được scaffold template vì batch remove trên template copy bị lỗi.",
                }
                run_state["status"] = "failed"
                run_state.setdefault("artifacts", {})["effective_template"] = str(prepared_template_file)
                write_json(report_file, report)
                write_json(run_dir / "run.json", run_state)
                raise SystemExit(1)

            shutil.copy2(prepared_template_file, cached_template_file)
            report = {
                "status": "prepared",
                "source_template_file": str(template_file),
                "effective_template_file": str(prepared_template_file),
                "selected_candidate": candidate.get("name"),
                "removed_child_count": len(candidate.get("remove_paths", [])),
                "remove_batch_summary": remove_batch_result.get("summary", {}),
                "guardrails": guardrails,
                "strategy": strategy,
                "cache_key": cache_key,
                "cache_hit": False,
                "message": "Đã derive effective template bằng cách giữ scaffold đầu tài liệu và loại bỏ main story cũ khỏi template copy.",
            }
        run_state.setdefault("artifacts", {})["source_template_profile"] = str(source_profile_file)
        run_state.setdefault("artifacts", {})["effective_template"] = str(prepared_template_file)

    write_json(report_file, report)
    write_json(run_dir / "run.json", run_state)


if __name__ == "__main__":
    main()