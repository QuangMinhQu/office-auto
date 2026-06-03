---
name: md-to-docx-pipeline
description: Primitive DOCX toolchain — inspect raw, validate execution ops, apply ops, read result.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE

## Trình tự chạy
Scripts là tay, LLM là não.

1. `docx_inspect.py` — raw dump, zero heuristics
2. **[LLM REASONING]** — đọc dump + markdown, viết `execution_ops.json`
3. `docx_validate_ops.py` — warn-only validator
4. `execute_execution_ops.py` — mechanical executor
5. `docx_read_result.py` — readback để verify
6. `qa_docx.py` / `review_docx.py` — metrics và summary

## Artifacts
| File | Mô tả |
|---|---|
| `docx_inspect_output.json` | Combined output (all layers) |
| `docx_inspect_paragraph_sample.json` | 30 paragraphs đầu (quick reference) |
| `docx_inspect_all_para_ids.json` | TẤT CẢ paraIds (full document, dùng cho anchor) |
| `docx_inspect_styles_raw.json` | Paragraph styles + outline_level_xml |
| `docx_inspect_page_layout_raw.json` | Paper size, margins (twips) |
| `docx_inspect_toc_entries_raw.json` | TOC fields + bookmark anchors |
| `docx_inspect_front_matter_boundary.json` | Last paraId trước body content |
| `execution_ops.json` | LLM-generated ops |
| `execution_ops_validation.json` | Validator warnings |
| `execute_ops_report.json` | Execution summary |
| `result_readback.json` | Output DOCX readback |

## LLM Reasoning Chain

### Bước 1 — Page layout
Đọc `page_layout_raw` từ `docx_inspect_output.json`. Convert twips → mm: `1 twip = 1/1440 inch = 0.0176mm`.

### Bước 2 — Style inheritance tree
Đọc `styles_raw`. `space_before_pt: null` = inherited — để LLM interpret.

### Bước 3 — Classify document type
Đọc `paragraph_sample` + `toc_entries_raw` + `noidung.md`. Xác định academic/legal/etc.

### Bước 4 — Map markdown → Word styles
- `# heading` → `Heading 1` (outline_level_xml: 0)
- `## heading` → `Heading 2` (outline_level_xml: 1)
- `paragraph` → `Body Text` (first_line_indent: 36pt)

### Bước 5 — Viết execution_ops.json
Mỗi paragraph trong noidung.md → 1 op.

Anchor convention:
- Op đầu tiên: `/body/p[@paraId=XXXX]` từ `all_para_ids.json`
- Các op tiếp theo: `"PREVIOUS"` — executor tự động track last inserted path

Mỗi op phải có đầy đủ `run_props` và `para_props` explicit — không inherit.

```json
[
  {
    "op": "insert_paragraph_after",
    "anchor": "/body/p[@paraId=49349C0D]",
    "style": "Heading1",
    "text": "CHƯƠNG 1. CƠ SỞ LÝ THUYẾT",
    "run_props": { "font": "Times New Roman", "size_pt": 14, "bold": true },
    "para_props": { "space_before_pt": 12, "space_after_pt": 6, "line_spacing": 1.5 },
    "bookmark": "_Toc_ch1"
  },
  {
    "op": "insert_paragraph_after",
    "anchor": "PREVIOUS",
    "style": "BodyText",
    "text": "Nội dung chương 1...",
    "run_props": { "font": "Times New Roman", "size_pt": 13 },
    "para_props": { "first_line_indent_pt": 36, "line_spacing": 1.5 }
  }
]
```

### Supported ops
| Op | Params |
|---|---|
| `insert_paragraph_after` | `anchor`, `style`, `text`, `run_props`, `para_props`, `bookmark` |
| `insert_paragraph_before` | `anchor`, `style`, `text`, `run_props`, `para_props` |
| `remove` | `path` |
| `update_text` | `path`, `text`, `run_props` |
| `insert_table` | `anchor`, `rows`, `col_widths`, `style` |
| `set_page_layout` | `margins`, `paper_size`, `orientation` |

## Contract scripts

### `docx_inspect.py`
Raw dump ONLY. Không có field pre-classified (không heading_level, không is_body_text). LLM tự suy luận.

### `docx_validate_ops.py`
Warn-only. Validate anchor (against all_para_ids), style, op params. Không block execution.

### `execute_execution_ops.py`
Mechanical executor. Đọc execution_ops.json, apply từng op qua OfficeCLI. Raise error nếu op không hợp lệ.

### `docx_read_result.py`
Đọc output DOCX thành outline/text/field/toc summary để LLM tự verify.

## Quy tắc
- Mỗi script ghi artifact ngắn, schema ổn định.
- Mỗi script chạy lại được mà không hỏng run state.
- `execution_ops.json` là source of truth.
- Scripts heuristic cũ đã archive trong `scripts/legacy/`.
