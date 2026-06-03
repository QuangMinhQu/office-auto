# Office Auto Bootstrap

## Mục tiêu file này
File này chỉ là bootstrap pointer cho orchestration.
Không được coi đây là session state và không được sử dụng artifact cứ làm context mặc định. 

## Bắt đầu mỗi session
1. Đọc `.opencode/memory/project.md` để nạp conventions của repo.
2. Chỉ đọc `.opencode/memory/task_current.md` khi cần resume session đang dở hoặc khi người dùng nói rõ run hiện tại.
3. Nếu đây là task mới, khởi tạo hoặc viết lại `task_current.md` theo input thực tế của session hiện tại trước khi gọi pipeline.
4. Chỉ đọc `task.md` khi người dùng đang muốn đi theo workflow build DOCX chuẩn theo repo.

## Các Quy Định Về Vận Hành (Orchestration Contract)

5. **Không đọc** dữ liệu từ `manual-run/`, `.manual-run/`, hoặc các tệp tin artifact trong `.office-auto/state/<run_id>/` nếu chưa xác định chính xác `run_id` cần sử dụng.

### Quy định về Điều phối (Orchestration Contract)

* **Agent chính:** `orchestrator`.
* **Quy định gọi công cụ:** Không gọi trực tiếp các công cụ của OfficeCLI MCP; chỉ được phép sử dụng OfficeCLI thông qua bash CLI hoặc các trình bao bọc công cụ tùy chỉnh (custom tools wrappers).
* **Tính nhất quán của phiên làm việc:** Mỗi phiên chỉ được chọn một bề mặt thực thi (execution surface) nhất quán:
* `docx_pipeline_inspectTemplate` để đọc raw inspection của template.
* `docx_pipeline_validateExecutionOps` để kiểm tra `execution_ops.json` trước khi build.
* `docx_pipeline_applyExecutionOps` để thực thi mechanical build từ `execution_ops.json`.
* `docx_pipeline_readResult` để đọc lại output DOCX cho bước verify.


* **Tính đồng bộ:** Không trộn lẫn việc sử dụng công cụ tùy chỉnh với các tập lệnh bash ad-hoc trong cùng một giai đoạn, trừ khi thực hiện chẩn đoán có chủ đích và ghi rõ lý do.

### Cổng kiểm soát bắt buộc (Hard Gate)

* **Điều kiện hoàn thành:** Không được chốt trạng thái "hoàn thành" (complete) nếu chưa có `build_report.json` ở trạng thái hoàn tất và `result_readback.json` đủ để tự verify output.
* **Xử lý lỗi:** Nếu một giai đoạn thất bại, `orchestrator` phải tự sửa `execution_ops.json` hoặc input context tương ứng rồi chạy lại primitive tool thích hợp.
* **Ưu tiên cấu trúc:** Luôn ưu tiên chế độ `preserve-template-scaffold` khi tạo báo cáo DOCX.
* **Phân quyền:** `orchestrator` tự thực hiện reasoning; tools chỉ được dùng cho inspect/apply/read/validate mang tính cơ học.