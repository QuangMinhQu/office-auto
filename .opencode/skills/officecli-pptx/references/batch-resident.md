# OfficeCLI PPTX: Batch, Resident Va Preview

Dung file nay khi phai chay nhieu lenh lien tiep tren deck.

## Resident mode

```bash
officecli open "$FILE"
# ... nhieu thao tac add/set/move/remove ...
officecli save "$FILE"
officecli close "$FILE"
```

- Giu chuoi mutation trong cung terminal de tranh mat presentation state.
- Phu hop voi workflow profile -> mutate -> recheck tren tung slide.

## Batch mode

```bash
officecli batch "$FILE" --input batch.json
```

- Dung khi danh sach lenh da deterministic va co the bieu dien duoi dang JSON array.
- Batch hop cho bounded replacement tren nhieu slide sau khi `plan.json` da resolve xong.

## Execution discipline
- Sau moi dot bien cau truc, doc lai slide vua sua bang `get` hoac `query`.
- Neu preserve scaffold la hard gate, xac minh lai layout binding, footer va title slide truoc khi finalize.

## Live preview va watch

```bash
officecli view "$FILE" html
officecli watch "$FILE"
officecli unwatch "$FILE"
```

- Dung preview/watch de debug overflow hoac overlap, nhung khong giu server chay vo han neu da xong.