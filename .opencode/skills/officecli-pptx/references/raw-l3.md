# OfficeCLI PPTX: L3 Raw XML Guardrail

Dung file nay chi khi L1/L2 khong du.

## Lenh L3

```bash
officecli raw "$FILE" /theme
officecli raw "$FILE" /slideMaster[1]
officecli raw "$FILE" /slideLayout[1]
officecli raw-set "$FILE" /slide[2] --xpath '//*' --action replace --xml '<p:sld />'
officecli add-part "$FILE" /customXml
```

## Khi nao duoc phep dung
- Can inspect XML edge-case ma `view`, `get`, `query` khong expose.
- Can mutate mot feature OfficeCLI chua co prop L2 tuong ung.
- Can copy/migrate relationship, custom part hoac layout binding co kiem soat.

## Khi nao khong duoc dung
- Chi vi quen sua XML truc tiep.
- Khi `slide`, `shape`, `textbox`, `picture`, `table`, `chart`, `notes`, `layout` da du de lam viec.

## Guardrails
- Luon doc XML truoc khi `raw-set`.
- Khi di chuyen hoac sao chep thanh phan giua slide, kiem tra lai `r:id` va relationship migration.
- Sau L3 mutation, phai `validate` va doc lai nhanh vua sua de kiem tra corrupt risk.

## Risks
- Sai relationship, layout binding hoac theme references co the lam hong deck.
- PPTX rat de vo placeholder binding neu sua XML mu ma khong re-resolve scaffold sau do.