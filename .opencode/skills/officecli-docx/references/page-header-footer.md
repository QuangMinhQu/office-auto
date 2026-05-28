# OfficeCLI DOCX: Page Setup, Header, Footer

Dùng file này khi cần giữ hình thức tài liệu từ template.

## Mục tiêu
- Giữ margins, section, page setup.
- Không làm vỡ header/footer khi rebuild hoặc append.
- Kiểm được section count trước và sau mutation.

## Kiểm tra nhanh

```bash
officecli query "$FILE" 'section'
officecli query "$FILE" 'header'
officecli query "$FILE" 'footer'
officecli view "$FILE" stats
officecli get "$FILE" "/header[1]" --depth 2
officecli get "$FILE" "/footer[1]" --depth 3
```

## Quy tắc
- Header/footer là scaffold bắt buộc, không phải chi tiết trang trí có thể bỏ qua.
- Nếu template có first-page header/footer riêng, phải giữ đúng loại section tương ứng.
- Khi close resident xong, dùng `view stats` hoặc `query header/footer` để xác nhận output chưa mất part.