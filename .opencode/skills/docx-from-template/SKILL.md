---
name: docx-from-template
description: Tạo file Word (.docx) mới hoàn toàn từ template, phân tích định dạng của template rồi tạo file mới với cùng định dạng và nội dung theo yêu cầu.
license: MIT
---
# SKILL: DOCX_FROM_TEMPLATE

## Mô tả
Tạo tài liệu Word (.docx) mới hoàn toàn dựa trên template. Skill này định nghĩa quy trình phân tích định dạng của template (font, cỡ chữ, khoảng cách, bảng, header/footer, style, v.v.) rồi TẠO MỚI file .docx với cùng định dạng chính xác và nội dung theo dữ liệu đầu vào. KHÔNG sao chép hay thay thế trực tiếp từ template file.

**Tất cả thao tác cụ thể với file .docx được thực hiện thông qua skill `officecli-docx`.** Skill này chỉ mô tả quy trình và logic; tra cứu syntax command, property name, và enum value trong `officecli-docx` skill.

## Đầu vào
- `template_file`: Đường dẫn đến file template .docx (ví dụ: `.opencode\skills\docx-from-template\template.docx`).
- `content`: Nội dung cần điền vào template (dạng JSON, Markdown, hoặc mô tả cấu trúc).
- `output_file`: Đường dẫn file đầu ra (mặc định: cùng thư mục với template, tên file khác).

## Quy trình thực hiện

Skill này có **4 giai đoạn** riêng biệt. Tuân thủ nghiêm ngặt thứ tự: hoàn tất Giai đoạn 1 trước khi bắt đầu Giai đoạn 2, hoàn tất Giai đoạn 2 trước khi bắt đầu Giai đoạn 3, hoàn tất Giai đoạn 3 trước khi bắt đầu Giai đoạn 4.

**Thao tác command:** Sử dụng `officecli-docx` skill cho tất cả lệnh `officecli` (view, get, create, add, set, batch, validate, query, raw-set).

---

### GIAI ĐOẠN 1: PHÂN TÍCH TEMPLATE (Template Analysis)

**Mục tiêu**: Hiểu rõ cấu trúc và định dạng của file template để lập bản đồ ánh xạ nội dung.

#### Bước 1: Khám phá cấu trúc template
- Xem outline template để ghi nhận số lượng paragraph, bảng (table), section, header/footer, style được sử dụng.
- Xem thống kê template để ghi nhận số trang, số từ, số hình ảnh, số bảng.
- Xem text hiện có để xác định các placeholder, biến thay thế (dạng `{variable}`, `[[variable]]`, `[BIẾN]`, hoặc văn bản mẫu cần thay thế).

*Sử dụng `officecli-docx` → Reading & Analysis cho các lệnh view outline, view stats, view text.*

#### Bước 2: Phân tích định dạng chi tiết
- Kiểm tra style của từng paragraph quan trọng: style name (Heading1, Heading2, Normal...), font family, font size, bold, italic, color, alignment, line-spacing.
- Kiểm tra table formatting (nếu có): số hàng, số cột, border style, cell shading, alignment từng cell.
- Kiểm tra header/footer.
- Kiểm tra document-level properties: docDefaults (font mặc định, cỡ chữ), page size, margin, locale.

*Sử dụng `officecli-docx` → Reading & Analysis cho các lệnh get với --depth và --json.*

#### Bước 3: Xây dựng bản đồ placeholder
Từ kết quả phân tích, tạo một bản đồ ánh xạ:
- **Danh sách placeholder**: Mỗi placeholder gồm (a) vị trí trong document (`/body/p[N]` hoặc `/body/tbl[N]/tr[M]/tc[K]`), (b) text hiện tại của placeholder, (c) style/định dạng liên quan.
- **Quy tắc thay thế**: Với mỗi placeholder, xác định (a) chỉ thay text, không động vào format; (b) nếu placeholder nằm trong run (`/body/p[N]/r[M]`), chỉ thay text của run đó; (c) nếu placeholder chiếm toàn bộ paragraph, thay text paragraph và giữ nguyên style.

