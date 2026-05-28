# OfficeCLI XLSX: Batch Va Resident Mode

Dung file nay khi phai chay nhieu lenh lien tiep tren workbook.

## Resident mode

```bash
officecli open "$FILE"
# ... nhieu thao tac add/set/remove ...
officecli save "$FILE"
officecli close "$FILE"
```

- Giu chuoi mutation trong cung terminal de tranh mat state.
- Phu hop khi can doc, kiem tra va mutate xen ke tren cung workbook.

## Batch mode

```bash
officecli batch "$FILE" --input batch.json
```

- Dung khi danh sach lenh da deterministic va co the bieu dien duoi dang JSON array.
- Batch hop cho import lon, style theo range va dien du lieu hang loat.

## Execution discipline
- Sau moi dot bien cau truc, chay `get`, `view` hoac `query` tren nhanh vua sua.
- Khong xep them mutation moi neu chua xac nhan formula, table range hoac chart source van hop le.
- Sau `close`, xac minh bang `validate` hoac mot lenh doc pham vi hep.

## Performance
- Uu tien batch cho thao tac dong bo tren nhieu cell/range de giam I/O.
- Uu tien resident mode cho workflow co vong lap profile -> mutate -> recheck.

## Error handling va rollback
- Neu mot buoc batch that bai giua chung, dung finalize va kiem tra workbook truoc khi chay tiep.
- Neu workflow yeu cau rollback, giu ban sao file dau vao hoac artifact batch de co the phuc hoi trang thai mot cach co kiem soat.