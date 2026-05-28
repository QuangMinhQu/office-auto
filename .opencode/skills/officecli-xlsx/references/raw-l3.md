# OfficeCLI XLSX: L3 Raw XML Guardrail

Dung file nay chi khi L1/L2 khong du.

## Lenh L3

```bash
officecli raw "$FILE" /styles
officecli raw "$FILE" /sharedStrings
officecli raw "$FILE" /Sheet1/drawing
officecli raw-set "$FILE" /styles --xpath '//*' --action replace --xml '<styleSheet />'
officecli add-part "$FILE" /customXml
```

## Khi nao duoc phep dung
- Can inspect XML edge-case ma `view`, `get`, `query` khong expose.
- Can mutate mot feature OfficeCLI chua co prop L2 tuong ung.
- Can chen custom XML part hoac sua drawing/schema ordering co kiem soat.

## Khi nao khong duoc dung
- Chi vi quen sua XML truc tiep.
- Khi `sheet`, `row`, `cell`, `table`, `chart`, `pivot`, `style` da du de lam viec.

## Guardrails
- Luon doc XML truoc khi `raw-set`.
- Neu sua worksheet XML, phai giu thu tu the hop le theo OpenXML schema.
- Sau L3 mutation, phai `validate` va doc lai nhanh vua sua de kiem tra corrupt risk.

## Risks
- Sai thu tu the hoac relationship co the lam hong workbook.
- `sharedStrings`, `styles` va drawing parts la diem de vo package neu mutate mu.