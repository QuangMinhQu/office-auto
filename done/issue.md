Chào bạn, dưới đây là toàn bộ nội dung phân tích và Checklist Native hóa tài liệu `.opencode` với OfficeCLI được định dạng bằng Markdown chuẩn, scannable và sẵn sàng để bạn copy-paste vào repo `QuangMinhQu/office-auto`.

---

# Checklist Native hóa `.opencode` với OfficeCLI

**Ngày:** 28/05/2026 | **Repo:** `QuangMinhQu/office-auto`

---

## 1. Tổng quan kiến trúc OfficeCLI (3-Layer Command Architecture)

OfficeCLI cung cấp giải pháp thao tác tài liệu Office thông qua 3 tầng xử lý, tối ưu hóa cho AI Agent:

* **L1 (Read & Inspect):** `view` (outline/stats/issues/text/annotated), `get --depth`, `validate`, `query`.
* **L2 (DOM Operations):** `add --type`, `set --prop`, `move`, `remove`.
* **L3 (Raw XML):** `raw` (XPath), `raw-set`, `add-part`.
* **Lifecycle & Session:** `create`, `open`, `close`.
* **Batch/Live Processing:** `batch` (JSON array), `watch`, `unwatch`.
* **AI Integration:** MCP server (stdio JSON-RPC 2.0), `SKILL.md`, Resident Mode, Help System 3-layer.
* **Format định dạng:** `.docx`, `.xlsx`, `.pptx`.

---

## 2. Phân tích hiện trạng tài liệu hệ thống

### 2.1 Những gì `.opencode` đã làm tốt

* **`AGENTS.md`:** Đã cấu hình routing logic, trigger phrases, hard gate cho `preserve-template-scaffold` và setup biến môi trường `PATH` trên Windows.
* **`officecli-docx/SKILL.md`:** Thiết lập tốt tư duy `help-first`, resident mode discipline và quy tắc shell quoting.
* **Hệ thống References:** Đã có 6 file core references bao gồm `view-query`, `elements`, `styles-numbering`, `fields-toc-refs`, `page-header-footer`, `batch-resident`.
* **Cấu trúc Module:** Phân tách rõ ràng giữa Orchestrator skill (`docx-from-template`), QA gate (`docx-qa`) và Pipeline (`md-to-docx-pipeline`).

### 2.2 Vấn đề nghiêm trọng cần khắc phục

> ⚠️ **Core Issue:** Toàn bộ 5 scripts Python trong thư mục `md-to-docx-pipeline/scripts/` (`build_docx.py`, `profile_template.py`, `qa_docx.py`,...) hiện đang **bypass OfficeCLI hoàn toàn**. Thay vào đó, chúng sử dụng trực tiếp các thư viện cấp thấp: `xml.etree.ElementTree` + `zipfile`.
> **Hệ lụy:** Gây trùng lặp logic, phá vỡ kiến trúc thiết kế của Agent, dễ sinh lỗi cấu trúc OpenXML và làm mất đi toàn bộ lợi thế tối ưu context/hiệu năng của OfficeCLI.

---

## 3. CHECKLIST NATIVE HÓA `.OPENCODE`

> **Legend:** `[ ]` Chưa làm | `[~]` Một phần | `[x]` Đã làm

### 🔴 NHÓM 1: ƯU TIÊN CAO NHẤT (Refactor Pipeline & Resident Mode)

#### A. Thay thế `xml.etree` + `zipfile` bằng OfficeCLI Commands

* [ ] **A1.** `profile_template.py`: Thay thế logic đọc XML thủ công bằng cụm lệnh native: `officecli view docx --mode outline` + `officecli get docx /styles` + `officecli get docx /sections`.
* [ ] **A2.** `build_docx.py`: Loại bỏ hoàn toàn `zipfile` và `ET.parse`. Chuyển dịch sang mô hình Resident Mode workflow tuần tự: `officecli open` ➡️ `officecli set/add/remove` ➡️ `officecli close`.
* [ ] **A3.** `qa_docx.py`: Thay thế bộ kiểm tra chất lượng (validation) bằng lệnh native: `officecli validate docx` + `officecli view docx --mode issues`.
* [ ] **A4.** Trích xuất định dạng Style: Chuyển sang dùng `officecli get docx /styles` kết hợp tham chiếu `officecli help docx style`.
* [ ] **A5.** Trích xuất cấu trúc Numbering: Chuyển sang dùng `officecli get docx /numbering` kết hợp tham chiếu `officecli help docx numbering`.
* [ ] **A6.** Range Replace (Tìm và xóa cụm paragraph): Thay thế logic loop XML bằng cặp lệnh `officecli query docx` + `officecli remove docx <path>`.
* [ ] **A7.** Chèn phần tử mới (Paragraph/Run/Image): Native hóa bằng cụm lệnh `officecli add docx --type paragraph/run/image` + `officecli set docx <path> --prop`.
* [ ] **A8.** Kiểm tra Header/Footer trong QA: Chuyển sang sử dụng `officecli get docx /header` + `officecli get docx /footer` + `officecli view docx --mode stats`.

