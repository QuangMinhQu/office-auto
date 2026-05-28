Tôi đã đọc kỹ `build_docx.py`. Bây giờ phân tích chính xác từng lỗi từ DOCX template và script.

***

# Phân tích 3 lỗi cụ thể sau run-005

Cả 3 lỗi đều có **root cause khác nhau** và cần fix ở các lớp khác nhau — từ XML structure trong `build_docx.py` đến cách Word handle field codes.

***

## Lỗi 1: TOC render ra text thô `TOC \o "1-3" \h \z \u`

### Root cause

TOC trong DOCX không phải là text — nó là một **field** (`w:fldChar` / `w:instrText` combo) hoặc **Structured Document Tag** (`w:sdt` với `w:sdtPr/w:docPart`). Khi `build_docx.py` đọc `word/document.xml` bằng `ElementTree` và rebuild bằng `ET.tostring()`, nó **không xử lý namespace đúng**.

Cụ thể ở dòng này trong `replace_body_range`:

```python
document_bytes = ET.tostring(tree, encoding="utf-8", xml_declaration=False)
```

`ET.tostring()` của Python's stdlib **không preserve namespace prefixes** — nó re-serializes mọi `xmlns:w=...` thành `ns0`, `ns1`, v.v. Kết quả là Word mở file lên không nhận ra các element thuộc namespace `w:` nữa. Nhưng tệ hơn: **`w:sdt` bị skip** trong `paragraph_index_to_body_child_range` vì logic chỉ count `w:p`, nhưng nếu TOC nằm trong `w:sdt` thì nó không bị xóa mà nội dung **upstream** của nó bị lệch index, gây replace sai range. Trong một số template, TOC field được viết dưới dạng `w:fldChar` + `w:instrText` trải qua nhiều `w:p` liên tiếp — những paragraph đó bị tính là paragraph thường và có thể bị include vào `replace_range`, sau đó bị xóa đi, **thay bằng text thô** của `instrText`.

Kiểm tra template: file DOCX sample của bạn có dòng `TOC \o "1-3" \h \z \u` xuất hiện trực tiếp — đây là `w:instrText` content của field code, bị render thành text vì **`w:fldChar w:fldCharType="begin"`** và **`w:fldChar w:fldCharType="end"`** đã bị mất khi script xóa các paragraph liên quan.

### Fix

Có 2 hướng:

**Hướng A (đúng về dài hạn):** Detect và preserve tất cả paragraph thuộc TOC field trước khi replace. TOC field trải qua nhiều paragraph, bắt đầu từ paragraph có `w:fldChar[@w:fldCharType='begin']` chứa `w:instrText` có `TOC`, kết thúc tại paragraph có `w:fldChar[@w:fldCharType='end']`. Những paragraph này phải được **excluded hoàn toàn** khỏi `replace_range`.

```python
def find_toc_paragraph_indices(body: ET.Element) -> set[int]:
    """Trả set paragraph_index của tất cả w:p thuộc TOC field."""
    toc_indices = set()
    in_toc = False
    para_idx = -1
    toc_start_para = None
    
    for child in body:
        if child.tag == qname("sectPr"):
            continue
        if child.tag != qname("p"):
            continue
        para_idx += 1
        
        for fld in child.iter(qname("fldChar")):
            fld_type = fld.get(qname("fldCharType"))
            if fld_type == "begin":
                # Check instrText trong cùng paragraph hoặc paragraph tiếp theo
                in_toc = True
                toc_start_para = para_idx
        for instr in child.iter(qname("instrText")):
            if "TOC" in (instr.text or ""):
                in_toc = True
        for fld in child.iter(qname("fldChar")):
            if fld.get(qname("fldCharType")) == "end" and in_toc:
                in_toc = False
                if toc_start_para is not None:
                    for i in range(toc_start_para, para_idx + 1):
                        toc_indices.add(i)
        
        if in_toc and toc_start_para is not None:
            toc_indices.add(para_idx)
    
    return toc_indices
```

Sau đó trong `profile_template.py`, khi tính `replace_range`, trừ ra các index thuộc TOC để `paragraph_start_index` bắt đầu **sau** TOC.

**Hướng B (nhanh hơn, đủ dùng ngay):** Trong `profile_template.py`, detect paragraph đầu tiên có `instrText` chứa `TOC` hoặc heading style `"TOC"`, và set `paragraph_start_index = max(toc_end_index + 1, first_heading_index)`.

***

## Lỗi 2: Heading bị duplicate — `1.2 1.2. Các thách thức...`

### Root cause

Đây là lỗi **double-numbering**: phần `1.2` đầu tiên là auto-numbering từ `w:numPr` (list numbering được gắn vào heading style của template), phần `1.2.` thứ hai là **text literal từ Markdown** mà `parse_markdown.py` giữ nguyên trong `block.text`.

Script `parse_markdown.py` parse heading như sau:

```python
# Nếu heading text là: "1.2. Các thách thức phổ biến..."
# thì block["text"] = "1.2. Các thách thức phổ biến..."
```

Và `build_docx.py` tạo paragraph với `pStyle = "Heading2"` — style này trong template của bạn đã có `w:numPr` linked đến numbering definition, tức là Word tự render thêm `1.2` ở đầu. Kết quả: `1.2` (auto) + `1.2. Các thách thức...` (text) = `1.2 1.2. Các thách thức...`.

### Fix

Trong `parse_markdown.py`, khi parse heading, **strip prefix numbering** trước khi lưu vào `block["text"]`:

