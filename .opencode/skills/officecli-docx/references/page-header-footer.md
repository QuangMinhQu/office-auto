# OfficeCLI DOCX: Page Setup, Header, Footer

Dùng file này khi cần giữ hình thức tài liệu từ template.

## Mục tiêu
- Giữ margins, section, page setup.
- Không làm vỡ header/footer khi rebuild hoặc append.

## Kiểm tra nhanh

```bash
officecli get "$FILE" / --depth 2
officecli get "$FILE" "/header[1]" --depth 2
officecli get "$FILE" "/footer[1]" --depth 3
```

## Quy tắc
- Header/footer phải được xem là phần phụ thuộc cấu trúc, không phải chi tiết trang trí có thể bỏ qua.
- Nếu template có first-page footer/header riêng, phải giữ đúng loại section tương ứng.