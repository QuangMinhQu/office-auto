# office-auto

Repo này chốt một workflow chuẩn duy nhất cho Markdown -> DOCX bằng OpenCode + OfficeCLI. Mục tiêu không phải tái tạo tài liệu từ đầu, mà là giữ scaffold của template Word và chỉ thay vùng nội dung chính theo contract `preserve-template-scaffold`.

## Workflow chuẩn hiện tại

- Đầu vào mặc định của workspace: `noidung.md`.
- Template mặc định: `format_template.docx`.
- File đích mặc định: `report.docx`.
- Wrapper chuẩn: `scripts/build_report.py`.
- Contract mặc định cho agent: `task.md`.

Nếu người dùng chỉ prompt ngắn kiểu “sinh report.docx mới” hoặc “đọc task.md và làm”, agent nên đi đúng đường chuẩn trên thay vì tự ghép lệnh ad-hoc.

## Thứ tự stage chuẩn

Wrapper DOCX hiện hành chạy theo thứ tự sau:

1. `document_topology_detector.py`
2. `profile_template.py`
3. `template_suitability_report.py`
4. `prepare_template_scaffold.py` khi template lịch sử quá dày
5. `document_topology_detector.py` lại nếu đã derive `effective_template.docx`
6. `profile_template.py` lại nếu đã derive `effective_template.docx`
7. `template_suitability_report.py` lại sau profile cập nhật
8. `generate_markitdown_style_map.py`
9. `input_processor.py`
10. `extract_sample_content.py`
11. `parse_markdown.py`
12. `plan_mapping.py`
13. `compile_execution_plan.py`
14. `build_docx.py`
15. `post_process_docx.py`
16. `roundtrip_markitdown.py`
17. `qa_docx.py`
18. `review_docx.py`

`review_docx.py` chạy sau QA để `review_report.json` mang luôn `qa_status` cuối cùng của run.

## Artifact quan trọng

Mỗi run nằm dưới `.office-auto/state/<run_id>/` và tối thiểu nên có:

- `preflight.json`
- `topology.json`
- `template_suitability_report.json`
- `pipeline_report.json`
- `run.json`
- `template_preparation_report.json`
- `markitdown_style_map.txt`
- `normalized.md`
- `sample_content.md`
- `content_ast.json`
- `content_outline.json`
- `template_profile.json`
- `plan.json`
- `execution_plan.json`
- `build_report.json`
- `roundtrip_report.json`
- `qa_report.json`
- `review_report.json`
- `review_report.md`
- `review_screen.html`

Schema run state nằm ở `.office-auto/run.schema.json`.

## Hard gate kỹ thuật

- Không được xóa trắng toàn bộ `w:body` trong mode `preserve-template-scaffold`.
- `replace_ranges` phải được resolve bằng artifact, không được suy đoán trong prompt.
- Semantic QA và structural QA là gate thật; `validate pass` một mình không đủ.
- TOC, list-of-figures, list-of-tables, bookmark, PAGEREF, section settings, header/footer vẫn là phần bắt buộc của output.
- Review layer là bước bàn giao cuối để soi drift về align, font, cỡ chữ và spacing mà QA thuần JSON có thể không bộc lộ rõ.

## Cách chạy

Chạy đường chuẩn mặc định:

```bash
python scripts/build_report.py \
  --run-dir .office-auto/state/manual-run \
  --source-file noidung.md \
  --template-file format_template.docx \
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

Chi tiết setup và cách vận hành nằm ở `docs/opencode-agent-setup.md`.

## Tài liệu nên đọc

- `task.md`: contract mặc định cho build DOCX của repo.
- `docs/opencode-agent-setup.md`: setup agent/workspace.
- `docs/docx-issues-03-qa-observability.md`: observability và artifact summary.
- `docs/docx-issues-04-roadmap.md`: roadmap còn lại sau khi đã chốt builder + review layer + workspace automation.
- `docs/docx-external-research.md`: nghiên cứu các tool/direct-DOCX và vì sao chúng chỉ nên bổ trợ review, không thay builder hiện tại.
- `docs/style_spec.example.json`: mẫu override style map cho role pháp lý (`legal_chuong`, `legal_dieu`, `legal_khoan`) khi template có custom style IDs.

## Kiểm thử

- Unit tests cho parser, planner, style-map, grounding, builder utilities và review layer nằm trong `tests/test_docx_pipeline.py`.
- Khi chỉ cần rà artifact mới nhất mà không mở tay từng file JSON, dùng `scripts/latest_review_artifacts.py`.