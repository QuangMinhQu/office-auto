Tôi đã đọc đủ toàn bộ codebase. Bây giờ phân tích toàn diện.

***

# Root Cause Analysis: Tại sao output DOCX ra kém chất lượng

Sau khi đọc kỹ toàn bộ `.opencode/AGENTS.md`, 4 skills, 5 pipeline scripts, `task.md`, `issue.md` và `build_report.py`, tôi xác định được **3 lớp vấn đề** với mức độ ưu tiên rõ ràng. Vấn đề không nằm ở một chỗ duy nhất mà là sự kết hợp của cả ba, và chúng khuếch đại lẫn nhau.

***

## Lớp 1: Script pipeline — lỗi nghiêm trọng nhất

Đây là root cause số một, ảnh hưởng trực tiếp đến output cuối.

### `build_docx.py` — paragraph replace logic bị sai cơ bản

Script này dùng `paragraph_index_to_body_child_range()` để map từ "paragraph index" sang "child index trong `w:body`". Nhưng logic đang **skip `sectPr`** mà **không skip các child khác** như `w:tbl`, `w:sdt`, `w:bookmarkStart`, `w:bookmarkEnd`. Trong một DOCX thực tế từ Word, `w:body` chứa không chỉ `w:p` mà còn table (`w:tbl`), structured document tags (`w:sdt`), và nhiều element khác. Vì vậy, `paragraph_counter` sẽ **tính sai index**, khiến vùng bị xóa không đúng — có thể xóa nhầm cả bìa, TOC, hoặc danh mục.

```python
# BUG: chỉ skip sectPr và chỉ count w:p, bỏ qua w:tbl và w:sdt
for child_index, child in enumerate(list(body)):
    if child.tag == qname("sectPr"):
        continue
    if child.tag != qname("p"):   # <-- tbl, sdt, bookmarkStart bị bỏ qua
        continue
    paragraph_counter += 1
```

Hệ quả: khi template có bảng (ví dụ trang bìa dạng bảng, bảng trong TOC section), `end_child_index` sẽ sai, dẫn đến replace sai vùng.

### `build_docx.py` — `make_paragraph` quá đơn giản, không map numbering

Hàm `make_paragraph` chỉ tạo `w:p` với `pStyle` và một `w:r/w:t` duy nhất. Nó **không chèn `w:numPr`** (numbering properties) cho heading có đánh số, **không chèn `rPr`** (run properties như bold, italic), và **không handle `inline markup`** trong Markdown (dấu `**bold**`, `*italic*`, inline code). Kết quả là toàn bộ nội dung ra đều dạng plain text không có bold, không có số thứ tự heading, và không có table thực sự.

### `profile_template.py` — `replace_range` định nghĩa sai biên

Logic detect range như sau:

```python
if first_heading_index is not None:
    replace_candidates.append({
        "paragraph_start_index": first_heading_index,
        "paragraph_end_index": last_paragraph_index,
        ...
    })
```

`last_paragraph_index = len(paragraphs) - 1` tức là **tính đến paragraph cuối cùng trong body**. Trong DOCX, `w:body` thường có một `sectPr` hoặc paragraph cuối chứa section properties. Bằng cách replace đến `last_paragraph_index`, script **xóa cả paragraph chứa `sectPr` của body**, làm mất section break cuối — đây là phần mang thông tin page size, margins, và header/footer linking. Đây là lý do header/footer hay bị mất hoặc bị lỗi.

### `parse_markdown.py` — parser quá sơ sài

