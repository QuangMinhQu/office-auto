Tôi đã đọc đủ toàn bộ kiến trúc hiện tại. Đây là phân tích architectural và đề xuất rebuild.

***

## Vấn Đề Cốt Lõi Của Kiến Trúc Hiện Tại

Kiến trúc hiện tại đang dùng LLM như một **orchestrator dumb** — nó chỉ biết "gọi tool A, đọc JSON, gọi tool B". Toàn bộ intelligence nằm trong Python scripts (`profile_template.py`, `plan_mapping.py`, `compile_execution_plan.py`...). LLM không tham gia vào bất kỳ quyết định nào về format, style, hay mapping. Đây là **inverted design**: scripts làm việc của LLM, LLM làm việc của scripts.

```
Hiện tại:
User → Orchestrator (LLM) → Tool A → Python heuristics → JSON → Tool B → Python → DOCX
                                           ↑ Intelligence nằm đây, KHÔNG phải ở LLM
```

***

## Kiến Trúc Mới: LLM-as-Reasoning-Engine

Nguyên tắc cốt lõi: **Chỉ những gì không thể suy luận mới trở thành tool. Những gì suy luận được thì LLM làm.**

```
Mới:
User → Orchestrator (LLM) ─── đọc template XML/stats → LLM tự suy luận style map
                           ─── đọc markdown content → LLM tự classify format
                           ─── tự viết execution_plan.json
                           → Executor tool (thuần mechanical) → DOCX
```

### Tầng Tool Tối Giản (Chỉ 4 Primitive Tools)

Thay vì 8+ scripts phức tạp với heuristics, chỉ cần:

```
1. docx_inspect(file)         → trả về raw XML/stats của template (read-only)
2. docx_apply_ops(ops[])      → nhận list operations, execute mechanical
3. docx_read_result(file)     → đọc DOCX ra text/structure để verify
4. file_read/write            → I/O thông thường
```

Không có bất kỳ heuristic nào trong tools. Tool `docx_apply_ops` nhận một list operations dạng:
```json
[
  {"op": "insert_paragraph_after", "anchor": "/body/p[@paraId=49349C0D]",
   "style": "Heading1", "text": "CƠ SỞ LÝ THUYẾT",
   "run_props": {"font": "Times New Roman", "size": "14pt", "bold": true}},
  {"op": "remove", "path": "/body/p[@paraId=04C2E2D0]"},
  {"op": "insert_table", "anchor": "...", "rows": [...]}
]
```

### LLM Làm Toàn Bộ Reasoning

Với `docx_inspect(template)`, LLM nhận về stats như:
```json
{
  "styles": [{"id": "Heading1", "font": "Times New Roman", "size": "14pt", "bold": true}, ...],
  "paragraphs_sample": [...20 paragraphs đầu...],
  "toc_entries": [...],
  "front_matter_zone": {"end_paraId": "49349C0D"}
}
```

LLM đọc markdown, đọc template stats, **tự suy luận**:
- "Heading level 1 trong markdown → style `Heading1`, Times New Roman 14pt bold, vì template dùng style này cho tiêu đề chương"
- "Đây không phải văn bản pháp lý vì không có cấu trúc ĐIỀU/KHOẢN → không cần legal mapping"
- "TOC cần bookmark `_Toc229985277` cho heading `CƠ SỞ LÝ THUYẾT` vì template TOC reference anchor đó"

Sau đó LLM **tự viết** `execution_ops.json` hoàn chỉnh và truyền cho `docx_apply_ops`.

***

## So Sánh Hai Kiến Trúc

| Tiêu chí | Kiến trúc hiện tại | Kiến trúc mới |
|---|---|---|
| Nơi chứa intelligence | Python heuristics | LLM reasoning |
| Số files Python core | ~15 scripts phức tạp | 4 primitive tools |
| Xử lý edge case | Thêm if/else vào scripts | LLM thấy → tự adapt |
| Legal/academic detection | Regex hardcode | LLM đọc content → suy luận |
| Font size inject | Bug phức tạp cần patch | LLM explicit set từ đầu |
| TOC bookmark matching | Broken vì mapping logic sai | LLM cross-reference trực tiếp |
| Maintainability | Mỗi case mới = thêm code | Mỗi case mới = thêm ví dụ vào prompt |

