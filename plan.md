Dưới đây là plan hoàn chỉnh dựa trên toàn bộ context đã phân tích.

***

## Section 1: Fixes cần thực hiện ngay (blocking)

Những lỗi này đang khiến pipeline **không chạy đúng trong mọi task**, phải fix trước khi làm gì khác.

### Fix 1 — Script name mismatch trong `docx_pipeline.ts`

`inspectTemplate` gọi `docx_inspect_raw.py`, file thực tế là `docx_inspect.py`. Sửa trong `docx_pipeline.ts`:
```typescript
// TRƯỚC (sai)
["docx_inspect_raw.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]

// SAU (đúng)
["docx_inspect.py", ["--template-file", absTplFile, "--run-dir", absRunDir]]
```
Đồng thời kiểm tra toàn bộ các tool khác (`applyExecutionOps`, `runPipeline`) — tất cả step names phải khớp với file thực tế trong `scripts/`.

### Fix 2 — `run_dir` phải được generate tự động trong MCP tool

LLM đang pass `$(date +%Y%m%d_%H%M%S)_report` như string literal. Sửa logic trong `inspectTemplate.execute()`:

```typescript
async execute(args, context) {
  let absRunDir: string
  if (!args.run_dir || args.run_dir.includes("$(")) {
    // auto-generate nếu LLM pass shell expression hoặc bỏ trống
    const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)
    absRunDir = `${context.worktree}/.office-auto/state/${ts}_auto`
  } else {
    absRunDir = resolveWorkspacePath(context.worktree, args.run_dir)
  }
  // ... rest of execute
}
```

Hoặc tốt hơn: làm `run_dir` optional, luôn auto-generate, trả về `run_dir` thực tế trong output để LLM biết dùng cho bước tiếp theo.

### Fix 3 — Description của `applyExecutionOps` phải nói rõ convention `execution_ops.json`

Thêm vào description:
```
PRECONDITIONS:
- File execution_ops.json MUST be placed at {run_dir}/execution_ops.json BEFORE calling this tool.
  Do NOT pass --ops-file as a CLI argument — the script reads from run_dir by convention.
- run_dir must be the SAME literal path returned by inspectTemplate (not a new path).
```

### Fix 4 — `docx_inspect.py` phải export `effective_font` và `is_front_matter`

Thêm hai fields vào mỗi entry trong `all_para_ids.json`:
```python
# Trong docx_inspect.py, khi build all_para_ids entry:
{
  "index": 42,
  "para_id": "04C2E2D0",
  "style_name": "Heading 1",
  "text_preview": "GIỚI THIỆU",
  "is_front_matter": False,   # NEW: dựa trên front_matter_boundary
  "effective_font": "Times New Roman"  # NEW: resolve từ style → theme
}
```

Resolve font:
```python
def resolve_effective_font(para, styles_map, theme_fonts):
    # 1. Check run-level rPr
    # 2. Fallback to style definition
    # 3. Fallback to theme majorFont/minorFont
    # 4. Fallback to "Times New Roman"
    ...
```

Với field `is_front_matter`, LLM đọc `all_para_ids.json` sẽ tự biết không viết `remove` ops cho những paraId có `is_front_matter: true` — không cần hardcoded logic trong executor.

***

## Section 2: Plan cải tiến (roadmap)

### Tier A — Cải tiến validator (giá trị cao, effort thấp)

**A1. Style name validation trong `docx_validate_ops.py`**

Hiện tại validator không check `op.style` có tồn tại trong template không. Thêm:
```python
known_styles = {s["style_id"] for s in template_inspection.get("styles_raw", [])}
known_styles |= {s["name"] for s in template_inspection.get("styles_raw", [])}

if op.get("style") and op["style"] not in known_styles:
    warnings.append({
        "op": i,
        "severity": "high",
        "message": f"Style '{op['style']}' not found in template. Available: {sorted(known_styles)}"
    })
```

**A2. `run_props` override warning**

Bất kỳ op nào có `run_props.font` hoặc `run_props.size` phải trigger warning medium:
```
"run_props.font='.VnTime' overrides style inheritance. 
 Template effective_font for style 'Normal_style' is 'Times New Roman'.
 Consider removing run_props.font to inherit from style."
```

Đây là warning, không phải error — LLM vẫn có thể giữ nguyên nếu có lý do.

**A3. Front-matter protection trong validator**

Thêm check: bất kỳ `remove` op nào target paraId có `is_front_matter: true` → error high severity, không chỉ warn:
```
"Remove op targets front-matter paragraph 04C2E2D0 ('GIỚI THIỆU', Heading 1).
 Front-matter paragraphs must not be removed. Use update_text instead if needed."
```

***

### Tier B — Cải tiến `docx_inspect.py` output (giá trị cao, effort trung bình)

**B1. Styles summary cho LLM**

Thêm file `docx_inspect_styles_for_llm.json` — một bản rút gọn có chủ đích để LLM đọc, không phải raw XML dump:
```json
{
  "body_text_style": "Normal_style",
  "heading_map": {
    "chapter_title": "Heading 1",
    "section": "Heading 2", 
    "subsection": "Heading 3"
  },
  "available_styles": [
    {
      "name": "Normal_style",
      "use_for": "body paragraphs",
      "effective_font": "Times New Roman",
      "font_size_pt": 14,
      "line_spacing": 1.5,
      "first_line_indent_pt": 28.35
    },
    ...
  ],
  "do_not_use_styles": ["Normal", "Default Paragraph Font"]
}
```