Parser không xử lý được:
- Numbered lists (`1. `, `2. `)
- Nested lists (indent-based)
- Bold/italic inline (`**`, `*`, `__`)
- Code blocks (fenced với ` ``` `)
- Blockquotes (`>`)
- Horizontal rules

Toàn bộ inline formatting bị gộp vào text thô. Một câu như `**Kết luận:** abc` sẽ ra `**Kết luận:** abc` thay vì run bold rồi run normal.

### `plan_mapping.py` — `style_map` infer cơ học

```python
"h1": style_names.get("heading 1") or style_names.get("heading1") or "Heading 1",
```

Logic này match theo **lowercase name** của style. Nhưng trong DOCX tiếng Việt dùng font VN, style thường có tên dạng `Tieu-de-1`, `Heading_VN1`, hoặc custom style như `Chuong`. `plan_mapping.py` sẽ fallback về `"Heading 1"` — style mặc định của Word, không phải style custom của template — nên numbering và formatting của heading không được áp đúng.

***

## Lớp 2: Skill config — agent bị routing sai và thiếu constraint

### `officecli-docx` vs `AGENTS.md` conflict vẫn còn

`AGENTS.md` nói: *"Chỉ load `officecli-docx` khi cần tra cứu cú pháp"*. Nhưng `docx-from-template/SKILL.md` trong phần usage không có đủ constraint để ngăn agent tự dùng OfficeCLI ad-hoc bên ngoài pipeline. Kết quả là agent có thể chạy OfficeCLI commands trực tiếp thay vì qua pipeline scripts, bypassing toàn bộ artifact system.

### `md-to-docx-pipeline/SKILL.md` — script contracts không có error contract

Contract trong skill chỉ mô tả happy path (input/output). Không có phần nào mô tả **khi nào script phải raise exception vs return error JSON**, nên agent không biết cách handle khi `plan.json` có `status: blocked`. Agent thường tiếp tục chạy `build_docx.py` ngay cả khi plan bị blocked, hoặc ngược lại kết luận xong khi chưa chạy.

### `docx-qa/SKILL.md` — QA checklist không có threshold cụ thể

Checklist có các item như *"header/footer không bị mất hoặc giảm bất thường"* nhưng không định nghĩa **thế nào là bất thường**. Agent open model không biết rằng nếu template có 2 header nhưng output chỉ còn 1 là fail. Cần threshold số học rõ ràng: `header_count_output >= header_count_template`.

***

## Lớp 3: OfficeCLI format reading — hạn chế có thật nhưng không phải root cause

OfficeCLI đọc DOCX tốt ở mức structure (open/close, get element, set prop). Vấn đề không phải OfficeCLI không hiểu format, mà là **pipeline scripts đang bypass OfficeCLI hoàn toàn** — họ đọc thẳng `word/document.xml` bằng Python `xml.etree.ElementTree` rồi ghi thẳng vào ZIP. Cách này bỏ qua toàn bộ relationship management của OfficeCLI:

- `word/_rels/document.xml.rels` — quan hệ giữa body và header/footer, images
- `[Content_Types].xml` — type registry cho các part mới
- `word/settings.xml` — compat settings
- `word/fontTable.xml` — font embedding

Khi script ghi thẳng, các relationship này có thể bị stale, khiến Word mở file lên thấy header/footer không link đúng section, hoặc numbering bị reset.

***

## Bản đồ lỗi → Fix ưu tiên

| Lỗi quan sát | Root cause | Fix |
|---|---|---|
| Heading không có số thứ tự | `make_paragraph` không chèn `w:numPr` | Thêm numPr lookup từ `template_profile.json` |
| Bold/italic mất hết | Parser không parse inline markup | Thêm inline parser cho `**`, `*`, code |
| Trang bìa/TOC bị xóa | `replace_range` end đến `last_paragraph`, bao gồm sectPr | Exclude last paragraph nếu chứa sectPr |
| Header/footer mất | Ghi thẳng XML không sync rels | Kiểm tra headers vẫn reference đúng trong rels sau build |
| Heading style không match | `style_map` fallback về `"Heading 1"` dù template dùng custom style | Thêm fuzzy match theo style type attribute thay vì name |
| `w:tbl` trong template bị xóa nhầm | `paragraph_index_to_body_child_range` chỉ count `w:p` | Đếm tất cả non-sectPr children, không chỉ `w:p` |

***

## Fix ngay lập tức — 3 thay đổi có ROI cao nhất

**Fix 1 — `profile_template.py`:** Khi tính `paragraph_end_index`, trừ đi các paragraph cuối chứa `sectPr` hoặc chỉ chứa `pPr/sectPr`:

```python
# Tìm last "real content" paragraph, không phải last paragraph của body
last_paragraph_index = None
for i, p in reversed(list(enumerate(paragraphs))):
    ppr = p.find("w:pPr/w:sectPr", WORD_NAMESPACE)
    if ppr is None and paragraph_text(p).strip():
        last_paragraph_index = i
        break
```

**Fix 2 — `build_docx.py`:** Đếm tất cả children, không chỉ `w:p`, khi map paragraph index:

```python
for child_index, child in enumerate(list(body)):
    if child.tag == qname("sectPr"):
        continue
    # Đếm mọi child là real content (p, tbl, sdt, ...)
    if child.tag == qname("p"):
        paragraph_counter += 1
    # w:tbl, w:sdt vẫn chiếm child_index nhưng không tăng paragraph_counter
```

**Fix 3 — `parse_markdown.py`:** Thêm inline markup parser để `make_paragraph` có thể tạo multi-run với `w:rPr`:

```python
def parse_inline(text: str) -> list[dict]:
    """Trả list runs: [{"text": ..., "bold": bool, "italic": bool}]"""
    import re
    runs = []
    pattern = re.compile(r'(\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|(.+?)(?=\*\*|\*|`|$))', re.DOTALL)
    for m in pattern.finditer(text):
        if m.group(2): runs.append({"text": m.group(2), "bold": True, "italic": False})
        elif m.group(3): runs.append({"text": m.group(3), "bold": False, "italic": True})
        elif m.group(4): runs.append({"text": m.group(4), "bold": False, "italic": False, "code": True})
        elif m.group(5): runs.append({"text": m.group(5), "bold": False, "italic": False})
    return [r for r in runs if r["text"]]
```

***

## Kết luận phân tích

Vấn đề chính **không phải** do OfficeCLI không đọc được DOCX, cũng **không phải** do agent không hiểu format — mà do 3 script (`profile_template.py`, `build_docx.py`, `parse_markdown.py`) có logic sai làm sai lệch replace range, xóa nhầm sectPr, và mất toàn bộ inline formatting. Skill config chỉ là vấn đề thứ yếu gây token bloat và routing nhầm, không phải root cause của output xấu. Ưu tiên fix pipeline scripts trước, sau đó mới tightening skill constraints.