#### B. Tối ưu hóa Resident Mode và Batch Mode

* [~] **B1.** `build_report.py`: Đang gọi các script Python tuần tự ➡️ Cần refactor để quản lý vòng đời session đóng/mở tập trung thay vì để mỗi script subprocess tự mở file riêng lẻ.
* [ ] **B2.** Xây dựng wrapper script chạy Batch Mode: Gom toàn bộ chuỗi mutations phức tạp của pipeline vào **1 file JSON array duy nhất** để truyền qua `officecli batch`, giảm thiểu overhead I/O.
* [ ] **B3.** Tối ưu hóa Resident Mode trong `build_docx.py`: Đảm bảo thực hiện chuỗi lệnh `set`/`add`/`remove` trong cùng một terminal session đang `open`.
* [ ] **B4.** Cập nhật `AGENTS.md`: Bổ sung điều khoản cứng: *"Đối với mọi tác vụ multi-step mutation, bắt buộc phải khởi tạo Resident Mode trước, chỉ đóng session sau khi hoàn tất toàn bộ mutation"*.

---

### 🟡 NHÓM 2: ƯU TIÊN TRUNG BÌNH (Mở rộng L1/L2/L3 & Rule Systems)

#### C. Tận dụng toàn diện các tính năng L1 (Read & Inspect)

* [ ] **C1.** `officecli-docx/references/view-query.md`: Bổ sung case-study và ví dụ thực tế cho `officecli view --mode annotated` (hiển thị trực quan path, style và numbering inline).
* [ ] **C2.** `officecli-docx/references/view-query.md`: Thêm hướng dẫn chuyên sâu về `officecli query docx` sử dụng **CSS-like selectors** để truy vấn phần tử theo Type hoặc Style class.
* [ ] **C3.** Tích hợp tiền kiểm tra: Hướng dẫn sử dụng `officecli view --mode stats` để đếm tổng số section, header/footer trước khi tiến hành cấu trúc lại file.
* [ ] **C4.** `docx-qa/SKILL.md`: Ép buộc chèn bước chạy `officecli validate docx` vào ngay đầu pipeline QA như một bộ lọc cứng (hard gate).
* [ ] **C5.** Tối ưu hóa Context Hygiene: Bổ sung chỉ dẫn sử dụng tham số `get --depth <n>` để bóc tách cây DOM theo tầng, tuyệt đối không dump toàn bộ tài liệu lớn vào context của LLM.

#### D. Bổ sung các tính năng L2 (DOM Operations) còn thiếu

* [ ] **D1.** Tính năng điều hướng cấu trúc: Thêm tài liệu hướng dẫn và ví dụ cho `officecli move` dùng để sắp xếp lại thứ tự các khối paragraph hoặc các slide trong bản trình chiếu tại `elements.md`.
* [ ] **D2.** Nhân bản phần tử (`officecli add --from`): Viết tài liệu hướng dẫn cơ chế clone element từ file template (giải pháp thay thế tối ưu cho việc copy XML node thủ công).
* [ ] **D3.** Định dạng cấp thấp (Run-level Formatting): Thêm reference chi tiết cho `officecli set --prop` tác động lên các thuộc tính của thẻ run (font, bold, italic, color).
* [ ] **D4.** Thao tác bảng biểu chuyên sâu: Cung cấp reference chi tiết cho việc đọc/ghi dữ liệu trên ô của bảng (`officecli set docx /body/tbl[1]/tr[1]/tc[1] --prop text='value'`).

#### E. Kiểm soát và ứng dụng đúng mục đích L3 (Raw XML)

* [ ] **E1.** Xây dựng skill reference cho `officecli raw` (XPath query) phục vụ các tác vụ inspect edge-case khi tầng L1 không đáp ứng đủ.
* [ ] **E2.** Xây dựng skill reference cho `officecli raw-set` (XPath mutation) cho các tác vụ đặc thù (Ví dụ: kích hoạt cờ `updateFields` bắt buộc cập nhật lại Table of Contents khi mở file).
* [ ] **E3.** Xây dựng hướng dẫn cho `officecli add-part` để inject các cấu trúc OpenXML đặc thù (như Custom XML parts).
* [ ] **E4.** Thêm chế tài vào `AGENTS.md`: *"Chỉ cho phép sử dụng tầng L3 khi và chỉ khi tầng L1/L2 không hỗ trợ. Agent bắt buộc phải giải trình lý do kỹ thuật chi tiết vào file `build_report.json`"*.

