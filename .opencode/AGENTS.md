# Office Auto — Agent Instructions

## Mục tiêu
Dự án này tự động tạo file Word (.docx) từ nội dung Markdown theo đúng định dạng template.

## Khi người dùng yêu cầu tạo/xuất file Word:
1. Load skill `docx-from-template` trước để lấy workflow ngắn, state machine, checkpoint schema, và invariant append.
2. Load skill `officecli-docx` chỉ để tra cứu command syntax hoặc element schema khi thực sự cần.
3. Load skill `docx-qa` trước khi bàn giao file, hoặc sớm hơn nếu task đụng TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer.
4. Template mặc định: `format_template.docx`
5. Nội dung mặc định: file `.md` được chỉ định (ví dụ `chuong_2.md`)
6. Output mặc định: `report.docx` trong thư mục gốc

## Routing cho Open Models

- Ưu tiên skill ngắn, đúng vai trò. Không load toàn bộ command encyclopedia nếu chưa cần syntax cụ thể.
- `docx-from-template` = orchestrator.
- `officecli-docx` = command reference.
- `docx-qa` = delivery gate cho TOC/references/appendix/cross-reference.
- Với `mode=append`, nếu `target_file` chưa tồn tại thì phải sao chép `template_file` sang `target_file` trước khi chèn nội dung mới.

## Khi thêm nội dung mới vào văn bản

- Không chỉ chèn section nội dung mới rồi dừng lại.
- Không được làm mất các phần hình thức mà Markdown nội dung chương không trực tiếp thay thế, tối thiểu gồm: tên đề tài/trang tiêu đề, mục lục, danh mục hình, danh mục bảng, header/footer, page number và các section dẫn hướng tương tự; nếu các phần này bị ảnh hưởng bởi nội dung mới thì phải cập nhật hoặc rebuild chúng, không được xóa hoặc bỏ trống.
- Phải rà toàn bộ các phần phụ thuộc vào cấu trúc tài liệu và cập nhật chúng nếu bị ảnh hưởng, tối thiểu gồm: mục lục/TOC, tài liệu tham khảo, phụ lục/appendix, danh mục hình, danh mục bảng, cross-reference nội bộ, header/footer, page number, và các heading điều hướng ở cuối tài liệu.
- Nếu tài liệu có `KẾT LUẬN`, `TÀI LIỆU THAM KHẢO`, `PHỤ LỤC`, hoặc các section cuối tương tự, phải xác nhận vị trí chèn không làm sai thứ tự và không đẩy các phần này vào trạng thái lỗi thời.
- Trước khi bàn giao, phải kiểm tra xem việc thêm nội dung mới có làm các field hoặc section phụ này cần refresh, rebuild hoặc chỉnh tay hay không.

## OfficeCLI trên Windows

- Nếu `officecli` vừa được cài trong chính terminal hiện tại mà lệnh vẫn báo `not recognized`, KHÔNG giả định cài đặt thất bại.
- Trước khi chạy các lệnh `officecli`, prepend PATH tạm trong chính session đó:

```powershell
$env:PATH = "$env:LOCALAPPDATA\OfficeCLI;$env:PATH"
officecli --version
```

- Chỉ khi lệnh trên vẫn thất bại mới tiếp tục kiểm tra file nhị phân tại `%LOCALAPPDATA%\OfficeCLI\officecli.exe`.
- Khi đã `officecli open <file>`, phải tiếp tục mọi lệnh `officecli` trong cùng terminal cho đến khi `officecli close <file>`.

## Trigger phrases
- "tạo file word", "xuất docx", "generate report", "tạo báo cáo", "viết word"