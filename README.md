# office-auto

Repo này chốt một workflow chuẩn duy nhất cho Markdown -> DOCX bằng OpenCode + OfficeCLI. Mục tiêu không phải tái tạo tài liệu từ đầu, mà là giữ scaffold của template Word và chỉ thay vùng nội dung chính theo contract `preserve-template-scaffold`.

## Workflow chuẩn hiện tại

- Đầu vào mặc định của workspace: `noidung.md`.
- Template mặc định: `format_template.docx`.
- File đích mặc định: `report.docx`.
- Primitive tools chuẩn: `inspectTemplate`, `validateExecutionOps`, `applyExecutionOps`, `readResult`.
 - Contract mặc định cho agent: `task.md`.

Nếu người dùng chỉ prompt ngắn kiểu “sinh report.docx mới” hoặc “đọc task.md và làm”, agent nên đi đúng đường chuẩn trên thay vì tự ghép lệnh ad-hoc.
Session mới khong duoc mac dinh tai su dung `manual-run` hoac artifact cu neu nguoi dung chua chi ro run can resume.

## Kiến trúc: LLM-as-Reasoning-Engine

Workspace đi theo kiến trúc mới trong `issue.md`: **"Chỉ những gì không thể suy luận mới trở thành tool. Những gì suy luận được thì LLM làm."**

### 5-step pipeline

```
1. docx_inspect.py          → raw dump (zero heuristics, zero interpretation)
      ↓ docx_inspect_output.json
2. [LLM REASONING]          ← LLM đọc raw dump + content, viết execution_ops.json
      ↓ execution_ops.json
3. docx_validate_ops.py     → warn-only validator (không block execution)
      ↓ execution_ops_validation.json
4. execute_execution_ops.py → mechanical executor (OfficeCLI)
      ↓ report.docx
5. docx_read_result.py      → read back result để LLM verify
      ↓ result_readback.json
6. qa_docx.py / review_docx.py → metrics & summary report
```

### Nguyên lý thiết kế

- **Raw data only**: `None` = inherited (chưa resolved), không pre-classification, không `heading_level` fields
- **Scripts = hands, LLM = brain**: Không có heuristic scripts (profile_template, plan_mapping, compile_execution_plan...)
- **Warn-only validation**: Validator chỉ báo cảnh báo, không block execution
- **6 ops supported**: `insert_paragraph_after`, `insert_paragraph_before`, `remove`, `update_text`, `insert_table`/`insert_table_after`, `set_page_layout`

### Old scripts

Các heuristic scripts cũ đã được archive vào `scripts/legacy/` — không còn được gọi bởi pipeline mới.

## Artifact quan trọng

Mỗi run nằm dưới `.office-auto/state/<run_id>/` và tối thiểu nên có:

- `preflight.json`
- `topology.json`
- `run.json`
- `template_inspection_raw.json`
- `execution_ops.json`
- `execution_ops_validation.json`
- `plan.json`
- `execution_plan.json`
- `build_report.json`
- `result_readback.json`

Schema run state nằm ở `.office-auto/run.schema.json`.

## Hard gate kỹ thuật

- Không được xóa trắng toàn bộ `w:body` trong mode `preserve-template-scaffold`.
- `replace_ranges` phải được resolve bằng artifact, không được suy đoán trong prompt.
- Semantic QA và structural QA là gate thật; `validate pass` một mình không đủ.
- TOC, list-of-figures, list-of-tables, bookmark, PAGEREF, section settings, header/footer vẫn là phần bắt buộc của output.
- Review layer là bước bàn giao cuối để soi drift về align, font, cỡ chữ và spacing mà QA thuần JSON có thể không bộc lộ rõ.

## Cách chạy

 ### Với build_report.py (legacy wrapper)

```bash
# Phase 1: Raw dump template, LLM viết execution_ops.json
python scripts/build_report.py --phase inspect --run-dir .office-auto/state/<run_id>

# Phase 2: Validate + Execute + Read Result
python scripts/build_report.py --phase execute --run-dir .office-auto/state/<run_id>

# Phase 3: QA + Review
python scripts/build_report.py --phase qa --run-dir .office-auto/state/<run_id>

# Hoặc chạy full pipeline
python scripts/build_report.py --phase all --run-dir .office-auto/state/<run_id>
```

 ### Với primitive tools (agent flow)

```bash
# 1. Inspect
python .opencode/skills/md-to-docx-pipeline/scripts/docx_inspect.py \
  --template-file format_template.docx --run-dir .office-auto/state/<run_id>

# 2. LLM writes execution_ops.json (manual or automated)

# 3. Validate
python .opencode/skills/md-to-docx-pipeline/scripts/docx_validate_ops.py \
  --run-dir .office-auto/state/<run_id>

# 4. Execute
python .opencode/skills/md-to-docx-pipeline/scripts/execute_execution_ops.py \
  --run-dir .office-auto/state/<run_id>

# 5. Read result
python .opencode/skills/md-to-docx-pipeline/scripts/docx_read_result.py \
  --run-dir .office-auto/state/<run_id>
```

Sau khi build xong, lấy nhanh artifact review mới nhất:

```bash
python scripts/latest_review_artifacts.py
```

## OpenCode và VS Code

Workspace đã được cấu hình để OpenCode/Copilot Agent đi đúng workflow chuẩn:

- `.opencode/AGENTS.md`: routing + hard gate.
- `task.md`: contract chuẩn cho prompt tối giản.
- `.opencode/tools/docx_pipeline.ts`: custom tools chuẩn của workspace.
- `.vscode/tasks.json`: task build DOCX, latest review summary, unit tests.
- `.vscode/settings.json`: bật MCP auto-start và unittest config.

Luu y orchestration:
- `task_current.md` chi la session state duoc ghi de resume, khong phai default input cho moi session.
- Artifact trong `.office-auto/state/<run_id>/`, `manual-run/`, `.manual-run/` chi duoc doc khi dung voi run ma nguoi dung dang noi den.

Chi tiết setup và cách vận hành nằm ở `docs/opencode-agent-setup.md`.

## Tài liệu nên đọc

- `task.md`: contract mặc định cho build DOCX của repo.
- `docs/opencode-agent-setup.md`: setup agent/workspace.
- `docs/docx-issues-03-qa-observability.md`: observability và artifact summary.
- `docs/docx-issues-04-roadmap.md`: roadmap còn lại sau khi đã chốt builder + review layer + workspace automation.
- `docs/docx-external-research.md`: nghiên cứu các tool/direct-DOCX và vì sao chúng chỉ nên bổ trợ review, không thay builder hiện tại.

## Kiểm thử

- Unit tests cho parser, planner, style-map, grounding, builder utilities và review layer nằm trong `tests/test_docx_pipeline.py`.
- Khi chỉ cần rà artifact mới nhất mà không mở tay từng file JSON, dùng `scripts/latest_review_artifacts.py`.