#### Bước 4: Xuất file phân tích
- Ghi kết quả ra file JSON: `template_analysis_[tên_template].json`, đặt trong thư mục làm việc.
- File bao gồm: cấu trúc outline, danh sách placeholder với path, style của mỗi element quan trọng, document-level properties.

---

### GIAI ĐOẠN 2: TẠO FILE MỚI HOÀN TOÀN (Document Generation)

**Mục tiêu**: Tạo file .docx mới hoàn toàn từ đầu, áp dụng chính xác định dạng đã phân tích được ở Giai đoạn 1. KHÔNG sao chép hay thay thế từ template, mà xây dựng document mới dựa trên bản đồ định dạng đã lưu trong file phân tích.

**Tất cả thao tác trong giai đoạn này sử dụng `officecli-docx` skill.**

#### Bước 1: Tạo file .docx mới
- Tạo file mới với cấu trúc OpenXML mặc định.

*Sử dụng `officecli-docx` → Quick Start cho lệnh create.*

#### Bước 2: Áp dụng document-level properties từ phân tích
- Dựa trên `template_analysis_[tên].json`, áp dụng các thuộc tính document-level: font mặc định và cỡ chữ, kích thước trang và margin, locale (nếu cần).

*Sử dụng `officecli-docx` → Sections and page setup cho lệnh set document root.*

#### Bước 3: Tạo từng element theo bản đồ định dạng
Xây dựng document từ trên xuống dưới, từng element một, áp dụng style đã phân tích:
- Tạo paragraph với style chính xác
- Tạo heading (nếu có)
- Tạo table với định dạng đã phân tích
- Tạo header/footer theo định dạng đã phân tích

*Sử dụng `officecli-docx` → Creating & Editing (Paragraphs, runs, styles / Tables / Headers & Footers).*

#### Bước 4: Xử lý nội dung động (danh sách, bảng nhiều hàng)
Đối với nội dung có nhiều mục/hàng:
- Tạo table với số row tương ứng số lượng dữ liệu
- Thêm cell cho mỗi row
- Lặp lại cho từng row dữ liệu

*Sử dụng `officecli-docx` → Tables và Report-level recipes.*

#### Bước 5: Thêm paragraph bổ sung theo cấu trúc template
Nếu document cần nhiều paragraph theo thứ tự giống template:
- Duyệt qua danh sách element trong file phân tích theo thứ tự, tạo tương ứng
- Sử dụng batch mode cho nhiều element

*Sử dụng `officecli-docx` → Common Workflow (batch usage).*

#### Bước 6: Sử dụng batch mode cho hiệu suất
- Với document có nhiều element (10+), bắt buộc dùng batch để tối ưu.

*Sử dụng `officecli-docx` → Common Workflow cho batch operations.*

---

### GIAI ĐOẠN 3: KIỂM TRA & VALIDATE (Quality Assurance)

**Mục tiêu**: Đảm bảo file đầu ra giữ nguyên định dạng template và nội dung đã được thay thế đúng.

**Tất cả thao tác trong giai đoạn này sử dụng `officecli-docx` skill.**

#### Bước 1: So sánh cấu trúc
- So sánh outline template và file mới.
- **Kiểm tra**: Số paragraph, số table, số section phải GIỐNG NHAU (trừ trường hợp đã thêm nội dung động ở Giai đoạn 2 Bước 3).
- Nếu khác, quay lại Giai đoạn 2 để sửa.

*Sử dụng `officecli-docx` → Reading & Analysis (view outline).*

#### Bước 2: Kiểm tra định dạng
- So sánh style của các paragraph quan trọng.
- **Kiểm tra**: Style name, font, size, bold, italic, color, alignment phải GIỐNG NHAU.
- Nếu khác, dùng set để điều chỉnh lại theo template.

*Sử dụng `officecli-docx` → Reading & Analysis (get) và Creating & Editing (set).*

