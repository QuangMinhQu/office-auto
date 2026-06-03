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

## Trình tự chạy (new philosophy: scripts = hands, LLM = brain)
1. `scripts/docx_inspect.py` — primitive tool: raw dump only, zero heuristics
    → outputs: `docx_inspect_output.json` + layer files
2. **[LLM REASONING]** — LLM reads raw dump + markdown, tự suy luận và viết execution_ops.json
3. `scripts/docx_validate_ops.py` — warn-only validator (không block execution)
4. `scripts/execute_execution_ops.py` — primitive tool: mechanical executor
    → reads execution_ops.json, applies ops to DOCX via OfficeCLI
5. `scripts/docx_read_result.py` — read back result để verify
6. `scripts/qa_docx.py` — metrics collection only (no reasoning)
7. `scripts/review_docx.py` — summary report

## LLM Reasoning Chain (bắt buộc thực hiện đúng)

Khi đến bước 2 [LLM REASONING], LLM phải thực hiện chain sau:

### Bước 1 — Đọc page layout
- Đọc `page_layout_raw` từ `docx_inspect_output.json`
- Convert twips → mm: `1 twip = 1/1440 inch = 0.0176mm`
- Ví dụ: `margin_left: 1800 twips → 1800/1440 = 1.25 inch → ~31.75mm`
- Classify: "margin hẹp phía trái, likely báo cáo học thuật VN (30mm standard)"

### Bước 2 — Build style inheritance tree
- Đọc `styles_raw` từ `docx_inspect_output.json`
- `space_before_pt: null` = **inherited** — không resolve, để LLM interpret
- Ví dụ: "Heading 1 → base: Normal, space_before_pt: null → inherited from Normal"
- "Normal có space_before_pt: 0 → Effective space_before Heading 1 = 0pt"

### Bước 3 — Classify document type
- Đọc `paragraph_sample` + `toc_entries_raw` + `noidung.md`
- "markdown có # Chương, không có ĐIỀU/KHOẢN → academic/technical, không phải legal"
- "first_line_indent_pt: 36pt ở Body Text → thụt đầu dòng kiểu VN"

### Bước 4 — Map markdown → Word styles
- `# heading` → `Heading 1` (outline_level_xml: 0, font: TNR 14pt bold)
- `## heading` → `Heading 2` (outline_level_xml: 1, ...)
- `paragraph` → `Body Text` (first_line_indent: 36pt)
- `bullet` → `List Bullet` (nếu tồn tại trong styles_raw, không có → dùng Body Text + manual indent)

### Bước 5 — Viết execution_ops.json
- Mỗi paragraph trong noidung.md → 1 op với đầy đủ explicit properties
- **Rule quan trọng**: LLM phải set `run_props` và `para_props` **explicit** cho mỗi op
- KHÔNG để inherit bất kỳ property nào không được set explicitly
- Dùng `anchor` là paraId từ `paragraph_sample` hoặc "PREVIOUS" cho paragraph sau cùng
- Format output: JSON array của các op objects

### Supported ops trong execution_ops.json

| Op | Params | Mô tả |
|---|---|---|
| `insert_paragraph_after` | `anchor`, `style`, `text`, `run_props`, `para_props`, `bookmark` | Insert paragraph sau anchor |
| `insert_paragraph_before` | `anchor`, `style`, `text`, `run_props`, `para_props` | Insert paragraph trước anchor |
| `remove` | `path` | Xóa element tại path |
| `update_text` | `path`, `text`, `run_props` | Update text của paragraph |
| `insert_table` | `anchor`, `rows`, `col_widths`, `style` | Insert table |
| `set_page_layout` | `margins`, `paper_size`, `orientation` | Set page-level properties |

### Ví dụ execution_ops.json

```json
[
  {
    "op": "insert_paragraph_after",
    "anchor": "/body/p[@paraId='49349C0D']",
    "style": "Heading1",
    "text": "CHƯƠNG 1. CƠ SỞ LÝ THUYẾT",
    "run_props": {
      "font": "Times New Roman",
      "size_pt": 14,
      "bold": true
    },
    "para_props": {
      "space_before_pt": 12,
      "space_after_pt": 6,
      "line_spacing": 1.5,
      "line_spacing_rule": "MULTIPLE"
    },
    "bookmark": "_Toc_ch1"
  },
  {
    "op": "insert_paragraph_after",
    "anchor": "PREVIOUS",
    "style": "BodyText",
    "text": "Nội dung chương 1...",
    "run_props": {
      "font": "Times New Roman",
      "size_pt": 13,
      "bold": false
    },
    "para_props": {
      "first_line_indent_pt": 36,
      "line_spacing": 1.5
    }
  }
]
```

Old scripts (`profile_template.py`, `plan_mapping.py`, `compile_execution_plan.py`,
`prepare_template_scaffold.py`, `patch_template_profile()`) are **archived** in
`scripts/legacy/`. They are Python doing LLM's work — this was the core issue
identified in `issue.md`.

## Contract ngắn cho từng script (new pipeline)

### `docx_inspect.py`
- Input: `--template-file`, `--run-dir`
- Output: `docx_inspect_output.json`
- Trách nhiệm: raw dump ONLY — zero heuristics, zero interpretation.
  + `page_layout_raw`: paper size, margins (twips), orientation
  + `styles_raw`: paragraph styles với `outline_level_xml` (raw w:outlineLvl @w:val, 0-9)
  + `paragraph_sample`: 30 paragraphs đầu tiên với para_id
  + `toc_entries_raw`: TOC fields với bookmark anchors
  + `front_matter_boundary`: last paraId before body content
  + **Không có field** pre-classified: không heading_level, không is_body_text

### `docx_validate_ops.py`
- Input: `--run-dir`, `--ops-file`
- Output: `execution_ops_validation.json`
- Trách nhiệm: warn-only validator — không block execution.
  + Validate anchor tồn tại trong paragraph_sample
  + Validate style tồn tại trong styles_raw
  + Validate op params hợp lệ
  + Output: `{"status": "ok"|"warnings", "warning_count": N, "warnings": [...]}`

### `execute_execution_ops.py`
- Input: `--run-dir`
- Output: `execute_ops_report.json`
- Trách nhiệm: mechanical executor — zero decision logic.
  + Đọc execution_ops.json, apply từng op lên DOCX qua OfficeCLI
  + Supported ops: insert_paragraph_after, insert_paragraph_before, remove,
    update_text, insert_table/insert_table_after, set_page_layout
  + Nếu op không hợp lệ → raise error với message rõ ràng

### `docx_read_result.py`
- Input: `--run-dir`, `--file?`
- Output: `result_readback.json`
- Trách nhiệm: đọc output DOCX thành outline/text/field/toc summary để LLM tự verify.

## Quy tắc
- Mỗi script phải ghi artifact ngắn, có schema ổn định.
- Mỗi script phải có thể chạy lại mà không làm hỏng run state.
- `execution_ops.json` là source of truth cho planning path mới.
- Các scripts heuristic cũ (`profile_template.py`, `plan_mapping.py`, `compile_execution_plan.py`, wrapper default cũ) chỉ còn phục vụ legacy/debug, không phải mặc định vận hành.