# OfficeCLI PPTX: Core Quick Ops

```bash
officecli get "$FILE" / --depth 2
officecli query "$FILE" 'slide'
officecli add "$FILE" / --type slide
officecli add "$FILE" /slide[1] --type shape --prop kind=textbox --prop text='Title'
officecli add "$FILE" /slide[1] --type picture --prop src=chart.png
officecli move "$FILE" /slide[3] --before /slide[2]
```

## Dung file nay khi nao
- Can mot cheat sheet rat ngan de orient nhanh truoc khi mo file tham chieu chi tiet.
- Khong dung file nay thay cho `SKILL.md` hoac cac reference chuyen sau.

## Mo tiep file nao
- `view-query.md`: profile slide tree, shape selectors, placeholder resolution.
- `elements.md`: slide, shape, picture, table, chart, textbox, group, connector.
- `text-formatting.md`: paragraph, run, bullet, rich text, placeholder text.
- `visual-properties.md`: fill, outline, effects, transform, z-order.
- `layouts-masters.md`: master, layout, theme, placeholder inheritance, slide size.
- `animations-transitions.md`: animation timing, target correlation, transitions.
- `notes-media.md`: speaker notes, audio/video, playback, hyperlinks.
- `batch-resident.md`: resident mode, batch mode, live preview, watch.
- `raw-l3.md`: XML fallback co guardrail.