#### Bước 3: Kiểm tra nội dung thay thế
- Xem text file mới để xác nhận placeholder đã được thay.
- **Kiểm tra**: Không còn placeholder nào sót lại (`{...}`, `[[...]]`, `[...]`).
- Nếu còn placeholder chưa thay, quay lại Giai đoạn 2 Bước 2.

*Sử dụng `officecli-docx` → Reading & Analysis (view text, query).*

#### Bước 4: Validate file
- Chạy validate và kiểm tra issues.
- Nếu có lỗi, sửa bằng set hoặc raw-set.

*Sử dụng `officecli-docx` → QA (validate, view issues).*

#### Bước 5: Kiểm tra header/footer
- **Kiểm tra**: Header/footer giữ nguyên định dạng template, placeholder (nếu có) đã được thay thế.

*Sử dụng `officecli-docx` → Reading & Analysis (get footer).*

---

### GIAI ĐOẠN 4: XUẤT FILE CUỐI CÙNG (Final Output)

**Mục tiêu**: Hoàn thiện và xuất file .docx cuối cùng.

*Sử dụng `officecli-docx` → Common Workflow (close, view html).*

#### Bước 1: Đóng file resident mode

#### Bước 2: Kiểm tra cuối cùng bằng view html
- Mở file HTML đầu ra để kiểm tra trực quan: layout, định dạng, nội dung đúng như mong đợi.

#### Bước 3: Xuất báo cáo
Ghi kết quả vào file `generation_report_[tên_file].json`:
- Template source
- Output file path
- Số placeholder đã thay thế
- Số paragraph/table được thêm (nếu có)
- Kết quả validate

---

## LƯU Ý QUAN TRỌNG

- **Không được nhảy cóc**: Bắt buộc hoàn tất Giai đoạn 1 (phân tích template) trước khi bắt đầu Giai đoạn 2. Hoàn tất Giai đoạn 2 trước khi chuyển sang Giai đoạn 3. Hoàn tất Giai đoạn 3 (kiểm tra) trước khi chuyển sang Giai đoạn 4.
- **Định dạng từ phân tích là tối cao**: Giai đoạn 2 TẠO MỚI hoàn toàn file, KHÔNG sao chép hay thay thế từ template. Mọi định dạng (font, size, bold, italic, color, alignment, style) phải được áp dụng CHÍNH XÁC theo dữ liệu đã phân tích và lưu trong `template_analysis_[tên].json`.
- **Style matching chính xác**: Khi tạo mỗi element mới, phải lấy style tương ứng từ file phân tích: style name, font family, font size, bold, italic, color, alignment, line-spacing. Thiếu bất kỳ thuộc tính nào so với template đều là lỗi.
- **Batch mode cho nhiều element**: Khi tạo hơn 5 element (paragraph, table, row...), bắt buộc dùng batch để tối ưu I/O và tránh corruption file. Tham khảo `officecli-docx` → Common Workflow.
- **Luôn validate sau khi tạo**: Sau mỗi nhóm element được tạo, chạy validate để đảm bảo file vẫn hợp lệ. Tham khảo `officecli-docx` → QA.
- **Quản lý resident mode**: Với file lớn hoặc nhiều thao tác, dùng open / close để quản lý resident session, tránh file-lock conflict. Tham khảo `officecli-docx` → Common Workflow.
- **Content mapping**: Agent phải ánh xạ nội dung đầu vào vào các vị trí tương ứng trong bản đồ phân tích. Nếu nội dung đầu vào có nhiều mục hơn placeholder, tạo thêm element mới với cùng style.
- **Template làm tham chiếu**: Template file chỉ dùng để phân tích ở Giai đoạn 1. Không đọc, không sao chép, không thay thế trực tiếp từ template ở Giai đoạn 2.
- **Tra cứu command syntax**: Mọi lệnh officecli, property name, enum value, và schema element được tra cứu trong `officecli-docx` skill. Không đoán property name — luôn tham khảo `officecli-docx` → Help-First Rule.

