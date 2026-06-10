# Office Auto Bootstrap

## Bắt đầu mỗi session
1. Đọc `.opencode/memory/project.md` để nạp conventions của repo.
2. Chỉ đọc `.opencode/memory/task_current.md` khi cần resume session đang dở.
3. Nếu task mới, khởi tạo `task_current.md` trước khi gọi pipeline.

## Quy Định Vận Hành

- **Agent chính:** `orchestrator` — nắm toàn bộ state, scaffold_summary, source_content.
- **Nguyên tắc context economy:** Orchestrator distill data, truyền inline vào subagent prompt. Subagents KHÔNG tự đọc file hệ thống nặng (docx_inspect_output.json, source markdown).
- **Không gọi trực tiếp** OfficeCLI MCP tools; luôn ưu tiên MCP tools trong `mcp/tools/*.ts`.
- **Không đọc** artifact trong `.office-auto/state/<run_id>/` nếu chưa xác định chính xác `run_id`.
- MCP server (`mcp/office-auto-server.ts` · `mcp/tools/*.ts`) là source of truth cho tool call order và preconditions.

## Available Tools

| MCP Tool | File | Dùng bởi |
|---|---|---|
| `inspectTemplate` | `mcp/tools/inspect.ts` | **inspector** subagent |
| `prepareInsertPlan` | `mcp/tools/scaffold.ts` | **orchestrator** (sau inspect, trước Planner) |
| `validateOps` | `mcp/tools/validate.ts` | **validator** subagent |
| `applyOps` | `mcp/tools/execute.ts` | **applier** subagent |
| `runQA` | `mcp/tools/qa.ts` | **reviewer** subagent (hard final gate) |
| `reviewOutput` | `mcp/tools/review.ts` | **reviewer** subagent |
| `refreshFields` | `mcp/tools/refresh.ts` | **orchestrator** (sau review passed) |
| `runFullPipeline` | `mcp/tools/orchestrator.ts` | **KHÔNG dùng trong normal flow** |

> **Note**: `.opencode/tools/docx_pipeline.ts` đã bị xóa. MCP server (`mcp/tools/*.ts`) là execution path duy nhất.

## Cấu trúc Topology của Tác nhân (Agent Topology)

Hệ thống vận hành theo mô hình phân cấp, trong đó **Orchestrator** đóng vai trò là tác nhân chủ chốt điều phối toàn bộ luồng công việc.

### 1. Vai trò của Orchestrator (Tác nhân chính)

* **Quản lý dữ liệu (Nắm giữ):** Chịu trách nhiệm quản lý các trạng thái và dữ liệu bao gồm: `scaffold_summary`, `source_content`, `execution_ops`, và `retry_count`.
* **Xử lý tác vụ (Tự thực hiện):**
* Phân tích cấu trúc tiêu đề (Markdown headings).
* Quản lý retry loop: khi Validator báo lỗi, spawn Planner với `retry_hint` mới (KHÔNG tự patch ops).



---

### 2. Hệ thống Subagents (Tác nhân phụ)

Các tác nhân phụ hoạt động dưới sự giám sát chặt chẽ của Orchestrator với quy định nghiêm ngặt:

| Subagent | Chức năng chính | Tool call (Số lượng) |
| --- | --- | --- |
| **Inspector** | Kiểm tra Template, xuất ra JSON rút gọn | 1 |
| **Planner** | Nhận dữ liệu inline, tạo `execution_ops` | 0 |
| **Validator** | Xác thực `execution_ops` (Pass/Warn/Fail) | 1 |
| **Applier** | Thực thi `execution_ops` để tạo kết quả | 1 |
| **Reviewer** | Đọc kết quả và đánh giá (Verdict) | 1 |

---

### 3. Quy tắc vận hành (Operational Rules)

Để đảm bảo tính nhất quán và kiểm soát, hệ thống tuân thủ các quy tắc sau:

* **Cơ chế spawn:** Subagents chỉ được phép khởi tạo bởi **Orchestrator** thông qua `Task tool`.
* **Định dạng giao tiếp:** Output của các Subagents bắt buộc phải kết thúc bằng một **JSON block** để Orchestrator có thể phân tích cú pháp (parse) chính xác.
* **Phân cấp giới hạn:** Subagents **không được phép** tự khởi tạo các Subagent khác (quyền này bị từ chối/deny trên toàn bộ hệ thống).

### 4. Topology Contract (HARD — không có ngoại lệ)

Orchestrator KHÔNG bao giờ:
- Gọi tool trực tiếp (kể cả bash write_file cho artifact)
- Reasoning > 2 turns về cùng một quyết định
- Generate ops content inline trong thinking
- Tự viết bất kỳ file artifact nào — chỉ subagent mới được write file

Orchestrator CHỈ:
- Gọi bash để đọc (grep, cat, python3 -m json.tool để verify)
- Spawn subagent qua Task tool
- Parse JSON block output từ subagent
- Quyết định bước tiếp theo dựa trên parse output

## Retry Protocol
- Retry loop do orchestrator quản lý, KHÔNG phải subagent
- Mỗi retry: orchestrator đã có scaffold_summary (cache từ Phase 1) → chỉ spawn Planner với retry_hint mới
- Re-inspect template: CHỈ khi template_file thay đổi
- Max retry: 3 lần
