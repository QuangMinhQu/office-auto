# Task: Tạo report.docx theo contract preserve-template-scaffold

Mục tiêu là sinh `report.docx` từ `chuong_2.md` nhưng không được đối xử `format_template.docx` như một bộ style rời rạc. File đích phải giữ nguyên scaffold hình thức của template và chỉ thay vùng nội dung chính bằng nội dung Markdown mới.

## Chế độ thực hiện

- `mode`: preserve-template-scaffold
- `template_file`: `format_template.docx`
- `target_file`: `report.docx`
- `source_file`: `chuong_2.md`
- `source_scope`: full-document

## Thành phần phải giữ

- Trang bìa hoặc phần mở đầu tương đương.
- Mục lục.
- Danh mục hình nếu template đang có.
- Danh mục bảng nếu template đang có.
- Header, footer, page number.
- Section break, margins, page setup, document settings.
- Styles, numbering và mọi ràng buộc cấu trúc ở cấp template.

## Thành phần được phép thay

- Vùng nội dung chính của tài liệu, được xác định bằng `replace_ranges` trong `plan.json`.
- Nếu chưa xác định được `replace_ranges` một cách có căn cứ, agent phải dừng ở trạng thái `blocked`, không được tự ý xóa toàn bộ body.

## Contract bắt buộc

```yaml
mode: preserve-template-scaffold
template_file: format_template.docx
target_file: report.docx
source_file: chuong_2.md
source_scope: full-document
preserve:
	- cover-page
	- toc
	- list-of-figures
	- list-of-tables
	- headers-footers
	- section-breaks
	- page-number-fields
	- styles-and-numbering
replace_ranges:
	- strategy: after-front-matter-to-end-of-main-story
		required: true
post_conditions:
	- toc-still-present-if-template-had-toc
	- list-of-figures-still-present-if-template-had-list
	- headers-footers-preserved
	- section-breaks-preserved
	- heading-style-mapped-to-template
	- numbering-not-duplicated
	- no-template-body-residue-inside-replaced-range
```

## Hard gate bắt buộc

Agent không được kết luận xong chỉ vì `validate` pass.

Trước khi bàn giao `report.docx`, agent phải tự chứng minh tất cả các điều sau:

1. Scaffold của template vẫn còn, tối thiểu gồm header/footer, section settings và các field mục lục hoặc danh mục nếu template có.
2. `replace_ranges` đã được resolve bằng artifact, không phải suy đoán tay trong prompt.
3. Outline của file kết quả khớp outline của `chuong_2.md` theo thứ tự.
4. Không còn residue của nội dung mẫu cũ bên trong vùng đã thay.
5. Không có các mẫu lỗi semantic sau trong text extract:
	 - `CHƯƠNG 1. CHƯƠNG 1`
	 - `CHƯƠNG 2. CHƯƠNG 2`
	 - `4.1. 1.1.`
	 - `5.1. 2.1.`
6. Không có placeholder hoặc scaffold bị mất rồi được coi là “không quan trọng”.

Nếu chưa chứng minh được các điều trên, agent phải coi task là chưa xong.

## Quy trình tối thiểu phải đi qua

1. Parse `chuong_2.md` thành `content_ast.json` và `content_outline.json`.
2. Profile `format_template.docx` để lấy `template_profile.json`, bao gồm scaffold, field, section, heading, numbering và candidate range.
3. Lập `plan.json` với `preserve`, `replace_ranges`, `post_conditions` và execution strategy.
4. Build `report.docx` theo bounded replacement, không dùng chiến lược xóa sạch body.
5. Chạy QA package + structural + range + semantic trước khi finalize.

## Kết quả mong muốn

- File đầu ra là `report.docx`.
- `report.docx` phản ánh đầy đủ nội dung hiện có trong `chuong_2.md` ở vùng nội dung chính.
- Template tiếp tục giữ scaffold hình thức thay vì chỉ còn vai trò “nguồn style”.
- File cuối phải validate sạch, không còn placeholder thừa, không mất mục lục hoặc các phần dẫn hướng tương tự nếu template ban đầu có.
- File cuối không được có duplicate chapter pattern khi copy text thô ra ngoài.