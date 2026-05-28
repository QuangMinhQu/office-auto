# OfficeCLI DOCX: Fields, TOC Và References

Dùng file này khi task đụng TOC, references, caption, cross-reference hoặc page field.

## Lệnh tham khảo

```bash
officecli add "$FILE" /body --type toc --prop levels="1-3" --prop hyperlinks=true --index 0
officecli set "$FILE" /toc[1] --prop levels="1-3" --prop hyperlinks=true --prop pageNumbers=true
officecli query "$FILE" 'toc'
officecli query "$FILE" 'field'
officecli query "$FILE" 'fieldchar'
officecli get "$FILE" "/footer[1]" --depth 3
officecli view "$FILE" issues
```

## Quy tắc
- Không coi `validate pass` là đủ nếu TOC/references còn stale.
- Nếu cần refresh-on-open cho TOC, ưu tiên rewrite `toc` qua L2 trước khi nghĩ tới `raw-set`.
- Khi người nhận có thể không refresh field, cần đánh giá rõ TOC đang là render sẵn hay chỉ là field sẽ refresh sau.
- Không tự compose field XML nếu OfficeCLI đã có prop tương ứng.