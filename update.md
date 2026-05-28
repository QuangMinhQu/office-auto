# PLAN: SKILLS CHO XLSX VÀ PPTX (Tương tự DOCX)

---

## 1. HIỆN TRẠNG (AS-IS)

### 1.1. DOCX Skills (Đã hoàn thiện)
* `SKILL.md`: Entry point, quy tắc bắt buộc, thứ tự tra cứu.
* `references/view-query.md`: Các lệnh `view`, `query`, `get`, cách định hướng trong tài liệu.
* `references/elements.md`: `paragraph`, `run`, `table`, `image`, `section`.
* `references/styles-numbering.md`: Quản lý `styles`, `numbering`, `numId`, `ilvl`.
* `references/fields-toc-refs.md`: `TOC`, `field`, `references`, `cross-reference`.
* `references/page-header-footer.md`: `section`, `page setup`, `header/footer`, `page number`.
* `references/batch-resident.md`: Cơ chế `resident mode`, `batch mode`, kỷ luật thực thi.
* `references/raw-l3.md`: Thao tác XML cấp thấp qua `raw`, `raw-set`, `add-part`, guardrail L3.

### 1.2. XLSX Skills (Hiện tại)
* `SKILL.md`: Đã có nhưng nội dung rất đơn giản, mang tính sơ khai.
* `references/core.md`: Chỉ chứa các lệnh cơ bản (`get`, `query`, `set`, `add`, `import`).
* **THIẾU:** Các phần tử phức tạp cấu thành một bảng tính nâng cao (`chart`, `pivot`, `conditional formatting`, `formulas`, `styles`).

### 1.3. PPTX Skills (Hiện tại)
* `SKILL.md`: Đã có nhưng cực kỳ đơn giản.
* `references/core.md`: Chưa có nội dung cụ thể, mới chỉ là khung file.
* **THIẾU:** Hết tất cả các thành phần chi tiết của một bài thuyết trình.

---

## 2. KẾ HOẠCH CHI TIẾT CHO XLSX SKILLS (TO-BE)

Dựa trên cấu trúc kiến trúc của `DeepWiki ExcelHandler` và format chuẩn của `docx`, hệ thống cần bổ sung và nâng cấp các file sau:

### 2.1. `SKILL.md` (Nâng cấp)
* **Mục tiêu:** Điểm truy cập đầu tiên (Entry point) cho `OfficeCLI xlsx`.
* **Điều kiện kích hoạt (Load):** Khi gặp task thao tác với `sheet`, `row`, `cell`, `formula`, `style` hoặc `import/export data`.
* **Điều kiện bỏ qua (Skip):** Khi chỉ đọc/ghi task thô hoặc lên kế hoạch pipeline ở tầng high-level.
* **Kỷ luật bắt buộc:**
    * *Help-first:* Bắt buộc gọi lệnh help trước khi suy đoán cú pháp: `officecli help xlsx <element> --json`.
    * *Kỷ luật Shell:* Luôn quote path, xử lý mượt mà cú pháp `Sheet1!A1` notation.
    * *Kỷ luật thực thi:* Đảm bảo chu trình `open`/`close` nằm trong cùng một phiên terminal, ưu tiên dùng `resident`/`batch` mode để tối ưu hiệu năng.
* **Thứ tự tra cứu:** `SKILL.md` $\rightarrow$ `references/<file>.md` $\rightarrow$ `officecli help`.
* **Danh mục tham chiếu:** Bản đồ liên kết đến các file chuyên sâu.
* **Boundary:** Tuyệt đối không nhồi nhét chi tiết command phức tạp vào prompt nếu nhiệm vụ chỉ là parse/mapping dữ liệu.

### 2.2. `references/view-query.md`
* **Workbook Tree:** Lệnh lấy cây cấu trúc `officecli get <file> / --depth 2`.
* **Query Sheets:** Tìm kiếm và lọc các trang tính `officecli query <file> 'sheet'`.
* **Cell/Range Access:** Phân biệt và ánh xạ giữa Path notation (`/Sheet1/row[1]/cell[1]`) và Excel notation (`Sheet1!A1:D10`).
* **Query Filters:** Lọc theo tên sheet, giá trị cell, hoặc pattern của công thức.
* **Sparse Cell Handling:** Cơ chế tối ưu chỉ hiển thị các ô có dữ liệu thực tế để tránh tràn context.
* **Named Ranges:** Cách thức query và truy cập các vùng dữ liệu đã đặt tên.

