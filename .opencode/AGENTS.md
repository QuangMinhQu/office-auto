# Office Auto — Agent Instructions

## Mục tiêu
Dự án này tự động tạo file Word (.docx) từ nội dung Markdown theo đúng định dạng template.

## Khi người dùng yêu cầu tạo/xuất file Word:
1. Load skill `docx-from-template` trước để lấy workflow điều phối ngắn, state machine, checkpoint schema và invariant preserve scaffold.
2. Chỉ load skill `officecli-docx` khi cần tra cứu cú pháp OfficeCLI, schema element hoặc prop name cụ thể.
3. Load skill `docx-qa` trước khi bàn giao file, hoặc sớm hơn nếu task đụng TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer.
4. Nếu task là `preserve-template-scaffold`, `replace-main-content-range` hoặc có nguồn Markdown, phải load `md-to-docx-pipeline` trước khi build.
5. Template mặc định: `format_template.docx`
6. Nội dung mặc định: file `.md` được chỉ định, ví dụ `chuong_2.md`
7. Output mặc định: `report.docx` trong thư mục gốc

## Routing cho Open Models

- Ưu tiên skill ngắn, đúng vai trò. Không load toàn bộ command encyclopedia nếu chưa cần syntax cụ thể.
- `docx-from-template` = orchestrator.
- `officecli-docx` = command reference.
- `md-to-docx-pipeline` = pipeline script/artifact để parse, profile, plan, build, QA ngoài context.
- `docx-qa` = delivery gate cho package QA, structural QA, range QA và semantic QA.
- `docx-from-template` phải ưu tiên các mode: `preserve-template-scaffold`, `replace-main-content-range`, `fill-declared-placeholders`, `append-structured-section`.
- `full-regenerate-from-schema` chỉ được dùng khi người dùng chấp nhận tái tạo gần như toàn bộ tài liệu từ đầu.
- Với `mode=append-structured-section`, nếu `target_file` chưa tồn tại thì phải sao chép `template_file` sang `target_file` trước khi chèn nội dung mới.
- Với `mode=preserve-template-scaffold`, không được đi theo flow xóa toàn bộ body. Tài liệu đích phải được chứng minh là vẫn giữ scaffold và chỉ thay bounded range của nội dung chính.
- Nếu task cũ dùng `rebuild-from-template-format`, phải normalize ngay sang `preserve-template-scaffold` rồi chạy theo invariant mới.

## Hard Gate cho mode preserve-template-scaffold

- Không được finalize chỉ vì `validate pass`.
- Phải có artifact tối thiểu: `content_ast.json`, `content_outline.json`, `template_profile.json`, `plan.json`, `build_report.json`, `qa_report.json`.
- Phải có bằng chứng rằng scaffold quan trọng của template vẫn tồn tại, tối thiểu gồm:
	- header/footer còn tồn tại và không bị giảm bất thường
	- section break hoặc section settings vẫn còn
	- nếu template có TOC hoặc danh mục hình/bảng thì các field tương ứng vẫn còn trong file đích
	- với TOC, hoặc result trong package đã có hyperlink/bookmark hợp lệ, hoặc file buộc Word refresh on open bằng `updateFields` và dirty field
- Phải có bằng chứng semantic rằng vùng nội dung chính đã bị thay thế, tối thiểu gồm:
	- outline của file kết quả khớp outline nguồn theo thứ tự
	- không còn heading/chương cũ của template bên trong vùng đã thay
	- không xuất hiện duplicate kiểu `CHƯƠNG 1. CHƯƠNG 1` hoặc `4.1. 1.1.` trong bản trích text
	- `replace_ranges` trong `plan.json` ở trạng thái `resolved`
- Nếu một trong các điều trên chưa được chứng minh, trạng thái phải là `failed` hoặc `needs-repair`, không được là `ready`.

## Khi thêm nội dung mới vào văn bản

- Không chỉ chèn section nội dung mới rồi dừng lại.
- Không được làm mất các phần hình thức mà Markdown nội dung chương không trực tiếp thay thế, tối thiểu gồm: trang bìa hoặc phần mở đầu, mục lục, danh mục hình, danh mục bảng, header/footer, page number và các section dẫn hướng tương tự; nếu các phần này bị ảnh hưởng bởi nội dung mới thì phải cập nhật hoặc rebuild chúng, không được xóa hoặc bỏ trống.
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