# Office Auto — Agent Instructions

## Mục tiêu
Dự án này tự động tạo file Word (.docx) từ nội dung Markdown theo đúng định dạng template.

## Khi người dùng yêu cầu tạo/xuất file Word:
1. Load skill `docx-from-template` (quy trình 4 giai đoạn)
2. Load skill `officecli-docx` (command syntax)
3. Template mặc định: `.opencode/format_template.docx`
4. Nội dung mặc định: file `.md` được chỉ định (ví dụ `chuong_2.md`)
5. Output mặc định: `report.docx` trong thư mục gốc

## Trigger phrases
- "tạo file word", "xuất docx", "generate report", "tạo báo cáo", "viết word"