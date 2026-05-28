# OfficeCLI DOCX: Elements Cơ Bản

Dùng file này khi cần thêm, sửa hoặc sắp xếp block nội dung.

## Các element thường gặp
- `paragraph`
- `run`
- `table`, `table-row`, `table-cell`
- `picture`
- `section`
- `footer`, `header`
- `field`, `toc`

## Ví dụ mutation tối thiểu

```bash
officecli add "$FILE" /body --type paragraph --prop text="Tiêu đề" --prop style=Heading1
officecli add "$FILE" /body --type paragraph --prop style=Normal --after "/body/p[@paraId=ABCD1234]"
officecli add "$FILE" "/body/p[last()]" --type run --prop text="đoạn nhấn mạnh" --prop bold=true
officecli set "$FILE" "/body/p[1]" --prop align=center
officecli remove "$FILE" "/body/p[last()]"
officecli move "$FILE" "/body/p[5]" --before "/body/p[3]"
officecli add "$FILE" /body --type paragraph --from "/body/p[3]"
```

## Run-level formatting

```bash
officecli add "$FILE" "/body/p[last()]" --type run --prop text="inline code" --prop font="Courier New"
officecli set "$FILE" "/body/p[4]/r[2]" --prop italic=true
officecli set "$FILE" "/body/p[4]/r[2]" --prop color=#C0392B
```

## Thao tác bảng

```bash
officecli set "$FILE" "/body/tbl[1]/tr[1]/tc[1]" --prop text='value'
officecli add "$FILE" "/body/tbl[1]" --type table-row
officecli add "$FILE" "/body/tbl[1]/tr[last()]" --type table-cell --prop text='new cell'
```

## Lưu ý
- `style` và `numbering` là hai lớp khác nhau.
- `add --from` phù hợp để clone khung paragraph/table từ template thay cho copy XML node thủ công.
- Không suy đoán prop hiếm; cần thì quay lại `officecli help docx <element> --json`.