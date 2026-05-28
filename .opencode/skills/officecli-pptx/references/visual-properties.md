# OfficeCLI PPTX: Visual Properties

Dung file nay khi can format hinh khoi ma van giu visual language cua template.

## Fill va outline

```bash
officecli set "$FILE" '/slide[2]/shape[1]' --prop fill.color='#D9EAF7'
officecli set "$FILE" '/slide[2]/shape[1]' --prop outline.color='#1F4E78'
officecli set "$FILE" '/slide[2]/shape[1]' --prop outline.width=2
officecli set "$FILE" '/slide[2]/shape[1]' --prop outline.dash=solid
```

## Effects

```bash
officecli set "$FILE" '/slide[2]/shape[1]' --prop effect.shadow='outer:45:40000:#999999'
officecli set "$FILE" '/slide[2]/shape[1]' --prop effect.glow='#4F81BD:6'
officecli set "$FILE" '/slide[2]/shape[1]' --prop effect.softEdges=4
```

## Transform va z-order

```bash
officecli set "$FILE" '/slide[2]/shape[1]' --prop x=914400 --prop y=914400
officecli set "$FILE" '/slide[2]/shape[1]' --prop cx=3657600 --prop cy=2286000
officecli set "$FILE" '/slide[2]/shape[1]' --prop rotation=5400000
officecli move "$FILE" '/slide[2]/shape[1]' --before '/slide[2]/shape[2]'
```

- Don vi vi tri va kich thuoc thuong la EMUs; help-first neu chua chac.
- Khong thay doi z-order cua placeholder quan trong neu chua kiem tra overlap voi background/template art.

## Color resolution
- Uu tien theme colors cua template truoc khi hard-code RGB moi.
- Neu can dung RGB, kiem tra xem slide master co su dung scheme colors cho doi tuong cung loai hay khong.