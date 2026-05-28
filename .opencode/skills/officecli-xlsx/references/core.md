# OfficeCLI XLSX: Core Quick Ops

```bash
officecli get "$FILE" / --depth 2
officecli query "$FILE" 'sheet'
officecli get "$FILE" /Sheet1/A1
officecli set "$FILE" /Sheet1/A1 --prop value='hello'
officecli set "$FILE" /Sheet1/B2 --prop formula='SUM(B1:B10)'
officecli add "$FILE" / --type sheet --prop name='Report'
officecli import "$FILE" /Sheet1 data.csv
```

## Dung file nay khi nao
- Can mot cheat sheet rat ngan de orient nhanh truoc khi mo file tham chieu chi tiet.
- Khong dung file nay thay cho `SKILL.md` hoac cac reference chuyen sau.

## Mo tiep file nao
- `view-query.md`: orient workbook, named range, sparse cells.
- `elements.md`: sheet, row, column, cell, table, chart, pivot.
- `formulas-functions.md`: formula, array formula, defined names, formula errors.
- `styles-formatting.md`: font, fill, border, alignment, number format, conditional formatting.
- `data-operations.md`: import/export, validation, sort, filter, replace.
- `advanced-features.md`: protection, comments, hyperlinks, page setup.
- `batch-resident.md`: multi-step mutation discipline.
- `raw-l3.md`: XML fallback co guardrail.