### 2.3. `references/elements.md`
* **Sheet:** Tạo mới, xóa, đổi tên, đổi màu tab (`tab color`), thiết lập `zoom`, cố định dòng/cột (`freeze panes`).
* **Row/Column:** Chèn (`insert`), xóa (`delete`), ẩn/hiện (`hide/unhide`), chỉnh độ cao/rộng (`height/width`).
* **Cell:** Quản lý giá trị (`value`), công thức (`formula`), và kiểu dữ liệu (`string`, `number`, `date`, `boolean`).
* **Table:** Định nghĩa và thao tác với Excel Tables (tự động có header, auto-filter, table styles).
* **Chart:** Hỗ trợ các loại biểu đồ (`bar`, `line`, `pie`, `scatter`), quản lý data series và tiêu đề biểu đồ.
* **Picture:** Nhúng ảnh, thiết lập vị trí (`position`) và kích thước (`size`).
* **Shape:** Thao tác với hộp văn bản (`textbox`) và các hình khối hình học.
* **PivotTable:** Khởi tạo và cấu hình các trường `rows`, `columns`, `values`, `filters`.

### 2.4. `references/formulas-functions.md`
* **Set Formula:** Cú pháp gán công thức, ví dụ: `officecli set <file> /Sheet1/B2 --prop formula='SUM(B1:B10)'`.
* **Formula Integrity:** Cơ chế cảnh báo và xử lý khi xóa dòng/cột làm ảnh hưởng, đứt gãy công thức (tránh lỗi `#REF!`).
* **Array Formulas:** Xử lý các hàm mảng hiện đại như `XLOOKUP`, `FILTER`, `UNIQUE`.
* **Named Formulas:** Định nghĩa và quản lý Name (`Define Name`).
* **Cell References:** Phân biệt địa chỉ tương đối và địa chỉ tuyệt đối (`$A$1`).
* **Formula Errors:** Nhận biết và xử lý các trạng thái lỗi như `#REF!`, `#VALUE!`, `#DIV/0!`.

### 2.5. `references/styles-formatting.md`
* **Font:** Tên font (`name`), kích cỡ (`size`), định dạng (`bold`, `italic`, `underline`), màu sắc.
* **Fill:** Đổ màu nền (`solid color`), màu chuyển sắc (`gradient`), hoa văn (`pattern`).
* **Border:** Kiểu viền (`style`), màu sắc, vị trí viền (`top`, `bottom`, `left`, `right`).
* **Alignment:** Căn lề ngang/dọc, tự động xuống dòng (`wrap text`), gộp ô (`merge cells`).
* **Number Format:** Định dạng số, tiền tệ (`currency`), phần trăm (`percentage`), ngày tháng (`date`), hoặc định dạng tùy chỉnh (`custom`).
* **Conditional Formatting:** Thiết lập các luật định dạng có điều kiện (so sánh lớn hơn/nhỏ hơn, chuỗi chứa ký tự, thang màu `color scales`).
* **Cell Styles:** Áp dụng các mẫu style có sẵn của Excel.
* **ExcelStyleManager:** Cơ chế gom nhóm và khử trùng lặp các style trong `WorkbookStylesPart` để tối ưu dung lượng file.

### 2.6. `references/data-operations.md`
* **Import CSV/TSV:** Đổ dữ liệu từ file text vào bảng tính: `officecli import <file> /Sheet1 data.csv`.
* **Export to CSV:** Trích xuất dữ liệu từ sheet ra file phẳng: `officecli export <file> /Sheet1 output.csv`.
* **Data Validation:** Tạo danh sách thả xuống (`dropdown lists`), giới hạn vùng số, hoặc thiết lập quy tắc tùy biến (`custom rules`).
* **Sort:** Sắp xếp dữ liệu theo một hoặc nhiều cột.
* **Filter:** Bật/tắt và cấu hình `AutoFilter`, `advanced filter`.
* **Find & Replace:** Tìm kiếm và thay thế chuỗi văn bản hoặc công thức trên diện rộng.

