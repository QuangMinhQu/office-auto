---
name: md-to-docx-pipeline
description: Primitive DOCX toolchain — inspect raw, validate execution ops, apply ops, read result.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE

## Trình tự chạy
Scripts là tay, LLM là não.

Các primitive này duoc expose qua MCP server `office-auto` (`mcp/office-auto-server.ts`). Moi phase la mot MCP tool rieng biet.

1. `docx_inspect.py` — raw dump, zero heuristics
2. **[LLM REASONING]** — đọc inspection output + markdown headings, viết `execution_ops.json`
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
| `docx_inspect_styles_for_llm.json` | Compact style summary for LLM reasoning |
| `docx_inspect_page_layout_raw.json` | Paper size, margins (twips) |
| `docx_inspect_toc_entries_raw.json` | TOC fields + bookmark anchors |
| `docx_inspect_front_matter_boundary.json` | Last paraId trước body content |
| `docx_inspect_content_map.json` | Front-matter/body anchor map |
| `execution_ops.json` | LLM-generated ops |
| `execution_ops_validation.json` | Validator warnings |
| `execute_ops_report.json` | Execution summary |
| `qa_report.json` | QA metrics after build |
| `review_report.json` / `review_report.md` / `review_screen.html` | Semantic review artifacts |
| `result_readback.json` | Output DOCX readback |

## Required Steps

1. `reviewOutput` — run review_docx.py and expose review artifacts (optional, post-build)

## LLM Reasoning Chain

### Bước 1 — Page layout
Đọc `page_layout_raw` từ `docx_inspect_output.json`. Convert twips → mm: `1 twip = 1/1440 inch = 0.0176mm`.

### Bước 2 — Style inheritance tree
Đọc `styles_raw`. `space_before_pt: null` = inherited — để LLM interpret.

### Bước 3 — Classify document type
Đọc `markdown_headings` từ source + `toc_entries_raw`. Xác định academic/legal/etc.
**KHÔNG đọc toàn bộ noidung.md** — chỉ cần heading structure để classify.

#### Verify heading levels (Issue #6 fix)
Trước khi map markdown → Word styles, kiểm tra:
- `# 1.4.` → Có thể là lỗi trong noidung.md. Nếu numbering depth = 2 (1.x) thì
  đây phải là `## 1.4.`, không phải `# 1.4.`
- Luôn ưu tiên số lượng `#` ký tự trong markdown, KHÔNG suy luận từ numbering prefix.
- Nếu số `#` và numbering depth mâu thuẫn, flag "heading_level_warning" và chọn
  theo `#` count (source of truth).

### Bước 4 — Map markdown → Word styles
- `# heading` → `Heading 1` (outline_level_xml: 0)
- `## heading` → `Heading 2` (outline_level_xml: 1)
- `paragraph` → `Body Text` (first_line_indent: 36pt)

### Bước 5 — Viết execution_ops.json
Mỗi paragraph trong noidung.md → 1 op.

Anchor convention:
- Op đầu tiên: `/body/p[@paraId=XXXX]` từ `all_para_ids.json`
- Các op tiếp theo: `"PREVIOUS"` — executor tự động track last inserted path

#### run_props Policy
- **KHÔNG bao giờ** set `run_props.font`, `run_props.size` cho heading ops → inherit từ style
- `run_props` chỉ dùng cho body text khi cần override (bold, italic inline)
- `para_props` chỉ set nếu template không có default hoặc cần thay đổi rõ ràng

#### Template Placeholder Rule
Sau khi viết tất cả insert ops, LUÔN thêm remove ops cho:
- Tất cả paragraphs trong `body_placeholders` (từ `content_map.json`)
- **NGOẠI TRỪ**: paragraphs có `is_front_matter: true` trong `all_para_ids`
- **NGOẠI TRỪ**: `CRITICAL_FIRST_OP_ANCHOR` paragraph (chính là điểm neo)
Remove ops phải được viết trong CÙNG `execution_ops.json` với insert ops,
không được tách thành 2 file riêng hay 2 lần chạy executor.

#### Preserved Structural Headings Rule (DATA-DRIVEN)

Khi viết remove ops cho `body_placeholders`, với MỖI paraId trong danh sách,
kiểm tra entry tương ứng trong `all_para_ids`:

```
IF all_para_ids[paraId].is_front_matter == true → SKIP, không remove
```

Quy tắc này là **data-driven** — không cần hardcode style name hay text pattern.
`is_front_matter` được `docx_inspect.py` gán dựa trên vị trí thực tế của paragraph
so với `front_matter_boundary` (XML fact, không phải heuristic).

**Validator enforcement**: `docx_validate_ops.py` đọc `is_front_matter` từ inspection
data và emit `code: "REMOVE_FRONT_MATTER"` warning nếu remove op nhắm vào front matter.
Orchestrator đọc warning này và quyết định retry.

