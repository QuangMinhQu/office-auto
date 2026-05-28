# OfficeCLI PPTX: Core Ops

```bash
officecli get "$FILE" / --depth 2
officecli query "$FILE" 'slide'
officecli add "$FILE" / --type slide
officecli add "$FILE" /slide[1] --type shape --prop kind=textbox --prop text='Title'
officecli add "$FILE" /slide[1] --type picture --prop src=chart.png
officecli move "$FILE" /slide[3] --before /slide[2]
```

## Gợi ý
- Dùng `query 'slide'` và `get /slide[N] --depth 2` để profile layout trước khi add shape.
- Không phá slide order hoặc layout binding chỉ vì cần chèn một textbox.
- Với animation/master/layout edge-case, kiểm `help pptx` trước khi hạ xuống L3.
