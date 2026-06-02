from __future__ import annotations

import argparse
import os
import re
import shutil
from contextlib import contextmanager
from pathlib import Path

from officecli_native import (
    OfficeCliError,
    ensure_officecli_available,
    extract_added_path,
    officecli_add,
    officecli_batch_commands,
    officecli_close,
    officecli_get,
    officecli_open,
    officecli_query,
    officecli_refresh,
    officecli_remove,
    officecli_save,
    officecli_set,
    officecli_view,
    read_json,
    write_json,
)


DIRECT_BODY_CHILD_PATTERN = re.compile(r'^/body/(?:p|tbl)(?:\[\d+\]|\[@paraId=[0-9A-Fa-f]+\])$')
DIRECT_BODY_PREFIX_PATTERN = re.compile(r"^(/body/(?:p|tbl)\[(\d+)\])(?:/.*)?$")
DEFAULT_REMOVE_BATCH_CHUNK_SIZE = 200
DEFAULT_PARAGRAPH_BATCH_CHUNK_SIZE = 40

@contextmanager
def officecli_document(path):
    officecli_open(path)
    try:
        yield path
    finally:
        try:
            officecli_close(path)
        except Exception:
            pass

def direct_body_path(path: str | None) -> str | None:
    if not path:
        return None
    match = DIRECT_BODY_PREFIX_PATTERN.match(str(path))
    return None if match is None else match.group(1)


def direct_body_index(path: str | None) -> int | None:
    if not path:
        return None
    match = DIRECT_BODY_PREFIX_PATTERN.match(str(path))
    return None if match is None else int(match.group(2))


def direct_body_children(document: Path) -> list[str]:
    text_view = officecli_view(document, "text") or {}
    return [
        str(element.get("path"))
        for element in text_view.get("elements", [])
        if DIRECT_BODY_CHILD_PATTERN.match(str(element.get("path") or ""))
    ]


def canonical_document_path(document: Path, path: str) -> str:
    payload = officecli_get(document, path, depth=1) or {}
    results = payload.get("results", []) if isinstance(payload, dict) else []
    if results:
        canonical_path = results[0].get("path")
        if canonical_path:
            return str(canonical_path)
    return path


def collect_build_blocking_reasons(plan: dict, execution_plan: dict) -> list[str]:
    reasons: list[str] = []
    for source in [plan.get("blocking_reasons", []), (plan.get("template_guardrails") or {}).get("blocking_reasons", []), execution_plan.get("blocking_reasons", [])]:
        for reason in source or []:
            if reason and reason not in reasons:
                reasons.append(str(reason))
    return reasons


def prototype_paths_requiring_reservation(execution_plan: dict) -> list[str]:
    selected_range = execution_plan.get("selected_replace_range", {})
    remove_paths = selected_range.get("remove_paths", [])
    remove_path_set = {str(path) for path in remove_paths}
    first_removed_index = direct_body_index(remove_paths[0]) if remove_paths else None

    candidates: list[str] = []
    seen: set[str] = set()
    for operation in execution_plan.get("render_ops", []):
        prototype_path = operation.get("prototype_path")
        if not prototype_path or prototype_path in seen:
            continue
        prototype_path = str(prototype_path)

        # For paraId-based ranges, reserve when prototype path is explicitly removed.
        if prototype_path in remove_path_set:
            candidates.append(prototype_path)
            seen.add(prototype_path)
            continue

        prototype_index = direct_body_index(prototype_path)
        if first_removed_index is None:
            continue
        if prototype_index is None or prototype_index < first_removed_index:
            continue
        candidates.append(str(prototype_path))
        seen.add(str(prototype_path))
    return candidates


def reserve_prototype_paths(document: Path, execution_plan: dict) -> dict[str, str]:
    prototype_paths = prototype_paths_requiring_reservation(execution_plan)
    if not prototype_paths:
        return {}

    # Try to find body paths using query instead of strict pattern matching
    try:
        body_results = officecli_query(document, "paragraph")
        body_paths = [r.get("path", "") for r in body_results if str(r.get("path", "")).startswith("/body/")]
    except Exception:
        body_paths = direct_body_children(document)

    if not body_paths:
        return {}

    reserved_paths: dict[str, str] = {}
    reserve_after = body_paths[-1] if body_paths else None
    for prototype_path in prototype_paths:
        try:
            payload = officecli_add(
                document,
                "/body",
                element_type="paragraph",
                from_path=prototype_path,
                after=reserve_after,
            )
            added_path = extract_added_path(payload, element_type="paragraph", parent="/body")
            if added_path is not None:
                reserve_after = added_path
                reserved_paths[prototype_path] = canonical_document_path(document, added_path)
        except OfficeCliError:
            pass

    return reserved_paths


