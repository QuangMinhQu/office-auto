# Office Auto — Agent Instructions

## Mục tiêu
Dự án này tự động thao tác tài liệu Office theo hướng native OfficeCLI, ưu tiên giữ scaffold của template thay vì sửa OOXML thủ công.

## Bootstrap môi trường bắt buộc
- Linux/macOS: `source ~/.bashrc` nếu cần, rồi chạy `command -v officecli` và `officecli --version` trước mọi task Office.
- Windows: nếu `officecli` vừa được cài mà terminal chưa nhận lệnh, prepend PATH tạm trong đúng session hiện tại rồi kiểm lại version:

```powershell
$env:PATH = "$env:LOCALAPPDATA\OfficeCLI;$env:PATH"
officecli --version
```

- Chỉ khi `officecli --version` vẫn thất bại mới tiếp tục chẩn đoán binary hoặc PATH.
- Nếu OfficeCLI MCP đã được đăng ký cho agent hiện tại, ưu tiên MCP tool calls thay vì shell subprocess.

## Routing theo intent và extension

### Khi người dùng yêu cầu tạo/xuất file Word
1. Load `docx-from-template` trước.
2. Chỉ load `officecli-docx` khi cần cú pháp OfficeCLI hoặc schema element cụ thể.
3. Load `md-to-docx-pipeline` cho mọi task `preserve-template-scaffold`, `replace-main-content-range` hoặc task Markdown-to-DOCX.
4. Load `docx-qa` trước khi bàn giao hoặc khi task đụng TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer.

### Khi task nhắm vào bảng tính hoặc trình chiếu
- File `.xlsx` hoặc intent kiểu dữ liệu/bảng tính: load `officecli-xlsx`.
- File `.pptx` hoặc intent kiểu slide/trình chiếu: load `officecli-pptx`.
- Task cài MCP, đăng ký agent, cài base skill OfficeCLI: load `officecli-mcp`.

## Routing cốt lõi cho DOCX
- Ưu tiên skill ngắn, đúng vai trò. Không load full command encyclopedia nếu chưa cần syntax cụ thể.
- `docx-from-template` = orchestrator.
- `officecli-docx` = command reference.
- `md-to-docx-pipeline` = pipeline script/artifact để parse, profile, plan, build, QA ngoài context.
- `docx-qa` = delivery gate cho package QA, structural QA, range QA và semantic QA.
- Các mode ưu tiên: `preserve-template-scaffold`, `replace-main-content-range`, `fill-declared-placeholders`, `append-structured-section`.
- `full-regenerate-from-schema` chỉ dùng khi người dùng chấp nhận tái tạo gần như toàn bộ tài liệu.
- Nếu gặp mode cũ `rebuild-from-template-format`, phải normalize sang `preserve-template-scaffold`.

## Discipline cho mutation
- Với mọi mutation nhiều bước, phải chọn một trong hai đường chạy rõ ràng:
	- resident mode: `officecli open` -> chuỗi `add/set/remove/move` -> `officecli save` -> `officecli close`
	- batch mode: gom mutation vào một JSON array duy nhất rồi chạy `officecli batch`
- Không được mở/đóng resident nhiều lần trong cùng một phase build nếu không có lý do kỹ thuật rõ ràng.
- Trước mỗi lệnh `add` hoặc `set`, phải tra `officecli help docx <element> --json` nếu chưa chắc schema prop.
- Sau khi `close`, phải chạy `officecli view <file> stats --json` hoặc `officecli validate <file> --json` như integrity gate tối thiểu.

## Hard Gate cho preserve-template-scaffold
- Không được finalize chỉ vì `validate pass`.
- Phải có artifact tối thiểu: `preflight.json`, `content_ast.json`, `content_outline.json`, `template_profile.json`, `plan.json`, `build_report.json`, `qa_report.json`.
- Phải có bằng chứng scaffold còn nguyên, tối thiểu gồm:
	- header/footer còn tồn tại và không bị giảm bất thường
	- section break hoặc section settings vẫn còn
	- nếu template có TOC hoặc danh mục hình/bảng thì field tương ứng vẫn còn trong file đích
	- với TOC, hoặc package hiện tại còn hyperlink/bookmark hợp lệ, hoặc build report ghi rõ refresh strategy native như `rewrite-toc-fields-on-open`
- Phải có bằng chứng semantic rằng vùng nội dung chính đã bị thay thế:
	- outline file kết quả khớp outline nguồn theo thứ tự
	- không còn heading/chương cũ của template trong vùng đã thay
	- không có duplicate kiểu `CHƯƠNG 1. CHƯƠNG 1` hoặc `4.1. 1.1.`
	- `replace_ranges` trong `plan.json` ở trạng thái `resolved`
- Nếu một trong các điều trên chưa được chứng minh, trạng thái phải là `failed` hoặc `needs-repair`, không được là `ready`.

## Guardrail cho L3
- Chỉ được dùng `raw`, `raw-set` hoặc `add-part` khi L1/L2 không hỗ trợ.
- Mọi fallback L3 phải được giải trình trong `build_report.json`, tối thiểu gồm:
	- `l3_fallback.reason`
	- `l3_fallback.command`
	- `l3_fallback.target_part`
- Nếu không có giải trình, coi như build vi phạm contract.

## Khi thêm nội dung mới vào văn bản
- Không chỉ chèn section nội dung mới rồi dừng lại.
- Không được làm mất các phần hình thức mà Markdown không trực tiếp thay thế, tối thiểu gồm: trang bìa hoặc phần mở đầu, TOC, danh mục hình, danh mục bảng, header/footer, page number và section dẫn hướng tương tự.
- Phải rà toàn bộ các phần phụ thuộc cấu trúc và cập nhật nếu bị ảnh hưởng: TOC, references, appendix, danh mục hình, danh mục bảng, cross-reference nội bộ, header/footer, page fields.
- Nếu tài liệu có `KẾT LUẬN`, `TÀI LIỆU THAM KHẢO`, `PHỤ LỤC` hoặc các section cuối tương tự, phải xác nhận vị trí chèn không làm sai thứ tự.

## Trigger phrases
- "tạo file word", "xuất docx", "generate report", "tạo báo cáo", "viết word"
- "tạo file excel", "xuất dữ liệu xlsx", "bảng tính", "sheet", "formula"
- "render slide powerpoint", "tạo slide", "xuất pptx", "presentation", "deck"
- "cài officecli mcp", "đăng ký officecli với copilot", "install officecli skill"