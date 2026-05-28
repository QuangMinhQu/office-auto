# OfficeCLI XLSX: Styles Va Formatting

Dung file nay khi can format workbook ma van giu style hygiene.

## Font

```bash
officecli set "$FILE" 'Sheet1!A1' --prop font.name='Aptos'
officecli set "$FILE" 'Sheet1!A1' --prop font.size=16
officecli set "$FILE" 'Sheet1!A1' --prop font.bold=true
officecli set "$FILE" 'Sheet1!A1' --prop font.color='#1F1F1F'
```

## Fill va border

```bash
officecli set "$FILE" 'Sheet1!A1:D1' --prop fill.color='#D9EAF7'
officecli set "$FILE" 'Sheet1!A1:D10' --prop border.bottom.style=thin
officecli set "$FILE" 'Sheet1!A1:D10' --prop border.bottom.color='#9AA5B1'
```

## Alignment va merge

```bash
officecli set "$FILE" 'Sheet1!A1:D1' --prop alignment.horizontal=center
officecli set "$FILE" 'Sheet1!A1:D1' --prop alignment.vertical=center
officecli set "$FILE" 'Sheet1!A1:D10' --prop alignment.wrapText=true
officecli set "$FILE" 'Sheet1!A1:D1' --prop merge=true
```

- Merge chi nen dung cho tieu de hoac label display; khong dung cho bang du lieu can sort/filter.

## Number format

```bash
officecli set "$FILE" 'Sheet1!B2:B10' --prop numberFormat='#,##0'
officecli set "$FILE" 'Sheet1!C2:C10' --prop numberFormat='$#,##0.00'
officecli set "$FILE" 'Sheet1!D2:D10' --prop numberFormat='0.00%'
officecli set "$FILE" 'Sheet1!E2:E10' --prop numberFormat='yyyy-mm-dd'
```

## Conditional formatting

```bash
officecli add "$FILE" /Sheet1 --type conditionalFormatting --prop range='B2:B10' --prop rule='greaterThan:1000'
officecli add "$FILE" /Sheet1 --type conditionalFormatting --prop range='C2:C10' --prop rule='containsText:late'
officecli add "$FILE" /Sheet1 --type conditionalFormatting --prop range='D2:D10' --prop rule='colorScale:3'
```

- Sau khi dat rule, query lai node conditional formatting neu workbook co nhieu rule chong nhau.

## Cell styles va style dedupe
- Uu tien ap dung style cap range thay vi set tung cell neu co the.
- Neu workbook phat sinh nhieu style gan giong nhau, gop lai de tranh phinh `WorkbookStylesPart`.
- Kiem tra `help xlsx style --json` truoc khi doan ten prop style manager hoac cell style built-in.