def apply_reserved_prototypes(execution_plan: dict, reserved_paths: dict[str, str]) -> None:
    if not reserved_paths:
        return
    for operation in execution_plan.get("render_ops", []):
        prototype_path = operation.get("prototype_path")
        if prototype_path in reserved_paths:
            operation["prototype_path"] = reserved_paths[prototype_path]


def add_bookmarks(document: Path, paragraph_path: str, bookmarks: list[dict]) -> None:
    for bookmark in bookmarks:
        name = bookmark.get("name")
        if not name:
            continue
        officecli_add(document, paragraph_path, element_type="bookmark", props={"name": name})


def should_direct_create_paragraph(operation: dict, *, prefer_direct_create: bool) -> bool:
    if prefer_direct_create:
        return True
    if operation.get("block_type") == "list_item":
        return True
    return not bool(operation.get("prototype_path"))


def paragraph_create_props(operation: dict) -> dict:
    create_props = dict(operation.get("set_props") or {})
    fallback_style = operation.get("fallback_style")
    if fallback_style and "style" not in create_props:
        create_props["style"] = fallback_style
    return create_props


def is_batchable_simple_paragraph(operation: dict, *, prefer_direct_create: bool) -> bool:
    return (
        operation.get("kind") == "paragraph"
        and should_direct_create_paragraph(operation, prefer_direct_create=prefer_direct_create)
        and not operation.get("append_runs")
        and not operation.get("bookmarks")
    )


def batch_add_simple_paragraphs(
    document: Path,
    anchor_path: str | None,
    operations: list[dict],
    *,
    chunk_size: int = DEFAULT_PARAGRAPH_BATCH_CHUNK_SIZE,
) -> tuple[str | None, list[str]]:
    if not operations:
        return anchor_path, []

    end_anchor = anchor_path
    all_document_paths: list[str] = []

    for chunk_end in range(len(operations), 0, -chunk_size):
        chunk_start = max(0, chunk_end - chunk_size)
        chunk = operations[chunk_start:chunk_end]

        commands: list[dict] = []
        for operation in reversed(chunk):
            command: dict = {
                "command": "add",
                "parent": "/body",
                "type": "paragraph",
                "props": paragraph_create_props(operation),
            }
            if anchor_path is None:
                command["index"] = 0
            else:
                command["after"] = anchor_path
            commands.append(command)

        payload = officecli_batch_commands(document, commands, stop_on_error=True)
        batch_data = payload.get("data") if isinstance(payload, dict) and payload.get("data") is not None else payload
        results = batch_data.get("results", []) if isinstance(batch_data, dict) else []
        paths_in_command_order: list[str] = []
        for result in results:
            path = extract_added_path(result, element_type="paragraph", parent="/body")
            if path is None:
                raise ValueError("OfficeCLI batch add paragraph không trả về path mới.")
            paths_in_command_order.append(path)

        if not paths_in_command_order:
            continue

        if chunk_end == len(operations):
            end_anchor = paths_in_command_order[0]

        all_document_paths = list(reversed(paths_in_command_order)) + all_document_paths

    return end_anchor, all_document_paths