### 2.7. `references/advanced-features.md`
* **Freeze Panes:** Cố định dòng đầu/cột đầu khi cuộn trang dữ liệu.
* **Sheet Protection:** Khóa và đặt mật khẩu bảo vệ riêng cho từng sheet.
* **Workbook Protection:** Bảo vệ cấu trúc toàn bộ file Excel (không cho đổi tên, xóa sheet).
* **Comments:** Thêm và chỉnh sửa các bình luận (`cell comments`).
* **Hyperlinks:** Tạo liên kết nội bộ (đến ô/sheet khác) và liên kết bên ngoài (URLs).
* **Sparklines:** Vẽ biểu đồ mini ngay trong một ô dữ liệu.
* **Page Setup:** Cấu hình vùng in (`print area`), căn lề (`margins`), hướng trang (`orientation`), tiêu đề trang (`header/footer`).

### 2.8. `references/batch-resident.md`
* **Resident Mode:** Mở file một lần $\rightarrow$ thực hiện chuỗi thao tác $\rightarrow$ đóng file để lưu:
    ```bash
    officecli open <file>
    # ... thực hiện nhiều thao tác mutation ...
    officecli close
    ```
* **Batch Mode:** Thực thi đồng thời thông qua mảng JSON chứa nhiều operations.
* **Execution Discipline:** Quy tắc bắt buộc kiểm tra lại cấu trúc bằng `get`/`view` sau mỗi đột biến.
* **Performance:** Ưu tiên dùng `batch` cho các tác vụ thay đổi dữ liệu hàng loạt để giảm I/O.
* **Error Handling:** Chiến lược rollback trạng thái file khi xảy ra lỗi giữa chừng.

### 2.9. `references/raw-l3.md`
* **Raw Access:** Truy cập trực tiếp vào các part XML gốc: `/styles`, `/sharedstrings`, `/SheetName/drawing`.
* **Raw-set:** Sửa đổi trực tiếp nội dung XML raw.
* **Add-part:** Thêm các custom XML parts bên ngoài vào cấu trúc zip của file.
* **Guardrails:** Cảnh báo nghiêm ngặt khi hạ xuống tầng L3, chỉ dùng khi tầng L1/L2 không đáp ứng được tính năng.
* **Schema Ordering:** Áp dụng bộ quy tắc `ReorderWorksheetChildren` để đảm bảo thứ tự thẻ XML tuân thủ nghiêm ngặt OpenXML Schema.
* **Risks:** Cảnh báo nguy cơ làm hỏng cấu trúc file (`corrupt file`) nếu sửa sai thứ tự thẻ.

---

## 3. KẾ HOẠCH CHI TIẾT CHO PPTX SKILLS (TO-BE)

Dựa trên cấu trúc kiến trúc của `DeepWiki PowerPointHandler`, hệ thống cần bổ sung và nâng cấp các file sau:

### 3.1. `SKILL.md` (Nâng cấp)
* **Mục tiêu:** Điểm truy cập đầu tiên (Entry point) cho `OfficeCLI pptx`.
* **Điều kiện kích hoạt (Load):** Khi xử lý task liên quan đến `slide`, `shape`, `textbox`, `image`, `notes` hoặc thay đổi bố cục `layout`.
* **Điều kiện bỏ qua (Skip):** Khi chỉ phân tích bài toán high-level hoặc lập kế hoạch chuỗi công việc thô.
* **Kỷ luật bắt buộc:**
    * *Help-first:* Luôn tra cứu help hệ thống trước: `officecli help pptx <element> --json`.
    * *Kỷ luật Shell:* Trích xuất đường dẫn chính xác bằng cơ chế quote path, ví dụ `/slide[1]/shape[2]`.
    * *Kỷ luật thực thi:* Tuân thủ quy trình `open`/`close`, ưu tiên xử lý qua `resident`/`batch` mode.
