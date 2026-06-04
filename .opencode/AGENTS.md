# Office Auto Bootstrap

## Bắt đầu mỗi session
1. Đọc `.opencode/memory/project.md` để nạp conventions của repo.
2. Chỉ đọc `.opencode/memory/task_current.md` khi cần resume session đang dở.
3. Nếu task mới, khởi tạo `task_current.md` trước khi gọi pipeline.

## Quy Định Vận Hành

- **Agent chính:** `orchestrator`.
- **Không gọi trực tiếp** OfficeCLI MCP tools; luôn ưu tiên custom tools trong `.opencode/tools`. Bash chỉ dùng cho file operations (read/write/edit JSON).
- **Không đọc** artifact trong `.office-auto/state/<run_id>/` nếu chưa xác định chính xác `run_id`.
- **Không trộn** custom tools với bash ad-hoc trong cùng một flow build/verify.
- MCP schema (`.opencode/tools/docx_pipeline.ts`) là source of truth cho tool call order và preconditions.

## Available Tools

Do not glob `.opencode/tools` to discover these. They are pre-loaded OpenCode plugin tools.

- `inspectTemplate` - inspect DOCX template
- `validateExecutionOps` - validate `execution_ops.json`
- `applyExecutionOps` - apply ops to produce output DOCX
- `prepareInsertPlan` - build reasoning scaffold
- `reviewOutput` - semantic review
- `readResult` - verify output
- `runPipeline` - composite: inspect → validate → apply → read

Default inputs: template=`format_template.docx`, content=`noidung.md`, output=`report.docx`.
