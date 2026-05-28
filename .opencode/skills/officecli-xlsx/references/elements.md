# OfficeCLI XLSX: Elements

Dung file nay khi can mutate hoac profile cac thanh phan chinh cua workbook.

## Sheet

```bash
officecli add "$FILE" / --type sheet --prop name='Report'
officecli set "$FILE" /Sheet1 --prop name='Week 1'
officecli set "$FILE" /Sheet1 --prop tabColor='#1F4E78'
officecli set "$FILE" /Sheet1 --prop zoom=125
officecli set "$FILE" /Sheet1 --prop freezePanes='A2'
officecli remove "$FILE" /Sheet3
```

- Doi ten sheet truoc khi viet formula hoac table neu ten sheet tham gia tham chieu.
- Sau khi them, xoa hoac doi ten sheet, query lai workbook tree de xac nhan thu tu va binding.

## Row va column

```bash
officecli add "$FILE" /Sheet1 --type row --prop index=5
officecli remove "$FILE" '/Sheet1/row[5]'
officecli set "$FILE" '/Sheet1/row[1]' --prop height=24
officecli set "$FILE" '/Sheet1/column[2]' --prop width=18
officecli set "$FILE" '/Sheet1/column[4]' --prop hidden=true
```

- Khi chen hoac xoa row/column, phai kiem tra lai formula va table range co bi dich sai hay khong.

## Cell

```bash
officecli set "$FILE" '/Sheet1/row[2]/cell[1]' --prop value='Revenue'
officecli set "$FILE" 'Sheet1!B2' --prop value=1250000
officecli set "$FILE" 'Sheet1!C2' --prop type=number
officecli set "$FILE" 'Sheet1!D2' --prop type=date --prop value='2026-05-28'
officecli set "$FILE" 'Sheet1!E2' --prop type=boolean --prop value=true
```

- Xac nhan `type` neu workflow yeu cau giu dung date/number thay vi string.
- Khong dua text markdown hoac placeholder residue vao cell do workbook de semantic content can sach.

## Table

```bash
officecli add "$FILE" /Sheet1 --type table --prop range='A1:D20' --prop name='SalesTable'
officecli set "$FILE" /Sheet1/table[1] --prop style='TableStyleMedium2'
officecli set "$FILE" /Sheet1/table[1] --prop showHeaderRow=true
officecli set "$FILE" /Sheet1/table[1] --prop showAutoFilter=true
```

- Table phu hop khi can header, auto-filter va style on dinh cho du lieu dang bang.

## Chart

```bash
officecli add "$FILE" /Sheet1 --type chart --prop kind=bar --prop range='A1:B6' --prop title='Weekly Revenue'
officecli set "$FILE" /Sheet1/chart[1] --prop title='Weekly Revenue by Day'
officecli set "$FILE" /Sheet1/chart[1]/series[1] --prop name='Revenue'
```

- Kiem tra lai nguon du lieu va ten series sau khi chen hoac xoa row/column.
- Voi chart phuc tap, hoi `officecli help xlsx chart --json` truoc khi doan prop.

## Picture va shape

```bash
officecli add "$FILE" /Sheet1 --type picture --prop src='chart.png' --prop anchor='F2'
officecli set "$FILE" /Sheet1/picture[1] --prop width=480 --prop height=240
officecli add "$FILE" /Sheet1 --type shape --prop kind=textbox --prop text='Week 1 summary'
```

- Dung shape cho note nhe, dung table/cell cho du lieu chinh.

## PivotTable

```bash
officecli add "$FILE" /Sheet1 --type pivotTable --prop source='SalesTable' --prop destination='H3'
officecli set "$FILE" /Sheet1/pivotTable[1] --prop rows='Region'
officecli set "$FILE" /Sheet1/pivotTable[1] --prop columns='Week'
officecli set "$FILE" /Sheet1/pivotTable[1] --prop values='Revenue:sum'
officecli set "$FILE" /Sheet1/pivotTable[1] --prop filters='Owner'
```

- Pivot table thuong can query lai de xac nhan field bindings sau khi doi source range.