def render_paragraph(document: Path, anchor_path: str | None, operation: dict, *, prefer_direct_create: bool = False) -> str:
    prototype_path = operation.get("prototype_path")
    set_props = dict(operation.get("set_props") or {})
    fallback_style = operation.get("fallback_style")

    if should_direct_create_paragraph(operation, prefer_direct_create=prefer_direct_create):
        payload = officecli_add(
            document,
            "/body",
            element_type="paragraph",
            props=paragraph_create_props(operation),
            after=anchor_path,
            index=0 if anchor_path is None else None,
        )
    elif prototype_path:
        try:
            payload = officecli_add(
                document,
                "/body",
                element_type="paragraph",
                from_path=str(prototype_path),
                after=anchor_path,
                index=0 if anchor_path is None else None,
            )
        except OfficeCliError:
            payload = None
            if set_props or fallback_style:
                create_props = dict(set_props)
                if fallback_style and "style" not in create_props:
                    create_props["style"] = fallback_style
                payload = officecli_add(
                    document,
                    "/body",
                    element_type="paragraph",
                    props=create_props,
                    after=anchor_path,
                    index=0 if anchor_path is None else None,
                )
    else:
        create_props = dict(set_props)
        if fallback_style and "style" not in create_props:
            create_props["style"] = fallback_style
        payload = officecli_add(
            document,
            "/body",
            element_type="paragraph",
            props=create_props,
            after=anchor_path,
            index=0 if anchor_path is None else None,
        )

    paragraph_path = extract_added_path(payload, element_type="paragraph", parent="/body")
    if paragraph_path is None:
        raise ValueError("OfficeCLI add paragraph không trả về path mới.")

    if prototype_path and set_props:
        officecli_set(document, paragraph_path, props=set_props)

    for run in operation.get("append_runs", []):
        text_value = str(run.get("text") or "")
        if not text_value:
            continue
        officecli_add(document, paragraph_path, element_type="run", props=run)

    add_bookmarks(document, paragraph_path, operation.get("bookmarks", []))
    return paragraph_path


def estimate_minimum_officecli_calls(execution_plan: dict, reserved_prototype_count: int, rewritten_toc_count: int = 0) -> int:
    remove_count = len(execution_plan.get("remove_batch_commands", []))
    remove_batches = (remove_count + DEFAULT_REMOVE_BATCH_CHUNK_SIZE - 1) // DEFAULT_REMOVE_BATCH_CHUNK_SIZE if remove_count else 0
    render_ops = execution_plan.get("render_ops", [])
    paragraph_set_calls = len(
        [
            operation
            for operation in render_ops
            if operation.get("kind") == "paragraph" and operation.get("prototype_path") and operation.get("set_props")
        ]
    )
    paragraph_add_calls = len([operation for operation in render_ops if operation.get("kind") == "paragraph"])
    table_add_calls = len([operation for operation in render_ops if operation.get("kind") == "table"])
    append_run_calls = sum(len(operation.get("append_runs", [])) for operation in render_ops if operation.get("kind") == "paragraph")
    bookmark_add_calls = sum(len(operation.get("bookmarks", [])) for operation in render_ops if operation.get("kind") == "paragraph")
    table_cell_set_calls = sum(
        len(row.get("cells", []))
        for operation in render_ops
        if operation.get("kind") == "table"
        for row in operation.get("rows", [])
    )
    reserved_cleanup_calls = reserved_prototype_count

    return (
        remove_batches
        + paragraph_add_calls
        + table_add_calls
        + paragraph_set_calls
        + append_run_calls
        + bookmark_add_calls
        + table_cell_set_calls
        + reserved_prototype_count
        + reserved_cleanup_calls
        + rewritten_toc_count
        + 3
    )


def render_table(document: Path, anchor_path: str | None, operation: dict) -> str:
    payload = officecli_add(
        document,
        "/body",
        element_type="table",
        props={"rows": operation.get("row_count", 0), "cols": operation.get("column_count", 0)},
        after=anchor_path,
        index=0 if anchor_path is None else None,
    )
    table_path = extract_added_path(payload, element_type="table", parent="/body")
    if table_path is None:
        raise ValueError("OfficeCLI add table không trả về path mới.")

    for row_index, row in enumerate(operation.get("rows", []), start=1):
        for column_index, cell in enumerate(row.get("cells", []), start=1):
            props = {"text": str(cell.get("text") or "")}
            if row.get("header"):
                props["bold"] = True
            officecli_set(document, f"{table_path}/tr[{row_index}]/tc[{column_index}]", props=props)

    return table_path


def render_operation(document: Path, anchor_path: str | None, operation: dict, *, prefer_direct_create: bool = False) -> str:
    if operation.get("kind") == "table":
        return render_table(document, anchor_path, operation)
    return render_paragraph(document, anchor_path, operation, prefer_direct_create=prefer_direct_create)


