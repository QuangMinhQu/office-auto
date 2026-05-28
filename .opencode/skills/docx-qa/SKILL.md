---
name: docx-qa
description: Skill QA cho Word (.docx) khi thêm, sửa hoặc append nội dung. Dùng khi cần rà soát TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer, page numbering và các phần phụ thuộc cấu trúc tài liệu trước khi giao file.
license: MIT
---
# SKILL: DOCX_QA

## Mục tiêu
Skill này chỉ phụ trách QA và delivery gate cho `.docx`.
Không dùng để tạo body từ đầu.
Syntax command chi tiết vẫn tra cứu trong `officecli-docx`.

## Khi nào phải load skill này
- Trước khi bàn giao file `.docx`.
- Khi task là `append` hoặc `preserve scaffold`.
- Khi tài liệu có TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer hoặc page fields.

## Checklist QA tối thiểu

### 1. Package QA
- File mở được.
- Chạy `officecli validate <file> --json` ngay đầu phase QA như hard gate đầu tiên.
- Sau `validate`, chạy `officecli view <file> issues --json` để lấy issue list hiện tại.
- Các part bắt buộc còn tồn tại nếu template ban đầu có: `word/document.xml`, `word/styles.xml`, `word/numbering.xml` khi áp numbering, header/footer parts.

### 2. Structural QA
- Header/footer không bị mất hoặc giảm bất thường: `header_count_output >= header_count_template` và `footer_count_output >= footer_count_template`.
- Section break và section settings vẫn còn.
- Nếu template có TOC thì field TOC vẫn còn.
- Nếu template có danh mục hình hoặc danh mục bảng thì field tương ứng vẫn còn.
- Nếu output dựa vào refresh-on-open, chấp nhận một trong hai bằng chứng:
  - `build_report.field_refresh_strategy = rewrite-toc-fields-on-open`
  - hoặc cơ chế khác được ghi rõ trong `build_report.json`

### 3. Range QA
- `replace_ranges` trong `plan.json` phải ở trạng thái `resolved`.
- Vùng được phép thay đã thay thật.
- Vùng phải giữ vẫn còn.
- Nếu `replace_ranges` không resolve được mà build vẫn chạy, phải fail ngay.

### 4. Body structure
- `view outline` phải phản ánh đúng heading mới.
- Không được skip cấp heading.
- Nếu append, nội dung cũ vẫn còn đầy đủ.
- Nếu preserve scaffold, nội dung cũ của template không được còn lại trong vùng đã thay.
- Nếu preserve scaffold, phải có cách chứng minh đây là `replace bounded range` chứ không phải `append body` hoặc `clear whole body`.

### 5. Numbering
- Numbered heading phải có `numId` + `ilvl` đúng.
- `paragraph[numId>0]` phải bao gồm các heading mới nếu template đang đánh số.

### 6. TOC
- Nếu tài liệu có TOC, heading mới phải được phản ánh trong TOC hoặc có kế hoạch rõ ràng để refresh/static fallback.
- TOC render sẵn trong package phải giữ hyperlink hợp lệ; không chấp nhận paragraph style `TOC*` bị chèn text thuần không có hyperlink.
- Nếu TOC chưa render sẵn đủ heading mới, chỉ được PASS khi `build_report.json` chứng minh refresh strategy hợp lệ.
- Nếu người nhận không refresh field, không được để lại chuỗi `Update field to see table of contents` mà vẫn coi là đã xong.

### 7. References
- Nếu nội dung mới có citation, section `TÀI LIỆU THAM KHẢO` phải được cập nhật.
- Không được để section mới sử dụng nguồn mà reference list chưa có.

### 8. Appendix
- Nếu nội dung mới tham chiếu phụ lục, phải kiểm tra section phụ lục tồn tại và khớp.

### 9. Các danh mục phụ thuộc nội dung
- Danh mục hình
- Danh mục bảng
- Caption/sequence fields
- Cross-reference/bookmark nội bộ
- Hyperlink TOC không được trỏ tới bookmark đã mất; nếu còn phụ thuộc vào refresh-on-open thì phải chứng minh cơ chế refresh đã được bật.

### 10. Header/Footer/Page fields
- Header/footer không bị ghi đè ngoài ý muốn.
- PAGE/NUMPAGES fields tồn tại đúng cấu trúc.

### 11. Placeholder leak
- Không còn `{{...}}`, `{...}`, `<TODO>`, `xxxx`, `lorem` nếu đó là placeholder.

### 12. Tình trạng schema
- `validate` phải pass.
- `view issues` không có lỗi nghiêm trọng liên quan đến output vừa sửa.
- Không coi warning vốn có của template là blocker nếu không phát sinh thêm lỗi nghiêm trọng ở output mới.

### 13. Semantic gate cho preserve scaffold
- Text extract của file kết quả phải khớp cấu trúc heading của nguồn.
- Không được xuất hiện duplicate heading pattern như:
  - `CHƯƠNG 1. CHƯƠNG 1`
  - `CHƯƠNG 2. CHƯƠNG 2`
  - `4.1. 1.1.`
  - `5.1. 2.1.`
- Không được xuất hiện thêm chương hoặc đề mục lớn không tồn tại trong markdown nguồn.
- Không được có dấu hiệu mất scaffold mà vẫn được coi là “đã đúng nội dung”.
- Nếu build report có chỉ số kiểu `body_children_before` gần bằng `body_children_after`, phải coi đây là tín hiệu append trá hình và kiểm tra lại ngay.

## Delivery Gate
Chỉ PASS khi tất cả đúng:
```json
{
  "package_ok": true,
  "required_parts_present": true,
  "scaffold_preserved": true,
  "replace_ranges_resolved": true,
  "outline_ok": true,
  "body_replaced_ok": true,
  "template_residue": false,
  "duplicate_heading_patterns": [],
  "numbering_ok": true,
  "toc_ok": true,
  "references_ok": true,
  "appendix_ok": true,
  "lists_ok": true,
  "cross_references_ok": true,
  "header_footer_ok": true,
  "placeholder_leak": false,
  "validate_ok": true
}
```

Nếu bất kỳ trường nào fail:
- không được giao file
- quay lại orchestrator phase execute/repair

## Lưu ý cho Open Models
Không được tự động coi `validate pass` là đủ.
Trong task rebuild, lỗi phổ biến nhất là:
- không xóa body cũ của template
- chèn heading mới chồng lên numbering cũ
- để text extract dính liền heading và paragraph do chèn sai block boundary
- QA chỉ nhìn `validate` nên bỏ lọt semantic regression
Trong task append, lỗi phổ biến nhất là:
- mất nội dung cũ
- TOC chưa cập nhật
- references chưa thêm
- appendix/cross-reference bị stale