#### H. Nâng cấp Help-First và Context Hygiene

* [~] **H1.** Đồng bộ hóa tư duy `help-first` từ `officecli-docx/SKILL.md` sang tất cả các skill modules còn lại (`docx-from-template`, `docx-qa`).
* [ ] **H2.** Thiết lập rule bắt buộc: *"Trước mỗi lệnh `officecli add` hoặc `officecli set`, Agent phải thực hiện gọi `officecli help docx <element> --json` để xác thực schema của property"*.
* [ ] **H3.** Cung cấp tài liệu đầy đủ cho quy trình Profile với `officecli view --mode annotated`.
* [ ] **H4.** Tích hợp Live Preview: Viết hướng dẫn ứng dụng cặp lệnh `officecli watch <file>` / `unwatch` nhằm phục vụ việc debug realtime output trong suốt quá trình phát triển pipeline.

#### I. Tối ưu hóa tệp cấu hình `AGENTS.md`

* [~] **I1.** Mở rộng biến môi trường `PATH`: Cấu hình bổ sung script tự động nhận diện và thiết lập môi trường chạy cho cả hệ điều hành Linux và macOS (hiện tại mới chỉ có Windows).
* [ ] **I2.** Kiểm chuẩn môi trường: Ép buộc Agent thực hiện kiểm tra phiên bản thông qua `officecli --version` tại bước khởi động của mọi task.
* [ ] **I3.** Chốt chặn tính toàn vẹn (Integrity Gate): Ràng buộc rule chạy `officecli view <file> --mode stats` ngay sau khi thực hiện `officecli close` để đảm bảo file đầu ra không bị corrupted.

---

### 🟢 NHÓM 3: ƯU TIÊN THẤP (Mở rộng hệ sinh thái & Nâng cấp AI)

#### F. Mở rộng Skills cho Excel (`.xlsx`) và PowerPoint (`.pptx`)

* [ ] **F1.** Phát triển module `officecli-xlsx/` tương tự cấu trúc của `officecli-docx/` (quản lý sheet, row, cell, formula, style).
* [ ] **F2.** Phát triển module `officecli-pptx/` (quản lý slide, shape, textbox, image, animation).
* [ ] **F3.** Cấu hình lại bộ định tuyến tại `AGENTS.md`: Thêm routing logic và phân phối task tự động dựa trên phần mở rộng của file đầu vào.
* [ ] **I4.** Bổ sung tập hợp các trigger phrases đặc trưng cho Excel/PowerPoint vào `AGENTS.md` (ví dụ: "tạo file excel", "xuất dữ liệu xlsx", "render slide powerpoint").

#### G. Tích hợp MCP Server và AI Native Tooling

* [ ] **G1.** Viết tài liệu hướng dẫn deploy OfficeCLI MCP Server trong không gian `.opencode/` giúp Agent chuyển dịch từ việc gọi shell subprocess sang gọi **MCP Tool Calls** trực tiếp thông qua giao thức JSON-RPC 2.0 (tối ưu hóa token và độ ổn định).
* [ ] **G2.** Bổ sung chỉ dẫn cấp cao tại `SKILL.md`: *"Ưu tiên tuyệt đối việc sử dụng MCP tool calls thay vì thực thi shell commands qua subprocess khi hệ thống có sẵn MCP server"*.
* [ ] **G3.** Tự động hóa phân phối Skill: Hướng dẫn Agent triển khai lệnh `officecli --install-skill <agent>` để đồng bộ cấu hình `SKILL.md` lên môi trường của opencode agent một cách tự động.

---

## 4. Kế hoạch triển khai hành động (Action Plan)

```
[ Giai đoạn 1 ] ──➡️ Thay thế toàn bộ xml.etree/zipfile trong 5 file Python bằng các lệnh OfficeCLI native (Nhóm A & B).
       │
[ Giai đoạn 2 ] ──➡️ Hoàn thiện hệ thống tài liệu References cho các tính năng L1/L2/L3 còn thiếu (Nhóm C, D, E, H).
       │
[ Giai đoạn 3 ] ──➡️ Siết chặt quy trình rào chắn (Hard Gates) trong AGENTS.md & Mở rộng tích hợp MCP Server, Excel, PPTX.

```

---

*Tài liệu checklist này đã được đồng bộ và lưu trữ trực tiếp vào Google Doc của dự án.*