# Office Auto Bootstrap

## Bắt đầu mỗi session
1. Đọc `.opencode/memory/project.md` để nạp conventions của repo.
2. Chỉ đọc `.opencode/memory/task_current.md` khi cần resume session đang dở.
3. Nếu task mới, khởi tạo `task_current.md` trước khi gọi pipeline.

## Quy Định Vận Hành (v3 — deterministic compiler)

- **Triết lý:** LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code.
- **Agent chính:** `orchestrator` — điều phối deterministic pipeline. LLM chỉ quyết định style_map + replace_range.
- **Nguyên tắc context economy:** Orchestrator distill data, truyền inline vào subagent prompt. Subagents KHÔNG tự đọc file nặng.
- **Không gọi trực tiếp** OfficeCLI MCP tools; luôn ưu tiên MCP tools trong `mcp/tools/*.ts`.
- **Không đọc** artifact trong `.office-auto/state/<run_id>/` nếu chưa xác định chính xác `run_id`.
- MCP server (`mcp/office-auto-server.ts` · `mcp/tools/*.ts`) là source of truth cho tool call order và preconditions.

## Available Tools

| MCP Tool | File | Dùng bởi |
|---|---|---|
| `inspectTemplate` | `mcp/tools/inspect.ts` | **inspector** subagent |
| `prepareInsertPlan` | `mcp/tools/scaffold.ts` | **orchestrator** (sau inspect) |
| `validateOps` | `mcp/tools/validate.ts` | **validator** subagent |
| `applyOps` | `mcp/tools/execute.ts` | **applier** subagent |
| `runQA` | `mcp/tools/qa.ts` | **reviewer** subagent |
| `reviewOutput` | `mcp/tools/review.ts` | **reviewer** subagent |
| `refreshFields` | `mcp/tools/refresh.ts` | **orchestrator** (sau review passed) |
| `generateOpsFromSourcePacket` | `mcp/tools/compiler.ts` | **orchestrator** (sau mapping) |
| `runFullPipeline` | `mcp/tools/orchestrator.ts` | **full deterministic pipeline** |
| `runPipelineFromOps` | `mcp/tools/orchestrator.ts` | **legacy** (backward compat) |

## Cấu trúc Topology của Tác nhân (Agent Topology — v3)

### 1. Vai trò của Orchestrator (Tác nhân chính)

* **Quản lý dữ liệu (Nắm giữ):** scaffold_summary, style_map, replace_range, run_dir.
* **Xử lý tác vụ (Tự thực hiện):**
  * Chạy inspect, source_packet, compile, validate, apply qua MCP tools.
  * Spawn MapperAgent để quyết định style_map + replace_range (nếu cần).
  * Spawn ReviewerAgent để semantic review (nếu cần).
* **KHÔNG tự viết execution_ops.json** — việc của compiler.

---

### 2. Hệ thống Subagents

| Subagent | Chức năng chính | Tool call |
| --- | --- | --- |
| **Inspector** | Kiểm tra Template, xuất JSON rút gọn | `inspectTemplate` |
| **Mapper** | Quyết định style_map + replace_range (SMALL output < 5KB) | `write_file` (ghi 2 file nhỏ) |
| **Validator** | Xác thực execution_ops (hard-block trên high severity) | `validateOps` |
| **Applier** | Thực thi execution_ops | `applyOps` |
| **Reviewer** | Đọc kết quả, đánh giá | `reviewOutput` + `runQA` |

---

### 3. Quy tắc vận hành (Operational Rules)

* **Cơ chế spawn:** Subagents chỉ được phép khởi tạo bởi **Orchestrator** thông qua `Task tool`.
* **Định dạng giao tiếp:** Output của các Subagents bắt buộc phải kết thúc bằng một **JSON block** để Orchestrator có thể parse chính xác.
* **Phân cấp giới hạn:** Subagents **không được phép** tự khởi tạo các Subagent khác (quyền này bị deny trên toàn bộ hệ thống).

### 4. Topology Contract (HARD — không có ngoại lệ)

Orchestrator KHÔNG bao giờ:
- Gọi tool trực tiếp (kể cả bash write_file cho artifact)
- Reasoning > 2 turns về cùng một quyết định
- Generate ops content inline trong thinking
- Tự viết execution_ops.json — việc của compiler
- Tự copy nội dung markdown vào ops

Orchestrator CHỈ:
- Gọi bash để đọc/verify (grep, cat, python3 -m json.tool)
- Spawn subagent qua Task tool
- Parse JSON block output từ subagent
- Quyết định bước tiếp theo dựa trên parse output

## Retry Protocol
- Retry loop do orchestrator quản lý, KHÔNG phải subagent
- Mỗi retry: orchestrator đã có scaffold_summary + source_packet → chỉ re-compile/re-validate
- Re-inspect template: CHỈ khi template_file thay đổi
- Max retry: 3 lần

## Pipeline Flow (v3 — deterministic compiler)

```
1. Inspect template        (script, NO LLM)
2. Parse markdown AST      (script, NO LLM)
3. Resolve mapping         (LLM decides style_map + replace_range, small output only)
4. Compile ops             (script, NO LLM — source_packet_to_ops.py)
5. Strict validate         (script, hard block on error — validate_ops_strict.py)
6. Apply ops               (script, NO LLM)
7. Verify output           (script, NO LLM — verify_docx_output.py)
8. QA + Review             (script, LLM optional for review)
9. Refresh TOC             (script, NO LLM)
10. Final gate             (CODE, not prompt — final_gate.py)
```
