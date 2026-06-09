# task.md

Contract chuẩn cho prompt tối giản trong workspace này.

- Input mặc định: `noidung.md`
- Template mặc định: `format_template.docx`
- Output mặc định: `report.docx`
- Flow chuẩn: `inspectTemplate` → `validateExecutionOps` → `applyExecutionOps` → `readResult`
- Nếu cần chạy trọn vòng: dùng `runPipeline`

Ghi chú:

- Không tự giả định run cũ nếu user chưa chỉ rõ `run_id`.
- Giữ `preserve-template-scaffold` làm nguyên tắc mặc định.
- Ưu tiên primitive tools trong `.opencode/tools/docx_pipeline.ts`.

## Constraint (HARD)

- Orchestrator KHÔNG reasoning inline về nội dung DOCX.
- Orchestrator CHỈ được: gọi tool, spawn subagent, read artifact.
- Mọi reasoning về structure → spawn Planner subagent với context đã distill.
- Tổng token inline reasoning của Orchestrator < 500 tokens/step.
- KHÔNG generate execution_ops.json inline — luôn spawn Planner subagent để viết.
