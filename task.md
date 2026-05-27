# Task: Tạo lại report.docx bằng nội dung đầy đủ từ chuong_2.md

Mục tiêu là sinh file `report.docx` sao cho file kết quả:

1. Dùng `format_template.docx` chỉ như nguồn định dạng và bố cục trình bày.
2. Thay toàn bộ nội dung thân bài hiện có bằng toàn bộ nội dung trong `chuong_2.md`.
3. Không giữ lại nội dung các chương hiện đang có sẵn trong template, trừ các thành phần định dạng cần kế thừa như style, numbering, header/footer, margins và page setup.

## Chế độ thực hiện

- `mode`: rebuild-from-template-format
- `template_file`: `format_template.docx`
- `target_file`: `report.docx`
- `source_file`: `chuong_2.md`
- `source_scope`: full-document

## Yêu cầu chi tiết

- Khởi tạo `report.docx` dựa trên `format_template.docx` để kế thừa định dạng tài liệu.
- Sau khi kế thừa format, phải thay toàn bộ phần nội dung chính của tài liệu bằng nội dung trong `chuong_2.md`.
- Không cần giữ lại nội dung chương, mục hay đoạn văn gốc đang có trong template.
- Nội dung được lấy từ `chuong_2.md` là toàn bộ file hiện tại, bao gồm cả Chương 1, phần ứng dụng AI và mục `TÀI LIỆU THAM KHẢO` ở cuối nếu có trong markdown.
- Cấu trúc heading trong file kết quả phải bám theo heading trong markdown nguồn.
- Phần nội dung mới phải khớp format của template: heading, font, cỡ chữ, khoảng cách, numbering, header/footer, căn lề và page settings.
- Nếu template dùng numbered headings, phải áp numbering tương ứng cho toàn bộ heading được sinh từ markdown.
- Không để sót placeholder, đoạn văn mẫu hoặc nội dung chương cũ từ template trong file kết quả.

## Kết quả mong muốn

- File đầu ra là `report.docx`.
- `report.docx` phản ánh đầy đủ nội dung hiện có trong `chuong_2.md`.
- Template chỉ còn vai trò cung cấp định dạng, không còn giữ nội dung cũ.
- File cuối phải validate sạch và không còn placeholder thừa.