def rewrite_toc_fields(document: Path) -> list[str]:
    rewritten_paths: list[str] = []

    for toc in officecli_query(document, "toc"):
        path = toc.get("path")
        if not path:
            continue
        toc_format = toc.get("format", {})
        props = {}
        if toc_format.get("levels"):
            props["levels"] = toc_format["levels"]
        props["hyperlinks"] = bool(toc_format.get("hyperlinks", True))
        props["pageNumbers"] = True
        if not props:
            continue
        officecli_set(document, str(path), props=props)
        rewritten_paths.append(str(path))

    return rewritten_paths


def refresh_fields_if_supported(document: Path, rewritten_tocs: list[str]) -> tuple[str, bool]:
    if not rewritten_tocs:
        return ("none", False)

    if os.name != "nt":
        return ("rewrite-toc-fields-on-open", False)

    try:
        officecli_refresh(document)
    except OfficeCliError:
        return ("rewrite-toc-fields-on-open", False)

    return ("officecli-refresh", True)


def direct_body_child_count(document: Path) -> int:
    return len(direct_body_children(document))


def execute_remove_batch(document: Path, execution_plan: dict, chunk_size: int = DEFAULT_REMOVE_BATCH_CHUNK_SIZE) -> dict:
    commands = execution_plan.get("remove_batch_commands", [])
    if not commands:
        return {"summary": {"total": 0, "executed": 0, "succeeded": 0, "failed": 0, "skipped": 0, "chunks": 0}, "results": []}

    total_succeeded = 0
    total_failed = 0
    total_chunks = 0
    all_results = []
    for i in range(0, len(commands), chunk_size):
        chunk = commands[i:i + chunk_size]
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

    return {"summary": {"total": len(commands), "executed": len(commands), "succeeded": total_succeeded, "failed": total_failed, "skipped": 0, "chunks": total_chunks}, "results": all_results}


def resolve_anchor_after_remove(document: Path, original_anchor: str | None) -> str | None:
    if original_anchor is None:
        return None
    try:
        body_results = officecli_query(document, "paragraph")
        body_paths = [r.get("path", "") for r in body_results if str(r.get("path", "")).startswith("/body/")]
        if body_paths:
            return body_paths[-1]
    except Exception:
        pass
    return original_anchor


