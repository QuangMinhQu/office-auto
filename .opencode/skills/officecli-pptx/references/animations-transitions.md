# OfficeCLI PPTX: Animations Va Transitions

Dung file nay khi task co dong den chuyen canh hoac hieu ung.

## Animations

```bash
officecli add "$FILE" /slide[2] --type animation --prop target='/slide[2]/shape[1]' --prop effect=fade
officecli set "$FILE" /slide[2]/animation[1] --prop trigger='on-click'
officecli set "$FILE" /slide[2]/animation[1] --prop duration=0.5
officecli set "$FILE" /slide[2]/animation[1] --prop delay=0.2
```

## Timing tree
- Animation phuc tap thuong duoc mo hinh bang timing tree va target id cua shape.
- Neu deck da co animation san trong template, profile truoc khi chen them hieu ung moi.

## Target correlation
- Xac minh hieu ung dang tro toi shape dung id sau khi duplicate, move hoac remap slide.

## Slide transitions

```bash
officecli set "$FILE" /slide[2] --prop transition=fade
officecli set "$FILE" /slide[3] --prop transition=push
officecli set "$FILE" /slide[4] --prop transition=morph
```

- Transition nen nhat quan voi narrative; khong chen hieu ung chi vi co the.