***

## Kế Hoạch Rebuild Cụ Thể

### Phase 1 — Slim Down Tools (~3 ngày)

Giữ lại từ codebase hiện tại:
- `officecli_native.py` — wrapper gọi OfficeCLI binary (mechanical, giữ nguyên)
- Primitive `docx_inspect` — extract XML stats (flatten `profile_template.py` xuống còn dump raw data, **bỏ toàn bộ heuristic classification**)
- Primitive `docx_apply_ops` — mechanical executor (từ `build_docx.py` nhưng **bỏ toàn bộ logic quyết định**, chỉ execute)

Xóa hoặc merge thành dead code:
- `parse_markdown.py` → LLM đọc markdown trực tiếp
- `plan_mapping.py` → LLM tự map
- `compile_execution_plan.py` → LLM tự compile
- `generate_pandoc_style_map.py` → LLM tự generate
- `profile_template.py` (phần heuristics) → chỉ giữ raw dump

### Phase 2 — LLM Reasoning Prompt (~2 ngày)

Viết `orchestrator.md` mới với explicit reasoning chain:

```markdown
## Bước 1: Inspect Template
Dùng docx_inspect(template_file) → đọc:
- Style catalog với font/size/bold defaults
- TOC entries và anchor IDs
- Front-matter zone boundary (end paraId)
- Sample paragraphs để hiểu visual structure

## Bước 2: Analyze Content
Đọc trực tiếp markdown source:
- Classify document type (academic/legal/report/...)
- Map heading levels → template styles dựa trên visual evidence từ template
- Identify TOC entries cần bookmark

## Bước 3: Compose Operations
Tự viết execution_ops list:
- Mỗi paragraph → 1 op với style, font, size EXPLICIT (không để inherit)
- Heading → lookup anchor ID từ TOC entries trong template
- Preserve front-matter zone boundary

## Bước 4: Execute + Verify
docx_apply_ops(ops) → docx_read_result() → compare với expected
```

### Phase 3 — Fallback Safety Net (~1 ngày)

LLM có thể sai về style names hay paraId. Cần một tool nhỏ:
```python
def docx_validate_ops(ops, template_profile) -> list[str]:
    """Trả về list warnings nếu ops reference style/path không tồn tại.
    Không block execution, chỉ warn để LLM tự correct."""
```

LLM đọc warnings và tự sửa ops trước khi execute — không cần retry loop phức tạp.

***

## Điều Kiện Cần Để Kiến Trúc Mới Hoạt Động

Một rủi ro thực tế cần thừa nhận: kiến trúc này **đặt cược vào context window và reasoning quality của model**. Với `Qwen3.6-35B-A3B-GGUF` (model hiện tại của orchestrator), context window ~32K là đủ cho template inspection + markdown + ops generation. Nhưng cần test với template lớn (>100 paragraphs front-matter).

Tradeoff so với scripts: scripts deterministic và fast, LLM non-deterministic và chậm hơn. Giải pháp: **chỉ dùng LLM cho reasoning phase, execution vẫn là scripts** — đây là điểm quan trọng nhất. LLM viết ops JSON → scripts execute → kết quả deterministic.

***

## Kết Luận: Có Nên Rebuild Không?

**Có, nhưng incremental.** Không cần rewrite toàn bộ một lần. Roadmap:

1. **Tuần 1**: Thêm `docx_inspect_raw` tool trả về template data không qua heuristics → test xem LLM có tự suy luận style map đúng không với 3–5 template mẫu
2. **Tuần 2**: Nếu LLM reasoning đúng ≥90% case → bắt đầu thay `plan_mapping.py` bằng LLM-generated `ops`
3. **Tuần 3**: Remove toàn bộ heuristic scripts, chỉ giữ primitive executor

Đây là cách "cách mạng hóa có kiểm soát" — không throw away working code trước khi có evidence LLM approach works.