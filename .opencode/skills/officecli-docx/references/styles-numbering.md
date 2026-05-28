# OfficeCLI DOCX: Styles Và Numbering

Dùng file này khi cần giữ format template cho heading, body, list và references.

## Mục tiêu
- Xác định style nào map cho H1, H2, H3, body.
- Xác định tài liệu có đánh số heading bằng numbering hay chỉ bằng style.
- Tách rõ style inheritance với numbering instance.

## Quan sát tối thiểu

```bash
officecli get "$FILE" /styles --depth 2
officecli get "$FILE" /numbering --depth 4
officecli query "$FILE" 'style'
officecli query "$FILE" 'paragraph[numId>0]'
officecli get "$FILE" "/body/p[1]" --json
officecli help docx style --json
officecli help docx numbering --json
```

## Quy tắc
- Nếu template dùng numbered heading, phải profile `numId` và `ilvl` từ paragraph thực tế hoặc numbering part trước khi build.
- Không giả định `Heading1` luôn là level 1 có numbering.
- `styleId` quyết định format; `numId`/`ilvl` quyết định numbering binding.
- Với rebuild, cần profile style map và numbering map trước khi build.