def execute_plan(template_file: Path, target_file: Path, execution_plan: dict) -> dict:
    shutil.copy2(template_file, target_file)

    before_count = direct_body_child_count(target_file)
    reserved_prototype_paths = reserve_prototype_paths(target_file, execution_plan)
    apply_reserved_prototypes(execution_plan, reserved_prototype_paths)
    remove_batch_result = execute_remove_batch(target_file, execution_plan)
    if (remove_batch_result.get("summary") or {}).get("failed", 0):
        raise RuntimeError("Remove batch thất bại; build bị dừng để tránh tài liệu nửa chừng.")

    original_anchor = execution_plan.get("selected_replace_range", {}).get("insert_after_path")
    current_anchor = resolve_anchor_after_remove(target_file, original_anchor)
    inserted_paths: list[str] = []
    prefer_direct_create = not bool(execution_plan.get("selected_replace_range", {}).get("remove_paths", []))
    batched_paragraph_count = 0
    officecli_open(target_file)
    try:
        batchable_buffer: list[dict] = []

        def flush_batchable_buffer() -> None:
            nonlocal current_anchor, batched_paragraph_count
            if not batchable_buffer:
                return
            current_anchor, batch_paths = batch_add_simple_paragraphs(target_file, current_anchor, batchable_buffer)
            inserted_paths.extend(batch_paths)
            batched_paragraph_count += len(batchable_buffer)
            batchable_buffer.clear()

        for operation in execution_plan.get("render_ops", []):
            if is_batchable_simple_paragraph(operation, prefer_direct_create=prefer_direct_create):
                batchable_buffer.append(operation)
                continue

            flush_batchable_buffer()
            current_anchor = render_operation(target_file, current_anchor, operation, prefer_direct_create=prefer_direct_create)
            inserted_paths.append(current_anchor)

        flush_batchable_buffer()

        for reserved_path in reserved_prototype_paths.values():
            officecli_remove(target_file, reserved_path)

        rewritten_tocs = rewrite_toc_fields(target_file)
        officecli_save(target_file)
    finally:
        officecli_close(target_file)

    after_count = direct_body_child_count(target_file)
    refresh_strategy, refreshed = refresh_fields_if_supported(target_file, rewritten_tocs)
    return {
        "body_children_before": before_count,
        "body_children_after": after_count,
        "remove_scope": execution_plan.get("selected_replace_range", {}).get("remove_scope", "direct-body-children"),
        "replaced_child_count": len(execution_plan.get("remove_batch_commands", [])),
        "remove_batch_summary": remove_batch_result.get("summary", {}),
        "inserted_block_count": len(execution_plan.get("render_ops", [])),
        "inserted_paths": inserted_paths,
        "reserved_prototype_count": len(reserved_prototype_paths),
        "required_prototype_reservations": len(prototype_paths_requiring_reservation(execution_plan)),
        "body_replaced": bool(execution_plan.get("render_ops")),
        "dirty_field_count": 0,
        "update_fields_on_open": refreshed,
        "field_refresh_strategy": refresh_strategy,
        "toc_rewrites": rewritten_tocs,
        "resident_mode": True,
        "prefer_direct_create": prefer_direct_create,
        "batched_simple_paragraph_ops": batched_paragraph_count,
        "estimated_minimum_officecli_calls": estimate_minimum_officecli_calls(
            execution_plan,
            reserved_prototype_count=len(reserved_prototype_paths),
            rewritten_toc_count=len(rewritten_tocs),
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sinh build_report.json cho pipeline DOCX.")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    plan = read_json(run_dir / "plan.json")
    run_state = read_json(run_dir / "run.json")
    template_profile = read_json(run_dir / "template_profile.json")
    execution_plan = read_json(run_dir / "execution_plan.json") if (run_dir / "execution_plan.json").exists() else {"status": "blocked"}

    target_file = Path(plan.get("target_file"))
    template_file = Path(plan.get("template_file"))
    officecli_version = ensure_officecli_available()
    blocking_reasons = collect_build_blocking_reasons(plan, execution_plan)
    build_failed = False

    if plan.get("mode") != "preserve-template-scaffold":
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Script build hiện chỉ cho phép mode preserve-template-scaffold trong workflow DOCX an toàn.",
            "body_replaced": False,
            "officecli_version": officecli_version,
        }
        run_state["status"] = "blocked"
    elif plan.get("status") != "ready-for-execution" or execution_plan.get("status") != "ready":
        build_report = {
            "status": "blocked",
            "mode": plan.get("mode"),
            "target_file": plan.get("target_file"),
            "message": "Build bị chặn do plan hoặc execution graph chưa sẵn sàng an toàn.",
            "body_replaced": False,
            "officecli_version": officecli_version,
            "blocking_reasons": blocking_reasons,
        }
        run_state["status"] = "blocked"
    else:
        try:
            replacement_stats = execute_plan(template_file=template_file, target_file=target_file, execution_plan=execution_plan)
            build_report = {
                "status": "completed",
                "mode": plan.get("mode"),
                "target_file": plan.get("target_file"),
                "officecli_version": officecli_version,
                "selected_replace_range": execution_plan.get("selected_replace_range"),
                "preserve": plan.get("preserve", []),
                "preserve_zones": plan.get("preserve_zones", []),
                "style_map": plan.get("style_map", {}),
                "prototype_roles": plan.get("prototype_roles", {}),
                "render_summary": execution_plan.get("render_summary", {}),
                "template_header_count": template_profile.get("header_count", 0),
                "template_footer_count": template_profile.get("footer_count", 0),
                **replacement_stats,
                "message": "Đã thực thi execution graph DOCX bằng remove batch trên direct body children và prototype-driven rendering qua OfficeCLI.",
            }
            run_state["status"] = "built"
        except Exception as exc:
            build_report = {
                "status": "failed",
                "mode": plan.get("mode"),
                "target_file": plan.get("target_file"),
                "officecli_version": officecli_version,
                "selected_replace_range": execution_plan.get("selected_replace_range"),
                "blocking_reasons": blocking_reasons,
                "body_replaced": False,
                "message": f"Build DOCX thất bại: {exc}",
            }
            run_state["status"] = "failed"
            build_failed = True

    run_state.setdefault("artifacts", {})["build_report"] = str(run_dir / "build_report.json")

    write_json(run_dir / "build_report.json", build_report)
    write_json(run_dir / "run.json", run_state)

    if build_failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()