Nếu `noidung.md` không có nội dung cho KẾT LUẬN hoặc TÀI LIỆU THAM KHẢO,
VẪN phải insert heading placeholder để navigation bar hiển thị đúng:
```json
{
  "op": "insert_paragraph_after",
  "anchor": "PREVIOUS",
  "style": "Heading1",
  "text": "KẾT LUẬN"
}
```

TOC entries (style `toc 1`) nằm trong front matter zone → `is_front_matter: true`
→ đã được bảo vệ tự động bởi rule trên. Chỉ remove body content placeholders,
giữ nguyên structural elements.

#### execution_ops Schema
Mỗi op phải có field `role` để executor/validator phân biệt heading vs body:
- `role: "h1" | "h2" | "h3"` cho headings
- `role: "body"` cho body text
- `role: "toc"` cho TOC entries

```json
{
  "version": "2",
  "ops": [
    {
      "op": "insert_paragraph_after",
      "role": "h1",
      "anchor": "/body/p[@paraId=49349C0D]",
      "style": "Heading1",
      "text": "CHƯƠNG 1. CƠ SỞ LÝ THUYẾT",
      "bookmark": "_Toc_ch1"
    },
    {
      "op": "insert_paragraph_after",
      "role": "body",
      "anchor": "PREVIOUS",
      "style": "BodyText",
      "text": "Nội dung chương 1...",
      "run_props": { "font": "Times New Roman", "size_pt": 13 },
      "para_props": { "first_line_indent_pt": 36, "line_spacing": 1.5 }
    },
    {
      "op": "remove",
      "path": "/body/p[@paraId=PLACEHOLDER_ID]"
    }
  ]
}
```

#### Remove Ops Completeness Self-Check
Trước khi finalize execution_ops.json, đếm:
- `body_placeholder_count` = số entries trong all_para_ids có `is_front_matter: false`
- `remove_op_count` = số ops có `"op": "remove"` trong file
- Nếu `remove_op_count < body_placeholder_count * 0.8` → PHẢI review lại,
  có khả năng đang thiếu remove ops.

#### TOC Refresh Protocol
Sau khi apply ops, TOC field cần được refresh. Có 3 chiến lược:
1. **LibreOffice headless** (preferred): `docx_refresh_fields.py --strategy libreoffice`
2. **mark_dirty** (fallback): `docx_refresh_fields.py --strategy mark_dirty` — đánh dấu fields dirty để Word tự refresh khi mở
3. **OfficeCLI refresh** (optional): nếu OfficeCLI hỗ trợ

### Supported ops
| Op | Params |
|---|---|
| `insert_paragraph_after` | `anchor`, `style`, `text`, `run_props`, `para_props`, `bookmark` |
| `insert_paragraph_before` | `anchor`, `style`, `text`, `run_props`, `para_props` |
| `remove` | `path` |
| `update_text` | `path`, `text`, `run_props` |
| `insert_table` | `anchor`, `rows`, `col_widths`, `style` |
| `set_page_layout` | `margins`, `paper_size`, `orientation` |
| `insert_image` | `anchor`, `image_path`, `width_cm`, `caption`, `caption_style` |

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

## Skeleton Pipeline Config

Khi template > 500 paragraphs, pipeline TỰ ĐỘNG bật skeleton mode.
LLM KHÔNG cần biết điều này — artifact structure giữ nguyên.

### Cách hoạt động
- `docx_inspect.py` nhận thêm `--skeleton-cache-dir` argument
- Nếu cache miss → `skeleton_builder.py` build skeleton (~10-20KB)
- Skeleton giữ: front matter, styles, header/footer, page layout, section properties
- Skeleton loại: body content placeholders (paragraphs/tables sau front matter)
- Hash-based cache: SHA-256 template file → tự động invalidation khi template thay đổi
- `--force-skeleton` flag để force rebuild

### Artifact mới
| File | Mô tả |
|---|---|
| `template_skeleton.docx` | Skeleton DOCX (~10-20KB) dùng cho inspection |
| `.office-auto/cache/skeletons/{hash}.meta.json` | Cache metadata |
| `.office-auto/cache/skeletons/{hash}.skeleton.docx` | Cached skeleton |

## Fallback Protocol: all_para_ids rỗng

**Trigger**: `recommended_insert_anchor` = null VÀ `all_para_ids` = []

**Mandatory behavior** (theo thứ tự):
1. Check `paragraph_sample` — dùng `IDX_{body_start_index:05d}` làm anchor đầu tiên
2. Sau op đầu tiên → `"anchor": "PREVIOUS"` cho mọi op tiếp theo  
3. **KHÔNG** speculate về cơ chế PREVIOUS khi chưa có anchor đầu tiên
4. **KHÔNG** gọi runPipeline khi chưa viết execution_ops.json
5. Nếu không resolve được anchor nào → abort với explicit error message

### IDX_ Synthetic paraIds
- Khi paragraph không có `w14:paraId`, script inject `IDX_XXXXX` format
- Validator KHÔNG warn HIGH severity cho synthetic IDs
- Executor resolve `IDX_XXXXX` → real paraId qua `body._element` iteration
- Nếu không resolve được → fallback PREVIOUS