LLM đọc file này → không cần parse `styles_raw.json` (complex, noisy) → quyết định style đúng ngay lần đầu.

**B2. Content section map**

Thêm file `docx_inspect_content_map.json`:
```json
{
  "front_matter": {
    "para_ids": ["5E9CB3ED", ..., "49349C0D"],
    "last_para_id": "49349C0D",
    "description": "Title page, TOC, figure list — DO NOT REMOVE"
  },
  "body_placeholders": {
    "para_ids": ["04C2E2D0", "47DD4FDA", ..., "3F0FE4AF"],
    "description": "Placeholder content — SHOULD BE REMOVED before inserting new content"
  },
  "recommended_insert_anchor": "49349C0D"
}
```

Đây là output cực kỳ có giá trị: LLM đọc một file → biết ngay anchor để insert, biết ngay paraIds cần remove. Không cần suy luận từ all_para_ids dài 57 entries.

***

### Tier C — MCP tool architecture (giá trị cao, effort cao)

**C1. Tool `prepareInsertPlan` — LLM-facing reasoning scaffold**

Thêm một MCP tool mới nằm giữa `inspectTemplate` và `applyExecutionOps`:

```typescript
export const prepareInsertPlan = tool({
  title: "Prepare Insert Plan from Markdown",
  description: `Reads inspection output and noidung.md, returns a structured 
  insert plan scaffold for LLM to fill in. Does NOT generate ops automatically — 
  returns the scaffold with style recommendations and anchor points so LLM can 
  make final decisions on content mapping.`,
  args: {
    run_dir: ...,
    content_file: tool.schema.string().describe("Path to markdown content file")
  },
  async execute(args, context) {
    // Đọc docx_inspect_styles_for_llm.json
    // Đọc docx_inspect_content_map.json  
    // Parse markdown headings structure
    // Trả về scaffold: { recommended_anchor, styles_to_use, heading_count, ... }
    // LLM nhận scaffold → điền text → submit execution_ops
  }
})
```

Triết lý: tool này **không quyết định** style hay content — chỉ aggregate thông tin từ nhiều inspect files thành một package compact để LLM reasoning. Giảm context window LLM phải xử lý từ ~5 JSON files xuống còn 1.

**C2. Tool `validateAndSuggest` thay vì `validateExecutionOps`**

Validator hiện tại chỉ warn/error. Nâng cấp: khi có lỗi, tool trả về **suggested fix**:
```json
{
  "op_index": 16,
  "severity": "high",
  "message": "Style 'Normal' not recommended for body text",
  "suggested_fix": {
    "style": "Normal_style",
    "remove_run_props": ["font", "size"]
  }
}
```

LLM nhận output này → tự patch `execution_ops.json` → validate lại. Vòng lặp tự sửa không cần user intervention.

***

### Tier D — QA và feedback loop (giá trị rất cao, effort cao — có thể vi phạm triết lý một phần)

**D1. `qa_docx.py` phải được integrate vào pipeline như bắt buộc**

Script `qa_docx.py` đã tồn tại nhưng không được gọi trong bất kỳ MCP tool nào . Đây là lãng phí lớn nhất. Thêm bước QA bắt buộc sau `applyExecutionOps`:

```typescript
// Trong applyExecutionOps hoặc runPipeline:
const steps = [
  ["execute_execution_ops.py", [...]],
  ["qa_docx.py", ["--output-file", targetFile, "--run-dir", absRunDir]],  // BẮT BUỘC
]
```

`qa_docx.py` đọc `report.docx` thực tế sau khi build → kiểm tra font, heading levels, line spacing → trả về pass/fail với chi tiết. Đây là feedback thực sự (ground truth từ DOCX) thay vì validation trên JSON ops.

**D2. `review_docx.py` expose qua MCP tool**

`review_docx.py` cũng đang bị bỏ quên . Tạo tool `reviewOutput`:
```typescript
export const reviewOutput = tool({
  title: "Review Generated DOCX",
  description: `Runs semantic review of the generated DOCX against the original 
  content source. Returns: missing_sections, style_violations, format_score (0-100).
  Call after applyExecutionOps to verify output quality before delivering to user.`,
  ...
})
```

Đây là tool cho phép LLM tự đánh giá output của chính nó — closing the reasoning loop. Có thể vi phạm triết lý "LLM không cần tool để đánh giá" nhưng ground truth từ OOXML parsing vẫn quan trọng hơn LLM tự review trên text.

***

### Tier E — Long-term: Template learning (giá trị cao, effort rất cao)

**E1. `template-cache` tận dụng đúng cách**

Thư mục `.office-auto/state/template-cache/` đã tồn tại nhưng không có gì trong đó. Ý tưởng: sau khi `inspectTemplate` chạy lần đầu trên một template, cache toàn bộ `styles_for_llm.json` + `content_map.json` theo hash của template file. Lần sau gọi cùng template → skip inspect, load từ cache → tiết kiệm ~3-5 giây và giảm context noise.

**E2. Per-template SKILL fragment**

Sau lần đầu build thành công với một template, generate file `.opencode/skills/md-to-docx-pipeline/templates/{template_hash}.md` chứa:
```markdown
# Template: format_template.docx
- body_text_style: Normal_style
- recommended_anchor: 49349C0D  
- front_matter_last_para: 49349C0D
- effective_font: Times New Roman
- lessons_learned: Avoid run_props.font override; use Normal_style not Normal
```

LLM đọc fragment này ở đầu task → không cần re-inspect, không cần re-discover conventions. Đây là **institutional memory** cho pipeline — mỗi lần chạy thành công dạy LLM thêm về template đó.