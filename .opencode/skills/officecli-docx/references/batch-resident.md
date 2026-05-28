# OfficeCLI DOCX: Batch, Resident Và Live Preview

Dùng file này khi phải chạy nhiều lệnh liên tiếp.

## Quy tắc resident mode
- `officecli open "$FILE"`
- Giữ mọi lệnh mutation tiếp theo trong cùng terminal hoặc cùng execution flow cho đến khi xong phase build.
- `officecli save "$FILE"` khi cần flush giữa chừng.
- `officecli close "$FILE"` trước khi validate hoặc bàn giao.

## Quy tắc batch
- Gom mutation vào một JSON array duy nhất rồi chạy `officecli batch "$FILE" --input batch.json`.
- Trong repo này có wrapper: `scripts/run_officecli_batch.py` để chạy batch và ghi `batch_report.json`.
- Batch phù hợp khi command list đã deterministic; resident phù hợp khi cần đọc-kiểm tra-gắn thêm theo vòng lặp.

## Live preview / watch

```bash
officecli watch "$FILE"
officecli watch "$FILE" mark "/body/p[1]"
officecli watch "$FILE" goto "/body/p[20]"
officecli unwatch "$FILE"
```

## Quy tắc
- Sau thao tác cấu trúc, luôn đọc lại một lần bằng `get`, `view` hoặc `query`.
- Không giữ watch server chạy vô hạn nếu đã xong debug.