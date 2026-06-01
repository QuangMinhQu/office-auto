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
- `.office-auto/state/<run_id>/preflight.json`
- `.office-auto/state/<run_id>/run.json`
- `.office-auto/state/<run_id>/template_preparation_report.json`
- `.office-auto/state/<run_id>/effective_template.docx`
- `.office-auto/state/<run_id>/normalized.md`
- `.office-auto/state/<run_id>/input_report.json`
- `.office-auto/state/<run_id>/markitdown_style_map.txt`
- `.office-auto/state/<run_id>/sample_content.md`
- `.office-auto/state/<run_id>/sample_outline.json`
- `.office-auto/state/<run_id>/sample_content_report.json`
- `.office-auto/state/<run_id>/content_ast.json`
- `.office-auto/state/<run_id>/content_outline.json`
- `.office-auto/state/<run_id>/template_profile.json`
- `.office-auto/state/<run_id>/plan.json`
- `.office-auto/state/<run_id>/execution_plan.json`
- `.office-auto/state/<run_id>/build_report.json`
- `.office-auto/state/<run_id>/review_report.json`
- `.office-auto/state/<run_id>/review_report.md`
- `.office-auto/state/<run_id>/review_screen.html`
- `.office-auto/state/<run_id>/roundtrip.md`
- `.office-auto/state/<run_id>/roundtrip_report.json`
- `.office-auto/state/<run_id>/qa_report.json`
- `.office-auto/state/<run_id>/pipeline_report.json` khi chạy qua wrapper `scripts/build_report.py`

## Trình tự chạy
1. `scripts/profile_template.py`
2. `scripts/prepare_template_scaffold.py` khi template lịch sử quá dày
3. `scripts/profile_template.py` lại nếu wrapper đã sinh `effective_template.docx`
4. `scripts/generate_markitdown_style_map.py`
5. `scripts/input_processor.py`
6. `scripts/extract_sample_content.py`
7. `scripts/parse_markdown.py`
8. `scripts/plan_mapping.py`
9. `scripts/compile_execution_plan.py`
10. `scripts/build_docx.py`
11. `scripts/roundtrip_markitdown.py`
12. `scripts/qa_docx.py`
13. `scripts/review_docx.py`

## Contract ngắn cho từng script

### `parse_markdown.py`
- Input: `--source-file`, `--run-dir`
- Output: `content_ast.json`, `content_outline.json`

### `profile_template.py`
- Input: `--template-file`, `--run-dir`
- Output: `template_profile.json`
- Trách nhiệm: phát hiện scaffold, field TOC/danh mục, section count, heading candidate và replace-range candidate qua OfficeCLI `view/get/query`.

### `prepare_template_scaffold.py`
- Input: `--template-file`, `--run-dir`
- Output: `template_preparation_report.json`, có thể sinh `effective_template.docx`
- Trách nhiệm: giảm template lịch sử về scaffold mỏng hơn, giữ preserve zones và cache theo content hash.

### `generate_markitdown_style_map.py`
- Input: `--run-dir`
- Output: `markitdown_style_map.txt`
- Trách nhiệm: map Word styles sang semantic Markdown để dùng nhất quán cho input normalization, sample extraction và roundtrip QA.

### `input_processor.py`
- Input: `--source-file`, `--run-dir`, `--style-map-file`
- Output: `normalized.md`
- Trách nhiệm: normalize đầu vào `.md/.docx/...` thành Markdown thống nhất trước khi parse.

### `extract_sample_content.py`
- Input: `--sample-file`, `--run-dir`, `--style-map-file`
- Output: `sample_content.md`, `sample_outline.json`
- Trách nhiệm: trích semantic scaffold từ template/sample DOCX để planner có thể trim front matter đã được scaffold cover sẵn.

### `parse_markdown.py`
- Input: `--source-file`, `--run-dir`
- Output: `content_ast.json`, `content_outline.json`

