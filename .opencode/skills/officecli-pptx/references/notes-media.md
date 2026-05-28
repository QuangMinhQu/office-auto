# OfficeCLI PPTX: Notes Va Media

Dung file nay khi slide can notes, audio, video hoac hyperlink.

## Slide notes

```bash
officecli set "$FILE" /slide[2]/notes --prop text='Speaker note for week 1 summary'
```

- Neu template da co notes pages, can coi do la mot phan scaffold can duoc ton trong.

## Audio va video

```bash
officecli add "$FILE" /slide[3] --type audio --prop src='intro.mp3'
officecli add "$FILE" /slide[4] --type video --prop src='demo.mp4'
officecli set "$FILE" /slide[4]/video[1] --prop autoplay=true
officecli set "$FILE" /slide[4]/video[1] --prop loop=false
```

## Media playback va hyperlinks

```bash
officecli set "$FILE" /slide[3]/audio[1] --prop volume=0.8
officecli set "$FILE" '/slide[2]/shape[1]' --prop hyperlink='https://example.com'
officecli set "$FILE" '/slide[2]/shape[2]' --prop hyperlink='#/slide[5]'
```

- Sau khi chen media, xac minh lai relationship va text extract de chac khong co residue placeholder.