---
name: md-to-docx-pipeline
description: Pipeline xử lý Markdown và DOCX bằng script và artifact ngoài context. Dùng khi cần parse Markdown, profile template, lập plan, build và QA qua file path cộng JSON thay vì đọc toàn bộ nội dung vào prompt.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE

## Mục tiêu
Skill này hướng agent chạy pipeline deterministic ngoài context.

Agent chỉ nên thấy:
- file path
- mode
- artifact path
- summary JSON ngắn

Không nên thấy:
- full `chuong_2.md`
- full XML trong `.docx`
- dump command output dài

## Khi nào dùng
- Task có `preserve-template-scaffold` hoặc mode cũ cần normalize sang mode này.
- Cần parse Markdown thành AST và outline.
- Cần profile template để lấy style, numbering, page setup, field và scaffold.
- Cần checkpoint state để resume.

## Artifacts chuẩn
- `.office-auto/state/<run_id>/run.json`
- `.office-auto/state/<run_id>/content_ast.json`
- `.office-auto/state/<run_id>/content_outline.json`
- `.office-auto/state/<run_id>/template_profile.json`
- `.office-auto/state/<run_id>/plan.json`
- `.office-auto/state/<run_id>/build_report.json`
- `.office-auto/state/<run_id>/qa_report.json`

## Trình tự chạy
1. `scripts/parse_markdown.py`
2. `scripts/profile_template.py`
3. `scripts/plan_mapping.py`
4. `scripts/build_docx.py`
5. `scripts/qa_docx.py`

## Contract ngắn cho từng script

### `parse_markdown.py`
- Input: `--source-file`, `--run-dir`
- Output: `content_ast.json`, `content_outline.json`

### `profile_template.py`
- Input: `--template-file`, `--run-dir`
- Output: `template_profile.json`
- Trách nhiệm: phát hiện scaffold, field TOC/danh mục, section count, heading candidate và replace-range candidate.

### `plan_mapping.py`
- Input: `--mode`, `--run-dir`, `--source-file`, `--template-file`, `--target-file`
- Output: `plan.json`, cập nhật `run.json`
- Trách nhiệm: normalize mode cũ, sinh `preserve`, `replace_ranges`, `post_conditions`, `execution_strategy`.

### `build_docx.py`
- Input: `--run-dir`
- Output: `build_report.json`
- Trách nhiệm: chỉ chạy bounded replacement; nếu range chưa resolve thì fail-closed.

### `qa_docx.py`
- Input: `--run-dir`
- Output: `qa_report.json`
- Trách nhiệm: kiểm package QA, structural QA, range QA và semantic QA.

## Quy tắc
- Mỗi script phải ghi artifact ngắn, có schema ổn định.
- Mỗi script phải có thể chạy lại mà không làm hỏng run state.
- Không được dùng `scaffolded`, `pending-implementation` hoặc trạng thái mơ hồ để ngụy trang thành công khi đường build thật chưa đạt chuẩn.
- Nếu chưa resolve được range thay nội dung hoặc chưa chứng minh được scaffold preservation, script phải fail rõ ràng.