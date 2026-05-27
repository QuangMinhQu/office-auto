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
- Khi task là `append`.
- Khi tài liệu có TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer hoặc page fields.

## Checklist QA tối thiểu

### 1. Body structure
- `view outline` phải phản ánh đúng heading mới.
- Không được skip cấp heading.
- Nếu append, nội dung cũ vẫn còn đầy đủ.

### 2. Numbering
- Numbered heading phải có `numId` + `ilvl` đúng.
- `paragraph[numId>0]` phải bao gồm các heading mới nếu template đang đánh số.

### 3. TOC
- Nếu tài liệu có TOC, heading mới phải được phản ánh trong TOC hoặc có kế hoạch rõ ràng để refresh/static fallback.
- Nếu người nhận không refresh field, không được để lại chuỗi `Update field to see table of contents` mà vẫn coi là đã xong.

### 4. References
- Nếu nội dung mới có citation, section `TÀI LIỆU THAM KHẢO` phải được cập nhật.
- Không được để section mới sử dụng nguồn mà reference list chưa có.

### 5. Appendix
- Nếu nội dung mới tham chiếu phụ lục, phải kiểm tra section phụ lục tồn tại và khớp.

### 6. Các danh mục phụ thuộc nội dung
- Danh mục hình
- Danh mục bảng
- Caption/sequence fields
- Cross-reference/bookmark nội bộ

### 7. Header/Footer/Page fields
- Header/footer không bị ghi đè ngoài ý muốn.
- PAGE/NUMPAGES fields tồn tại đúng cấu trúc.

### 8. Placeholder leak
- Không còn `{{...}}`, `{...}`, `<TODO>`, `xxxx`, `lorem` nếu đó là placeholder.

### 9. Tình trạng schema
- `validate` phải pass.
- `view issues` không có lỗi nghiêm trọng liên quan đến output vừa sửa.

## Delivery Gate
Chỉ PASS khi tất cả đúng:
```json
{
  "outline_ok": true,
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
Trong task append, lỗi phổ biến nhất là:
- mất nội dung cũ
- TOC chưa cập nhật
- references chưa thêm
- appendix/cross-reference bị stale