* **Thứ tự tra cứu:** `SKILL.md` $\rightarrow$ `references/<file>.md` $\rightarrow$ `officecli help`.
* **Danh mục tham chiếu:** Bản đồ liên kết đến các file chuyên sâu của PPTX.
* **Boundary:** Không chèn mã lệnh thô vào prompt nếu mục tiêu chính chỉ là xử lý logic nghiệp vụ.

### 3.2. `references/view-query.md`
* **Presentation Tree:** Lấy toàn bộ cây cấu trúc slide: `officecli get <file> / --depth 2`.
* **Query Slides:** Tìm kiếm và định vị slide nhanh chóng: `officecli query <file> 'slide'`.
* **Query Shapes Selector Engine:** Bộ công cụ lọc shape nâng cao theo loại hình (`shape`, `picture`, `table`, `chart`).
* **Attribute Matching:** Tìm kiếm thuộc tính nâng cao: `[font='Arial']`, `[color=#FF0000]`, `[title=true]`.
* **Content Matching:** Lọc shape theo nội dung văn bản bên trong: `:contains("Sales Report")`.
* **Positional Filtering:** Lọc theo phân cấp vị trí, ví dụ: `slide[1] > shape`.
* **Element Retrieval:** Cách lấy chi tiết phần tử qua đường dẫn đích danh: `/slide[1]/shape[2]`, `/slide[1]/table[1]`.
* **Placeholder Resolution:** Cơ chế giải nghĩa thuộc tính kế thừa từ Layout và Master Slide.

### 3.3. `references/elements.md`
* **Slide:** Thêm (`add`), xóa (`delete`), đổi thứ tự (`reorder`), nhân bản (`duplicate`), gán bố cục (`layout assignment`).
* **Shape:** Quản lý các hình khối (chữ nhật, hình tròn, mũi tên), hộp văn bản (`textbox`), tọa độ vị trí (`x, y`), và kích thước (`cx, cy`).
* **Picture:** Nhúng hình ảnh đa định dạng (PNG, JPG, SVG), thiết lập văn bản thay thế (`alt text`), và thuộc tính không gian.
* **Table:** Thao tác dòng, cột, ô, áp dụng kiểu bảng (`table styles`), gộp ô (`merge cells`).
* **Chart:** Tích hợp các loại biểu đồ (`bar`, `line`, `pie`) thông qua việc dùng chung cấu trúc nền tảng `ChartHelper`.
* **TextBox:** Thêm nhanh khối văn bản thuần túy và quản lý nội dung text bên trong.
* **Group:** Quản lý `GroupShape` chứa tập hợp các shape con có cấu trúc phân cấp.
* **Connector:** Các đường thẳng/mũi tên kết nối có tính năng neo dính giữa các khối shape với nhau.
* **3D Model:** Tính năng nhúng và điều khiển các mô hình 3D định dạng `.glb`.
* **Zoom:** Tạo liên kết động dạng `Slide Zoom` trực quan giữa các slide.

### 3.4. `references/text-formatting.md`
* **Paragraph:** Căn lề (`alignment`), khoảng cách dòng (`spacing`), thụt đầu dòng (`indentation`).
* **Run:** Cấu trúc chi tiết nhỏ nhất của văn bản: tên font, kích cỡ, thuộc tính `bold`, `italic`, `underline`, màu chữ.
* **Bullet/Numbering:** Thiết lập định dạng danh sách ký tự đầu dòng, phân tầng thụt lề (`levels`).
* **Text within Shapes:** Quản lý cấu trúc phức hợp `TextBody` chứa nhiều đoạn văn bên trong một khối hình.
* **Placeholder Text:** Phân loại văn bản giữ chỗ hệ thống: `Title`, `Subtitle`, `Body`, `Footer`.
* **Rich Text:** Kỹ thuật áp dụng nhiều khối định dạng `Run` khác nhau trên cùng một dòng văn bản.

