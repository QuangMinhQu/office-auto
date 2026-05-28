# OfficeCLI DOCX: Elements Cơ Bản

Dùng file này khi cần thêm hoặc sửa block nội dung.

## Các element thường gặp
- `paragraph`
- `run`
- `table`
- `image`
- `section`
- `footer`
- `header`
- `field`

## Ví dụ tối thiểu

```bash
officecli add "$FILE" /body --type paragraph --prop text="Tiêu đề" --prop style=Heading1
officecli add "$FILE" /body --type paragraph --prop text="Nội dung đoạn văn" --prop style=Normal
officecli set "$FILE" "/body/p[1]" --prop align=center
officecli remove "$FILE" "/body/p[last()]"
```

## Lưu ý
- `style` và `numbering` là hai lớp khác nhau.
- Không suy đoán prop hiếm; cần thì quay lại `officecli help`.