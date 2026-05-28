# OfficeCLI XLSX: View Va Query

Dung file nay khi can orient workbook truoc khi sua.

## Muc tieu
- Xem cay workbook de biet sheet, named range, table, chart va style part dang co.
- Lay dung semantic path hoac range notation truoc khi `set`, `add`, `remove`.
- Query co chon loc de tranh dump qua nhieu cell vao context.

## Lenh thuong dung

```bash
officecli view "$FILE" stats
officecli get "$FILE" / --depth 2
officecli get "$FILE" /Sheet1 --depth 2
officecli get "$FILE" "/Sheet1/row[1]/cell[1]" --depth 2
officecli get "$FILE" 'Sheet1!A1:D10'
officecli query "$FILE" 'sheet'
officecli query "$FILE" 'cell[value!=""]'
officecli query "$FILE" 'cell[formula]'
officecli query "$FILE" 'table[name="SalesTable"]'
officecli query "$FILE" 'named-range'
```

## Workbook tree
- Bat dau bang `get / --depth 2` de lay danh sach sheet, table, chart, named range va workbook-level parts.
- Neu can chi tiet mot sheet, tang do sau tai nhanh do thay vi dump toan workbook.

## Path notation va Excel notation
- Path notation hop cho schema tree va thao tac theo node, vi du `"/Sheet1/row[3]/cell[2]"`.
- Excel notation hop cho range truy cap theo luoi, vi du `'Sheet1!A1:D10'`.
- Neu workflow can map giua hai kieu dia chi, uu tien `get` tren pham vi hep de xac nhan truoc khi mutate.

## Query filters
- `sheet[name="Report"]`: tim sheet theo ten.
- `cell[value="Done"]`: tim o theo gia tri.
- `cell[formula*="SUM("]`: tim formula theo pattern neu version ho tro selector tuong ung.
- `cell[type=date]`: loc theo kieu du lieu.

## Sparse cell handling
- Voi sheet lon, uu tien `query 'cell[value!=""]'` hoac `get 'Sheet1!A1:D50'` thay vi doc ca sheet.
- Neu can profile layout bang du lieu thuc, lay range co du lieu thay vi day du cot/hang rong.

## Named ranges
- Dung `query 'named-range'` de liet ke vung da dat ten.
- Sau do dung `get` vao node named range hoac range ma no tro toi de xac nhan pham vi su dung.

## Context hygiene
- Luon bat dau bang depth nho, chi mo rong khi can mot nhanh cu the.
- Neu task chu yeu la formula debug, query `cell[formula]` truoc khi doc text hoặc style.