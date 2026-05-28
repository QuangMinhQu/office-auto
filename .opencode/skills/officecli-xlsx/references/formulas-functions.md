# OfficeCLI XLSX: Formulas Va Functions

Dung file nay khi can set, sua, kiem tra hoac debug cong thuc.

## Set formula

```bash
officecli set "$FILE" 'Sheet1!B2' --prop formula='SUM(B3:B10)'
officecli set "$FILE" 'Sheet1!C2' --prop formula='B2/$F$1'
officecli set "$FILE" 'Sheet1!D2' --prop formula='IFERROR(XLOOKUP(A2,Lookup!A:A,Lookup!B:B),"N/A")'
```

- Formula nen duoc quote bang single quote neu co `$`, dau phay hoac ngoac.

## Formula integrity
- Sau khi chen hoac xoa row/column, query `cell[formula]` tren range lien quan de tim `#REF!` som.
- Neu source range cua table/chart/pivot thay doi, kiem tra lai formula phu thuoc truoc khi finalize.
- Neu mutation lon, gom thao tac cau truc va formula vao cung resident session de de rollback.

## Array formulas va ham hien dai

```bash
officecli set "$FILE" 'Sheet1!G2' --prop formula='FILTER(A2:C100,C2:C100>0)'
officecli set "$FILE" 'Sheet1!J2' --prop formula='UNIQUE(A2:A100)'
officecli set "$FILE" 'Sheet1!K2' --prop formula='XLOOKUP(I2,A2:A100,B2:B100)'
```

- Voi dynamic arrays, xac nhan vung spill khong de len du lieu dang co.

## Named formulas va defined names

```bash
officecli add "$FILE" / --type name --prop name='TaxRate' --prop refersTo='=Config!$B$2'
officecli set "$FILE" /name[1] --prop formula='=SUM(Sheet1!$B$2:$B$10)'
```

- Dat ten cho formula hoac range khi can tai su dung trong nhieu sheet.

## Relative va absolute references
- `A1` la tham chieu tuong doi, se dich khi copy hoac fill.
- `$A$1` la tham chieu tuyet doi, phu hop cho config cell hoac anchor.
- `A$1` va `$A1` dung khi chi khoa mot chieu.

## Formula errors can canh bao
- `#REF!`: tham chieu bi vo do xoa row/column/sheet.
- `#VALUE!`: sai kieu du lieu dau vao.
- `#DIV/0!`: mau so bang 0.
- `#NAME?`: ham hoac named range khong ton tai.

## Kiem tra nhanh
- Query `cell[formula]` truoc va sau mutation co anh huong cau truc.
- Neu output cuoi la report, uu tien xoa residue va loi formula truoc khi style hoan thien.