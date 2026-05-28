# OfficeCLI DOCX: View Và Query

Dùng file này khi cần orient tài liệu trước khi sửa.

## Mục tiêu
- Xem outline để biết cấu trúc heading.
- Xem text, stats, issues hoặc annotated view ở phạm vi nhỏ.
- Lấy đúng semantic path trước khi `set`, `move`, `remove`.

## Lệnh thường dùng

```bash
officecli view "$FILE" outline
officecli view "$FILE" annotated
officecli view "$FILE" text --start 1 --end 80
officecli view "$FILE" stats
officecli view "$FILE" issues
officecli get "$FILE" /body --depth 1
officecli get "$FILE" /styles --depth 2
officecli get "$FILE" "/body/p[1]" --depth 2
officecli query "$FILE" 'paragraph[style=Heading1]'
officecli query "$FILE" 'paragraph[styleName="toc 1"]'
officecli query "$FILE" 'paragraph[numId>0]'
officecli query "$FILE" 'paragraph:contains("KẾT LUẬN")'
```

## Khi nào dùng `annotated`
- Profile template ban đầu để thấy path, style, numbering và text cùng lúc.
- Debug lệch `replace_range` hoặc anchor path.
- Kiểm tra paragraph nào đang mang numbering trực tiếp thay vì kế thừa style.

## Gợi ý selector CSS-like
- `paragraph[style=Heading1]`: chọn heading level 1 theo styleId.
- `paragraph[styleName="toc 1"]`: chọn paragraph TOC theo display name.
- `paragraph[numId>0]`: tìm paragraph đang có numbering trực tiếp.
- `table-row > table-cell`: dò cell trong bảng.
- `run[font!=Arial]`: tìm run lệch font.

## Context hygiene
- Luôn bắt đầu bằng `view outline` hoặc `view stats` nếu chưa biết cấu trúc.
- Chỉ tăng `get --depth` đến mức đủ dùng; không dump full tree nếu chỉ cần một nhánh.
- Với tài liệu dài, ưu tiên `outline`, `stats`, `annotated` hoặc `query` thay vì `view text` toàn file.