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

## Kiến trúc mặc định

Workspace này mặc định đi theo kiến trúc mới trong `issue.md`:

1. `docx_inspect_raw.py` trả raw inspection của template.
2. LLM đọc trực tiếp markdown nguồn và tự viết `execution_ops.json`.
3. `docx_validate_ops.py` chỉ cảnh báo sai anchor/style/path.
4. `compile_execution_ops.py` + `build_docx.py` + `post_process_docx.py` thực thi cơ học.
5. `docx_read_result.py` đọc output ra text/structure để model tự verify.

Pipeline heuristic cũ vẫn còn trong repo như legacy/debug path, nhưng không còn là đường mặc định cho agent.

## Runtime requirement

- Cần có `pandoc` trong PATH vì các phase normalize/roundtrip semantic QA đã chuyển từ MarkItDown sang Pandoc.

## Thứ tự stage chuẩn

Flow mặc định cho agent:

1. `docx_inspect_raw.py`
2. LLM tự viết `execution_ops.json`
3. `docx_validate_ops.py`
4. `compile_execution_ops.py`
5. `build_docx.py`
6. `post_process_docx.py`
7. `docx_read_result.py`

Roundtrip/QA legacy vẫn có thể dùng khi cần chẩn đoán sâu, nhưng không còn là primitive default của agent.

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

Agent/OpenCode nên dùng primitive flow thay vì wrapper legacy. Nếu cần chạy bằng script, dùng nhánh `--ops-file`:

```bash
python scripts/build_report.py \
  --run-dir .office-auto/state/<run_id> \
  --source-file noidung.md \
  --template-file format_template.docx \
  --ops-file execution_ops.json \
  --target-file report.docx
```

Sau khi build xong, lấy nhanh artifact review mới nhất:

```bash
python scripts/latest_review_artifacts.py
```

## OpenCode và VS Code

Workspace đã được cấu hình để OpenCode/Copilot Agent đi đúng workflow chuẩn:

- `.opencode/AGENTS.md`: routing + hard gate.
- `task.md`: contract chuẩn cho prompt tối giản.
- `.vscode/mcp.json`: OfficeCLI MCP cho workspace.
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