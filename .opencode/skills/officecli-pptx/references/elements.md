# OfficeCLI PPTX: Elements

Dung file nay khi can mutate hoac profile cac thanh phan chinh cua deck.

## Slide

```bash
officecli add "$FILE" / --type slide --prop layout='Title and Content'
officecli remove "$FILE" /slide[4]
officecli move "$FILE" /slide[5] --before /slide[3]
officecli add "$FILE" /slide[2] --type duplicate
officecli set "$FILE" /slide[3] --prop layout='Section Header'
```

- Neu workflow la preserve scaffold, dung layout co san hoac layout-compatible trong template, khong tu sinh deck moi tu dau.

## Shape va textbox

```bash
officecli add "$FILE" /slide[2] --type shape --prop kind=rect --prop x=914400 --prop y=914400 --prop cx=3657600 --prop cy=914400
officecli add "$FILE" /slide[2] --type textbox --prop text='Weekly highlights'
officecli set "$FILE" '/slide[2]/shape[2]' --prop text='Updated summary'
```

- Uu tien dien text vao placeholder/textbox san co neu template da co content slots.

## Picture

```bash
officecli add "$FILE" /slide[2] --type picture --prop src='chart.png' --prop x=914400 --prop y=1828800 --prop cx=3657600 --prop cy=2286000
officecli set "$FILE" /slide[2]/picture[1] --prop altText='Revenue chart'
```

## Table

```bash
officecli add "$FILE" /slide[3] --type table --prop rows=4 --prop cols=3
officecli set "$FILE" /slide[3]/table[1]/row[1]/cell[1] --prop text='Metric'
officecli set "$FILE" /slide[3]/table[1] --prop style='Medium Style 2'
```

## Chart

```bash
officecli add "$FILE" /slide[4] --type chart --prop kind=bar --prop dataRange='Sheet1!A1:B5' --prop title='Weekly Revenue'
officecli set "$FILE" /slide[4]/chart[1] --prop title='Revenue by Day'
```

- Chart trong PPTX thuong phu thuoc bang du lieu nen; xac nhan data binding sau khi copy hoac reorder slide.

## Group, connector, 3D model, zoom

```bash
officecli add "$FILE" /slide[5] --type group
officecli add "$FILE" /slide[5] --type connector --prop from='/slide[5]/shape[1]' --prop to='/slide[5]/shape[2]'
officecli add "$FILE" /slide[6] --type model3d --prop src='demo.glb'
officecli add "$FILE" /slide[1] --type zoom --prop target='/slide[6]'
```

- Cac doi tuong nang cao nay can help-first truoc khi doan prop chi tiet.