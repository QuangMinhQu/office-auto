# OfficeCLI DOCX: Batch Và Resident Mode

Dùng file này khi phải chạy nhiều lệnh liên tiếp.

## Quy tắc resident mode
- `officecli open "$FILE"`
- Giữ mọi lệnh tiếp theo trong cùng terminal.
- `officecli close "$FILE"` trước khi validate hoặc bàn giao.

## Quy tắc batch
- Chỉ batch các thao tác cùng khu vực và cùng ngữ cảnh.
- Không batch quá lớn nếu chưa kiểm tra được lỗi trung gian.
- Sau thao tác cấu trúc, luôn đọc lại một lần bằng `get` hoặc `view`.