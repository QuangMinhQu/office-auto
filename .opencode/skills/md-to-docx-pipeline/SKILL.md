---
name: md-to-docx-pipeline
description: Primitive DOCX toolchain cho kiến trúc LLM-as-reasoning: inspect raw, validate execution ops, apply ops và read result.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE

## Mục tiêu
Skill này hướng agent dùng scripts như primitive mechanical tools, không dùng planner heuristic cũ trong flow mặc định.

Agent chỉ nên thấy:
- file path
- mode
- artifact path
- summary JSON ngắn

Không nên thấy:
- full `noidung.md`
- full XML trong `.docx`
- dump command output dài

## Khi nào dùng
- Task DOCX cần đúng kiến trúc mới trong `issue.md`.
- Cần raw inspection của template.
- Cần validate/apply `execution_ops.json`.
- Cần đọc output DOCX ra text/structure để verify.

## Artifacts chuẩn
- `.office-auto/state/<run_id>/preflight.json`
- `.office-auto/state/<run_id>/topology.json`
- `.office-auto/state/<run_id>/run.json`
- `.office-auto/state/<run_id>/template_inspection_raw.json`
- `.office-auto/state/<run_id>/execution_ops.json`
- `.office-auto/state/<run_id>/execution_ops_validation.json`
- `.office-auto/state/<run_id>/plan.json`
- `.office-auto/state/<run_id>/execution_plan.json`
- `.office-auto/state/<run_id>/build_report.json`
- `.office-auto/state/<run_id>/post_process_report.json`
- `.office-auto/state/<run_id>/result_readback.json`

## Trình tự chạy
1. `scripts/document_topology_detector.py` (optional observability)
2. `scripts/docx_inspect_raw.py`
3. LLM tự đọc markdown nguồn và tự viết `execution_ops.json`
4. `scripts/docx_validate_ops.py`
5. `scripts/compile_execution_ops.py`
6. `scripts/build_docx.py`
7. `scripts/post_process_docx.py`
8. `scripts/docx_read_result.py`

## Contract ngắn cho từng script

### `docx_inspect_raw.py`
- Input: `--template-file`, `--run-dir`
- Output: `template_inspection_raw.json`
- Trách nhiệm: dump raw OfficeCLI snapshots và body/style/TOC/field data đủ để LLM tự suy luận.

### `docx_validate_ops.py`
- Input: `--run-dir`, `--ops-file`
- Output: `execution_ops_validation.json`
- Trách nhiệm: cảnh báo anchor/style/prototype_path/remove-path không khớp template inspection raw; không block execution.

### `compile_execution_ops.py`
- Input: `--run-dir`, `--ops-file`, `--template-file`, `--target-file`, `--source-file?`
- Output: `execution_ops.json`, `plan.json`, `execution_plan.json`
- Trách nhiệm: compile `execution_ops.json` do LLM/agent soạn sẵn thành execution graph cơ học; không làm style/range inference heuristic.

### `build_docx.py`
- Input: `--run-dir`
- Output: `build_report.json`
- Trách nhiệm: chỉ chạy bounded replacement; nếu range chưa resolve thì fail-closed.
- Script build mặc định đi theo resident mode OfficeCLI: `open -> remove/add/set -> save -> close`, và dùng batch nội bộ cho các chunk remove/add deterministic.
- Nếu template có TOC hoặc field dẫn hướng phụ thuộc heading, script phải giữ field đó và chọn refresh strategy native, ví dụ rewrite TOC field qua L2. Chỉ dùng L3 khi L2 không đủ và phải ghi rõ vào `build_report.json`.
- Error contract: khi `plan.json.status=blocked`, script phải ghi `build_report.json.status=blocked`, không tạo output giả hoàn tất và phải giữ `run.json.status=blocked`.

### `docx_read_result.py`
- Input: `--run-dir`, `--file?`
- Output: `result_readback.json`
- Trách nhiệm: đọc output DOCX thành outline/text/field/toc summary để LLM tự verify.

## Quy tắc
- Mỗi script phải ghi artifact ngắn, có schema ổn định.
- Mỗi script phải có thể chạy lại mà không làm hỏng run state.
- `execution_ops.json` là source of truth cho planning path mới.
- Các scripts heuristic cũ (`profile_template.py`, `plan_mapping.py`, `compile_execution_plan.py`, wrapper default cũ) chỉ còn phục vụ legacy/debug, không phải mặc định vận hành.