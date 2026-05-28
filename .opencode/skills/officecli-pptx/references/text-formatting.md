# OfficeCLI PPTX: Text Formatting

Dung file nay khi can sua text ben trong placeholder, textbox hoac shape.

## Paragraph

```bash
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]' --prop alignment=center
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]' --prop spacingAfter=12
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]' --prop indent=18
```

## Run

```bash
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]/run[1]' --prop font.name='Aptos'
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]/run[1]' --prop font.size=24
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]/run[1]' --prop font.bold=true
officecli set "$FILE" '/slide[2]/shape[1]/paragraph[1]/run[1]' --prop font.color='#1F1F1F'
```

## Bullet va numbering

```bash
officecli set "$FILE" '/slide[3]/shape[2]/paragraph[1]' --prop bullet.type=bullet
officecli set "$FILE" '/slide[3]/shape[2]/paragraph[2]' --prop bullet.level=1
officecli set "$FILE" '/slide[3]/shape[2]/paragraph[3]' --prop bullet.type=number
```

- Giu level bullet nhat quan voi layout title/body dang dung.

## Text trong shape va placeholder
- Mot shape text thuong chua `TextBody` gom nhieu paragraph va run.
- Neu slide duoc layout cap placeholder, uu tien sua text trong placeholder thay vi tao textbox de de giu scaffold.
- Placeholder thuong co vai tro `Title`, `Subtitle`, `Body`, `Footer` hoac `Slide Number`.

## Rich text
- Dung nhieu run trong cung mot paragraph khi can nhan manh mot phan text ma van giu mot shape duy nhat.
- Sau khi tach run, query lai shape do de chac khong bi lap bullet hoac mat placeholder binding.