```python
import re

def strip_heading_numbering(text: str) -> str:
    """
    Xóa prefix dạng '1.', '1.2.', '1.2.3.', 'CHƯƠNG 1.', 'I.', 'A.'
    khỏi heading text để tránh double-numbering với w:numPr.
    """
    # Pattern: số + dấu chấm, có thể lặp, có thể có space
    text = re.sub(r'^(?:CHƯƠNG\s+\d+\.\s*|[\d]+(?:\.[\d]+)*\.?\s+)', '', text.strip())
    # Pattern: chữ số La Mã hoặc chữ hoa
    text = re.sub(r'^(?:[IVX]+\.|[A-Z]\.)\s+', '', text)
    return text.strip()
```

Và áp dụng khi extract heading:

```python
if line.startswith("#"):
    level = len(line) - len(line.lstrip("#"))
    raw_text = line.lstrip("#").strip()
    clean_text = strip_heading_numbering(raw_text)
    blocks.append({"type": "heading", "level": level, "text": clean_text, "runs": [{"text": clean_text}]})
```

Đây là fix dứt điểm nhất. Lý do là template của bạn **đã có** numbering được quản lý bởi `w:abstractNumId` trong `word/numbering.xml` — việc script chèn text số vào heading là thừa và gây conflict.

***

## Lỗi 3: References là text thô, không phải auto-numbering

### Root cause

Đây là lỗi hiểu nhầm bản chất của  trong template Word. Trong DOCX mẫu chuẩn, phần tài liệu tham khảo dùng **list numbering** (`w:numPr`) — tương tự như heading, mỗi entry trong references list là một `w:p` với style `"References"` hoặc style nào đó linked đến một `w:abstractNum` có `w:numFmt` là `decimal` (số thập phân trong ngoặc: `[%1]`). Số `[2]` không phải text mà là **field value** được Word render từ định nghĩa numbering format.

Script hiện tại parse references từ Markdown dạng:

```markdown
 Krizhevsky, A., Sutskever, I., & Hinton, G. E. (2012)...
```

và lưu nguyên `block["text"] = " Krizhevsky..."`. Khi build, `make_paragraph` tạo paragraph với style `"Normal"` hoặc `"References"`, nhưng **không gắn `w:numPr`**. Kết quả là text thô, không phải auto number.

Có thêm một vấn đề: nếu template có numbering format dạng `[%1]`, thì khi chèn paragraph với cả text  lẫn `w:numPr`, sẽ ra ` Krizhevsky...`. 

### Fix

**Bước 1:** Trong `parse_markdown.py`, detect references section và strip prefix `[N]`:

```python
import re

def parse_reference_line(text: str) -> dict | None:
    """Parse ' Author...' thành block reference không có prefix số."""
    m = re.match(r'^\[(\d+)\]\s+(.*)', text.strip())
    if m:
        return {
            "type": "reference",
            "ordinal": int(m.group(1)),
            "text": m.group(2).strip(),
            "runs": [{"text": m.group(2).strip()}]
        }
    return None
```

**Bước 2:** Trong `plan_mapping.py`, map `"reference"` type sang style của template:

```python
style_map = {
    ...
    "reference": style_names.get("references") 
                 or style_names.get("tài liệu tham khảo")
                 or style_names.get("bibliography")
                 or "Normal",
}
```

**Bước 3:** Trong `build_docx.py`, khi `block["type"] == "reference"`, gắn `w:numPr` vào `pPr` **nếu** style của references có numbering trong template:

```python
def get_style_num_id(template_profile: dict, style_name: str) -> tuple[int, int] | None:
    """Lấy (numId, ilvl) từ template_profile nếu style có numbering."""
    style_num = template_profile.get("style_numbering", {})
    entry = style_num.get(style_name)
    if entry:
        return entry.get("numId"), entry.get("ilvl", 0)
    return None

# Trong make_paragraph:
if block.get("type") == "reference":
    num_info = get_style_num_id(template_profile, paragraph_style_name)
    if num_info:
        num_id, ilvl = num_info
        num_pr = make_element("numPr")
        ilvl_el = make_element("ilvl"); ilvl_el.set(qname("val"), str(ilvl))
        num_id_el = make_element("numId"); num_id_el.set(qname("val"), str(num_id))
        num_pr.append(ilvl_el); num_pr.append(num_id_el)
        paragraph_properties.append(num_pr)
```

Tuy nhiên, **trước hết** cần `profile_template.py` extract thêm `style_numbering` map — hiện tại script này không extract `w:numPr` default của từng style từ `word/styles.xml`. Đây là field còn thiếu trong `template_profile.json`.

***

## Tóm tắt fix ưu tiên

| Lỗi | File cần sửa | Loại fix |
|---|---|---|
| TOC bị render thành text | `profile_template.py` + `build_docx.py` | Detect & exclude TOC field paragraphs khỏi replace_range |
| Heading double-numbering | `parse_markdown.py` | Strip prefix số trước khi lưu vào `block["text"]` |
| References text thô | `parse_markdown.py` + `profile_template.py` + `build_docx.py` | Strip `[N]` prefix, extract `style_numbering` từ styles.xml, gắn `w:numPr` khi build |

Fix theo thứ tự: **heading numbering** trước (1 file, 5 dòng, impact ngay), rồi **TOC detection** (phức tạp hơn, cần test), rồi **references numbering** (cần thêm field vào `profile_template.py` trước).