---

## Cấu trúc đầu ra mẫu

### File phân tích template (`template_analysis_[tên].json`)
```json
{
  "template_file": "path/to/template.docx",
  "outline": {
    "paragraphs": 25,
    "tables": 2,
    "sections": 1,
    "has_header": true,
    "has_footer": true
  },
  "placeholders": [
    {
      "path": "/body/p[3]",
      "current_text": "{ten_ho_ten}",
      "style": "Normal",
      "font": "Times New Roman",
      "size": "14pt",
      "bold": false
    },
    {
      "path": "/body/p[5]",
      "current_text": "{ngay_lap}",
      "style": "Normal",
      "font": "Times New Roman",
      "size": "14pt",
      "bold": false
    }
  ],
  "document_properties": {
    "defaultFont": "Times New Roman",
    "defaultFontSize": "14pt",
    "pageSize": "A4",
    "locale": "vi-VN"
  }
}
```

### File báo cáo (`generation_report_[tên].json`)
```json
{
  "template_source": "path/to/template.docx",
  "output_file": "path/to/output.docx",
  "placeholders_replaced": 8,
  "paragraphs_added": 0,
  "rows_added": 3,
  "validation_passed": true,
  "issues_found": 0
}
```

---

## YÊU CẦU TUÂN THỦ (Compliance)

1. **Định dạng từ phân tích là tối cao**:
   - File đầu ra phải khớp 100% định dạng của template: font family, font size, bold, italic, underline, color, alignment, line-spacing, paragraph-spacing, indentation.
   - Mọi element phải sử dụng style name đúng như trong template.
   - Không được thêm style mới nếu template không có.

2. **Tạo mới, không thay thế**:
   - Giai đoạn 2 TẠO MỚI hoàn toàn file .docx, KHÔNG đọc/sao chép/thay thế từ template file.
   - Toàn bộ định dạng phải được apply qua props khi tạo element: `style`, `font`, `size`, `bold`, `italic`, `color`, `alignment`.
   - Không được bỏ qua bất kỳ thuộc tính định dạng nào đã phân tích được ở Giai đoạn 1.

3. **Nội dung động**:
   - Mỗi element được tạo mới phải có đầy đủ style matching từ bản đồ phân tích.
   - Không phá vỡ cấu trúc table: số cột phải khớp template, chỉ thêm row nếu cần.
   - Thứ tự element trong document phải giống thứ tự trong template.

4. **Header/Footer**:
   - Tạo header/footer mới với định dạng chính xác như đã phân tích.
   - Chỉ tạo header/footer nếu template có header/footer.
   - Không thêm element không có trong template vào header/footer.

5. **Validate trước khi xuất**:
   - Bắt buộc chạy validate và view issues trước khi hoàn tất. Tham khảo `officecli-docx` → QA.
   - Nếu có lỗi, phải sửa và validate lại cho đến khi file sạch.
   - Không xuất file có lỗi OpenXML.

6. **Quản lý lỗi**:
   - Nếu command thất bại, kiểm tra lại path, prop name, và syntax bằng way tham khảo `officecli-docx` → Help-First Rule.
   - Không đoán property name: luôn tra cứu trong `officecli-docx` skill.
   - Nếu gặp lỗi không thể sửa, xóa file output và bắt đầu lại từ Giai đoạn 2 Bước 1.

7. **Hiệu suất**:
   - Với 5+ element cần tạo, bắt buộc dùng batch. Tham khảo `officecli-docx` → Common Workflow.
   - Với file lớn (100+ paragraph), dùng resident mode: open → batch operations → close.
   - Không chạy từng lệnh add riêng lẻ cho nhiều element.

8. **Tính nhất quán**:
   - Tất cả element cùng style trong document phải có cùng định dạng xuyên suốt.
   - Nếu có bảng dữ liệu, định dạng số, ngày tháng phải nhất quán với quy chuẩn của template.
