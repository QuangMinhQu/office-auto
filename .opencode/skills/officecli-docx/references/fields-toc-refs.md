# OfficeCLI DOCX: Fields, TOC Và References

Dùng file này khi task đụng TOC, references, caption, cross-reference.

## Lệnh tham khảo

```bash
officecli add "$FILE" /body --type toc --prop levels="1-3" --prop hyperlinks=true --index 0
officecli get "$FILE" "/footer[1]" --depth 3
officecli query "$FILE" 'field'
officecli view "$FILE" issues
```

## Quy tắc
- Không coi `validate pass` là đủ nếu TOC/references còn stale.
- Khi người nhận có thể không refresh field, cần đánh giá rõ trạng thái TOC trước khi giao file.
- Không tự compose field XML nếu OfficeCLI đã có prop tương ứng.