### 3.5. `references/visual-properties.md`
* **Fill:** Đổ màu nền cho hình: màu đơn (`solid color`), chuyển sắc (`linear`, `radial`), hoa văn (`pattern`), hoặc dùng ảnh nền (`picture fill`).
* **Outline:** Màu sắc viền, độ dày viền (`width`), kiểu nét đứt (`dash style`), hoặc viền kép (`compound line`).
* **Effects:** Hiệu ứng đổ bóng (`shadow - outer/inner`), phản chiếu (`reflection`), phát sáng (`glow`), làm mềm cạnh (`soft edges`).
* **Transform:** Ma trận biến đổi vị trí (`x, y` tính bằng đơn vị EMUs), kích thước (`cx, cy`), độ xoay góc (`rotation`).
* **Z-order:** Điều khiển lớp hiển thị: đưa lên trên cùng (`bring to front`), hạ xuống dưới cùng (`send to back`).
* **Color Resolution:** Cơ chế phân giải màu sắc theo chủ đề (`Theme colors`), mã `RGB`, hoặc hệ bảng màu (`scheme colors`).

### 3.6. `references/layouts-masters.md`
* **Slide Layouts:** Kỹ thuật áp dụng bố cục có sẵn vào slide hiện hành, hoặc tùy chỉnh `custom layouts`.
* **Slide Masters:** Cấu hình các cài đặt giao diện toàn cục (Global template settings).
* **Placeholder Types:** Xác định các loại vùng chứa mặc định: `title`, `body`, `footer`, `date`, `slide number`.
* **Placeholder Inheritance:** Luồng kế thừa thuộc tính: `Layout` $\rightarrow$ `Master` $\rightarrow$ `Slide`.
* **Theme:** Quản lý đồng bộ màu sắc (`Colors`), font chữ (`Fonts`), và hiệu ứng (`Effects`) của toàn bộ presentation.
* **Presentation Properties:** Định nghĩa kích thước slide (`slideWidth`, `slideHeight`), tỷ lệ hiển thị chuẩn (`16:9` hoặc `4:3`).

### 3.7. `references/animations-transitions.md`
* **Animations:** Thiết lập hiệu ứng xuất hiện (`entrance`), biến mất (`exit`), hoặc nhấn mạnh (`emphasis`).
* **Animation Timing:** Cấu hình trình kích hoạt (`on click`, `with previous`, `after previous`), thời lượng chạy (`duration`), và thời gian trễ (`delay`).
* **Timing Tree:** Quản lý cấu trúc cây thời gian phức tạp `CommonTimeNode`.
* **Target Correlation:** Ánh xạ chính xác hiệu ứng sẽ tác động lên mã định danh của shape nào (`spid` hoặc `id`).
* **Slide Transitions:** Kiểu chuyển trang giữa các slide (`fade`, `push`, `morph`), thời gian chuyển cảnh.
* **Morph Transition:** Xử lý kỹ thuật chuyển cảnh thông minh `Morph` ở cấp độ đối tượng giữa hai slide kế tiếp.

### 3.8. `references/notes-media.md`
* **Slide Notes:** Thêm mới và biên tập nội dung ghi chú dành riêng cho người thuyết trình (`speaker notes`).
* **Audio:** Nhúng các tệp âm thanh vào slide.
* **Video:** Nhúng và cấu hình các tệp video hiển thị trực tiếp.
* **Media Playback:** Thiết lập chế độ tự động chạy (`autoplay`), lặp lại (`loop`), hoặc âm lượng (`volume`).
* **Hyperlinks:** Tạo đường dẫn điều hướng nhanh đến slide được chỉ định, URLs bên ngoài hoặc mở file cục bộ.

### 3.9. `references/batch-resident.md`
* **Resident Mode:** Quy trình mở luồng kết nối `officecli open <file>` $\rightarrow$ chạy chuỗi đột biến $\rightarrow$ đóng và ghi file bằng `officecli close`.
* **Batch Mode:** Gửi mảng JSON lệnh để tối ưu hóa quá trình biên dịch slide.
* **Execution Discipline:** Luôn xác thực lại cấu trúc tổng thể của slide sau mỗi lệnh thay đổi giao diện.
* **Live Preview:** Cơ chế sinh mã xem trước dạng HTML (`ViewAsHtml`) phục vụ render thời gian thực.
* **Watch Server:** Khởi chạy máy chủ giám sát, tự động tải lại giao diện khi có thay đổi từ tệp nguồn.

