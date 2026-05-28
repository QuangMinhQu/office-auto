# OfficeCLI PPTX: Layouts Va Masters

Dung file nay khi task can giu scaffold cua template thay vi chi lay theme.

## Slide layouts

```bash
officecli query "$FILE" 'layout'
officecli get "$FILE" /slide[2] --depth 2
officecli set "$FILE" /slide[3] --prop layout='Title and Content'
```

- Layout quyet dinh placeholder regions, content slots va mot phan visual binding cua slide.

## Slide masters va theme
- Master giu global template settings, color palette, font theme va placeholder inheritance.
- Truoc khi them slide moi, xac nhan layout thuoc cung scaffold master voi deck hien co.

## Placeholder types va inheritance
- Placeholder thong dung: `title`, `body`, `subtitle`, `footer`, `date`, `slide number`.
- Luong ke thua thuong la `Layout -> Master -> Slide`.
- Neu slide khong hien thi text nhu mong doi, kiem tra binding cua placeholder thay vi them shape moi ngay lap tuc.

## Presentation properties

```bash
officecli get "$FILE" /presentation --depth 1
officecli set "$FILE" /presentation --prop slideSize='16:9'
```

- Slide size, background va theme la scaffold can phai bao toan trong mode preserve-template-scaffold.