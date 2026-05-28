# OfficeCLI PPTX: View Va Query

Dung file nay khi can orient presentation truoc khi sua.

## Muc tieu
- Xem cay slide, layout, placeholder va cac shape chinh de biet scaffold dang co.
- Lay dung semantic path truoc khi `set`, `add`, `move`, `remove`.
- Query co chon loc de profile dung slide can thay ma khong dump ca deck vao context.

## Lenh thuong dung

```bash
officecli view "$FILE" stats
officecli get "$FILE" / --depth 2
officecli get "$FILE" /slide[1] --depth 2
officecli get "$FILE" '/slide[1]/shape[2]' --depth 2
officecli query "$FILE" 'slide'
officecli query "$FILE" 'slide > shape'
officecli query "$FILE" 'shape[kind=textbox]'
officecli query "$FILE" 'shape:title'
officecli query "$FILE" 'shape:contains("Sales Report")'
officecli query "$FILE" 'picture[altText]'
```

## Presentation tree
- Bat dau bang `get / --depth 2` de thay slide, layout refs, theme va presentation-level parts.
- Khi can chi tiet mot slide, doc rieng nhanh do thay vi dump ca deck.

## Selector engine
- `shape[kind=textbox]`: loc textbox.
- `table[rowCount>3]`: loc table theo kich thuoc neu version ho tro.
- `shape[font="Arial"]`: tim shape co text mang font cu the.
- `shape[color="#FF0000"]`: tim shape theo mau.

## Content va positional matching
- `shape:contains("Week 1")`: tim text ben trong shape.
- `slide[1] > shape`: loc shape thuoc mot slide cu the.
- `slide[2] > table`: lay bang trong slide thu 2.

## Placeholder resolution
- Placeholder co the ke thua tu layout hoac master; profile slide va layout gan no truoc khi ket luan rang slide dang thieu text.
- Neu mot title shape khong xuat hien ro o slide tree, query layout/master de kiem tra placeholder binding.

## Context hygiene
- Luon profile title slide va mot content slide mau truoc khi nhan deck moi.
- Neu task la thay noi dung trong mot vung bounded, chi doc slide range lien quan.