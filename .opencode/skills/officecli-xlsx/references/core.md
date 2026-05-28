# OfficeCLI XLSX: Core Ops

```bash
officecli get "$FILE" / --depth 2
officecli query "$FILE" 'sheet'
officecli get "$FILE" /Sheet1/A1
officecli set "$FILE" /Sheet1/A1 --prop value='hello'
officecli set "$FILE" /Sheet1/B2 --prop formula='SUM(B1:B10)'
officecli add "$FILE" / --type sheet --prop name='Report'
officecli import "$FILE" /Sheet1 data.csv
```

## Gợi ý
- Dùng `get` để lấy cây workbook theo depth nhỏ trước khi mutate.
- Không sửa trực tiếp XML sheet khi `sheet`, `row`, `cell`, `table` đã đủ.
- Với chart/pivot/named range phức tạp, kiểm tra `help xlsx` trước khi dùng L3.
