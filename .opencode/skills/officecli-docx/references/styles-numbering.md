# OfficeCLI DOCX: Styles Và Numbering

Dùng file này khi cần giữ format template cho heading và body.

## Mục tiêu
- Xác định style nào map cho H1, H2, H3, body.
- Xác định tài liệu có đánh số heading bằng numbering hay chỉ bằng style.

## Quan sát tối thiểu

```bash
officecli get "$FILE" /styles --depth 2
officecli get "$FILE" /numbering --depth 2
officecli query "$FILE" 'paragraph[numId>0]'
officecli get "$FILE" "/body/p[1]" --json
```

## Quy tắc
- Nếu template dùng numbered heading, phải giữ đúng `numId` và `ilvl`.
- Không giả định `Heading1` luôn là level 1 có numbering.
- Với rebuild, cần profile style map và numbering map trước khi build.