### 3.10. `references/raw-l3.md`
* **Raw Access:** Can thiệp sâu vào các cấu trúc XML nền: `/theme`, `/slideMaster[N]`, `/slideLayout[N]`.
* **Raw-set:** Sửa đổi mã XML thô trực tiếp trên file gốc.
* **Add-part:** Bổ sung các cấu phần XML tùy biến vào gói nén PPTX.
* **Guardrails:** Cảnh báo rủi ro cao khi dùng L3, chỉ dùng khi không còn giải pháp L1/L2 thay thế.
* **Relationship Migration:** Cơ chế xử lý, cập nhật lại các tham chiếu `r:id` khi dịch chuyển hoặc sao chép các thành phần giữa các slide để tránh lỗi mất liên kết phần tử.
* **Risks:** Nguy cơ trực tiếp gây hỏng file trình chiếu nếu cấu trúc XML bị sai lệch chuẩn OpenXML.

---

## 4. ƯU TIÊN THỰC HIỆN (ROADMAP)

### PHASE 1: Foundational (Nền tảng - Cần làm trước)
* **XLSX:** `SKILL.md` + `view-query.md` + `elements.md` + `formulas-functions.md`
* **PPTX:** `SKILL.md` + `view-query.md` + `elements.md` + `text-formatting.md`

### PHASE 2: Core Features (Tính năng lõi)
* **XLSX:** `styles-formatting.md` + `data-operations.md` + `batch-resident.md`
* **PPTX:** `visual-properties.md` + `layouts-masters.md` + `batch-resident.md`

### PHASE 3: Advanced (Nâng cao & Tối ưu)
* **XLSX:** `advanced-features.md` + `raw-l3.md`
* **PPTX:** `animations-transitions.md` + `notes-media.md` + `raw-l3.md`

---

## 5. GỢI Ý CHIA SẺ CODE (COMMON REUSE)

Do có rất nhiều khái niệm trùng lặp giữa cả 3 định dạng (`docx`, `xlsx`, `pptx`), chúng ta có thể tách các module dùng chung ra thư mục trung tâm `references/common/` để tối ưu hóa context:

* `references/common/help-system.md`: Quy trình gọi hệ thống trợ giúp (`officecli help <format> <element> --json`).
* `references/common/path-addressing.md`: Khái niệm chung về DOM paths so với cú pháp bản địa của định dạng.
* `references/common/execution-modes.md`: Luồng làm việc chung của `resident mode`, `batch mode` và `live preview`.
* `references/common/raw-guardrails.md`: Định nghĩa các rủi ro, quy tắc an toàn khi hạ xuống tầng mã XML thô (L3).
* `references/common/chart-infrastructure.md`: Cơ chế quản lý cấu trúc biểu đồ dùng chung hệ sinh thái qua `ChartHelper`.

> **Lưu ý thiết kế:** Dù chia sẻ các phần core chung, mỗi định dạng tệp tin bắt buộc vẫn phải duy trì các file tham chiếu cụ thể của riêng mình vì:
> 1. *Cấu trúc phần tử khác biệt hoàn toàn:* `paragraph/run` (docx) $\neq$ `cell/row` (xlsx) $\neq$ `slide/shape` (pptx).
> 2. *Thuộc tính đặc trưng:* `numId/ilvl` (docx) $\neq$ `formula` (xlsx) $\neq$ `animation` (pptx).
> 3. *Mục đích sử dụng (Use case):* Dòng văn bản tuần tự (Document flow) $\neq$ Lưới dữ liệu (Spreadsheet grid) $\neq$ Trang trình diễn (Presentation slides).

---

## 6. KẾT LUẬN

* **XLSX:** Cần xây dựng mới **8 files** references (hiện tại mới chỉ có duy nhất `core.md`).
* **PPTX:** Cần xây dựng mới **9 files** references (hiện tại chưa có nội dung cụ thể).
* **Tổng thể:** Hệ thống cần hoàn thiện khoảng **17 files mới** và thực hiện **nâng cấp sâu cho 2 file `SKILL.md`** hiện tại.