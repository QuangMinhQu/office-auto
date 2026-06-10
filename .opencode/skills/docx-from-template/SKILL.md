---
name: docx-from-template
description: Tạo file Word (.docx) từ template theo kiến trúc LLM-as-reasoning: model tự suy luận và chỉ gọi primitive tools cơ học.
lifecycle: llm-as-reasoning default
license: MIT
---

# SKILL: DOCX_FROM_TEMPLATE

## Mục tiêu
Skill này là contract mặc định để agent tạo `.docx` theo kiến trúc mới trong `issue.md`.

LLM là reasoning engine chính. Scripts và custom tools chỉ làm 4 việc cơ học:
- inspect template
- validate execution ops
- apply execution ops
- read result

## Khi nào dùng skill này
- Tạo `report.docx` từ `format_template.docx`.
- Rebuild phần nội dung chính từ Markdown nhưng giữ scaffold của template.

## Mode mặc định
- `preserve-template-scaffold`

## Inputs bắt buộc
- `template_file`
- `source_file`
- `target_file`

## Single-agent vs Multi-agent Mode

Skill này có 2 mode chạy, tùy vào môi trường:

- **Multi-agent mode:** Khi chạy qua OpenCode với orchestrator agent → dùng multi-agent topology trong `AGENTS.md`. Orchestrator spawn subagents (Inspector, Planner, Validator, Applier, Reviewer) qua Task tool. Dùng mode này khi cần retry loop, chunked planning, và verification chặt chẽ tự động.
- **Single-agent mode (primitive flow dưới đây):** Khi agent tự chạy standalone, không spawn subagents. LLM tự làm tất cả các bước: inspect, suy luận, viết ops, validate, apply, read result.

## Primitive flow bắt buộc (single-agent mode)
1. Gọi `inspectTemplate` để lấy `template_inspection_raw.json`.
2. Đọc trực tiếp markdown nguồn bằng file read.
3. Tự suy luận replace range, style map, anchors, bookmarks, TOC intent.
4. Tự viết `.office-auto/state/<run_id>/execution_ops.json`.
5. Gọi `validateOps`.
6. Nếu có warnings, sửa `execution_ops.json` rồi validate lại.
7. Gọi `applyOps`.
8. Gọi `reviewOutput`.
9. So output readback với markdown nguồn và template intent; nếu chưa đúng thì sửa ops và apply lại.

## Invariants
- Không đưa reasoning về `profile_template.py`, `plan_mapping.py`, `compile_execution_plan.py` trong flow mặc định.
- Không coi `body` là toàn bộ tài liệu; phải giữ scaffold của template.
- Không xóa trắng toàn bộ `w:body` để thay nội dung mới.
- Nếu chưa explicit được `selected_replace_range` hoặc cặp `remove_paths` + `insert_after_path`, phải inspect lại và sửa ops; không build liều.
- Mỗi paragraph/heading model viết vào `execution_ops.json` nên explicit `style`, và khi cần thì explicit `run_props` hoặc `bookmarks`.
- Validator chỉ là safety net; warnings phải được xem là input để sửa ops, không phải lý do bỏ qua verification.

## Routing tối thiểu
- Chỉ load `officecli-docx` khi cần command/schema cụ thể.
- Load `md-to-docx-pipeline` để lấy primitive scripts/tools và artifact contracts.
- Không dùng hidden subagent topology cũ.
- Không coi wrapper heuristic cũ là fallback mặc định.

## Execution Contract cho prompt chỉ có `@task.md`
- Nếu task chỉ cung cấp `task.md`, mặc định dùng: `noidung.md`, `format_template.docx`, `report.docx`, `.office-auto/state/<run_id>`.
- Agent vẫn phải tự dựng đầy đủ `execution_ops.json` và để lại artifact inspect/validate/apply/read-result.
- Không được nhảy từ đọc `task.md` sang chạy planner heuristic cũ rồi kết luận xong.

## Minimal `execution_ops.json`
```json
{
  "preserve": ["headers-footers", "toc"],
  "selected_replace_range": {
    "status": "resolved",
    "remove_scope": "direct-body-children",
    "insert_after_path": "/body/p[@paraId=49349C0D]",
    "remove_paths": ["/body/p[@paraId=04C2E2D0]"],
    "preserve_zones": ["front-matter"]
  },
  "ops": [
    {
      "op": "insert_paragraph_after",
      "anchor": "selected_replace_range.insert_after_path",
      "role": "h1",
      "style": "Heading1",
      "text": "CƠ SỞ LÝ THUYẾT"
    }
  ]
}
```

## Delivery Rule
Chỉ coi là xong khi:
- `execution_ops.json` là artifact reasoning trung tâm của run.
- `build_report.json` cho thấy build hoàn tất.
- `result_readback.json` cho thấy structure/text phù hợp với markdown nguồn và template intent.
- Scaffold quan trọng của template vẫn còn.
- Không còn dấu hiệu residue template, anchor sai, hoặc drift lớn trong output readback.