### `plan_mapping.py`
- Input: `--mode`, `--run-dir`, `--source-file`, `--template-file`, `--target-file`
- Output: `plan.json`, cập nhật `run.json`
- Trách nhiệm: normalize mode cũ, sinh `preserve`, `replace_ranges`, `post_conditions`, `execution_strategy`, và `semantic_grounding.source_render_window`.
- Error contract: nếu `replace_ranges` chưa `resolved` trong mode `preserve-template-scaffold` thì `plan.json.status` phải là `blocked` và downstream không được build tiếp như thể thành công.

### `compile_execution_plan.py`
- Input: `--run-dir`
- Output: `execution_plan.json`
- Trách nhiệm: compile `plan.json` và `content_ast.json` thành render ops deterministic, có reuse prototype format defaults nhưng không kéo sai cover formatting sang body.

### `build_docx.py`
- Input: `--run-dir`
- Output: `build_report.json`
- Trách nhiệm: chỉ chạy bounded replacement; nếu range chưa resolve thì fail-closed.
- Script build mặc định đi theo resident mode OfficeCLI: `open -> remove/add/set -> save -> close`, và dùng batch nội bộ cho các chunk remove/add deterministic.
- Nếu template có TOC hoặc field dẫn hướng phụ thuộc heading, script phải giữ field đó và chọn refresh strategy native, ví dụ rewrite TOC field qua L2. Chỉ dùng L3 khi L2 không đủ và phải ghi rõ vào `build_report.json`.
- Error contract: khi `plan.json.status=blocked`, script phải ghi `build_report.json.status=blocked`, không tạo output giả hoàn tất và phải giữ `run.json.status=blocked`.

### `review_docx.py`
- Input: `--run-dir`
- Output: `review_report.json`, `review_report.md`, `review_screen.html`
- Trách nhiệm: tạo lớp screen review sau QA, so output với template baseline phù hợp và highlight các paragraph mới có drift về style, align, cỡ chữ, font hoặc spacing.

### `roundtrip_markitdown.py`
- Input: `--run-dir`, `--style-map-file`
- Output: `roundtrip.md`, `roundtrip_report.json`
- Trách nhiệm: convert output DOCX ngược về Markdown, trim cùng semantic window của template scaffold, rồi so semantic heading/table/body text.

### `qa_docx.py`
- Input: `--run-dir`
- Output: `qa_report.json`
- Trách nhiệm: kiểm package QA, structural QA, range QA và semantic QA.
- Threshold tối thiểu: `header_count_output >= header_count_template`, `footer_count_output >= footer_count_template`, và nếu template có TOC hoặc danh mục hình/bảng thì field tương ứng phải còn trong file đích.
- Nếu TOC đang dựa vào refresh-on-open, QA phải đọc refresh strategy từ `build_report.json`; nếu TOC đã render sẵn trong package thì hyperlink/anchor của các entry phải còn hợp lệ.

### `scripts/build_report.py`
- Input: `--run-dir`, `--source-file`, `--template-file`, `--target-file`, `--sample-file?`
- Output: `pipeline_report.json`
- Trách nhiệm: wrapper điều phối full flow, tự chọn `effective_template.docx` làm sample mặc định, retry hẹp cho `build_docx.py` khi OfficeCLI batch bị flaky lần đầu, và sinh review artifacts sau khi QA đã hoàn tất.

## Quy tắc
- Mỗi script phải ghi artifact ngắn, có schema ổn định.
- Mỗi script phải có thể chạy lại mà không làm hỏng run state.
- Mọi script OfficeCLI native phải dùng `officecli --version` hoặc `preflight.json` làm source-of-truth cho runtime hiện tại.
- Không được dùng `scaffolded`, `pending-implementation` hoặc trạng thái mơ hồ để ngụy trang thành công khi đường build thật chưa đạt chuẩn.
- Nếu chưa resolve được range thay nội dung hoặc chưa chứng minh được scaffold preservation, script phải fail rõ ràng.