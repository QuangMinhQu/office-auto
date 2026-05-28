# OfficeCLI DOCX: View Và Query

Dùng file này khi cần orient tài liệu trước khi sửa.

## Mục tiêu
- Xem outline để biết cấu trúc heading.
- Xem text hoặc stats ở phạm vi nhỏ.
- Lấy đúng semantic path trước khi `set`, `move`, `remove`.

## Lệnh thường dùng

```bash
officecli view "$FILE" outline
officecli view "$FILE" text --start 1 --end 80
officecli view "$FILE" stats
officecli view "$FILE" issues
officecli get "$FILE" /body --depth 1
officecli get "$FILE" "/body/p[1]"
officecli query "$FILE" 'paragraph[style=Heading1]'
officecli query "$FILE" 'p:contains("KẾT LUẬN")'
```

## Quy tắc dùng
- Luôn bắt đầu bằng `view outline` nếu chưa biết cấu trúc.
- Chỉ đọc phạm vi nhỏ đủ để xác định anchor hoặc style map.
- Với tài liệu dài, ưu tiên `outline` và `query` thay vì `view text` toàn file.