# Kế hoạch đánh giá pipeline DOCX

## Bộ ca kiểm thử tối thiểu

1. Preserve scaffold của `format_template.docx` rồi thay nội dung chính bằng toàn bộ `chuong_2.md`.
2. Append một section mới vào template đang có nội dung.
3. Fill placeholder cho biểu mẫu định kỳ.
4. Markdown có bảng, hình, caption và references.
5. Template có heading numbering phức tạp, TOC và phụ lục.
6. Template có danh mục hình hoặc danh mục bảng cần giữ nguyên field sau build.

## Metrics cần log

```text
context_tokens
tool_calls
elapsed_seconds
build_success
qa_pass
heading_match
style_match
numbering_match
toc_status
reference_status
placeholder_leak
scaffold_preserved
replace_range_resolved
template_residue_detected
header_footer_preserved
section_count_delta
```

## Quy tắc đọc kết quả
- Chỉ đánh giá subagent hoặc MCP sau khi đã có baseline pipeline script.
- Nếu token giảm nhưng `qa_pass` không tăng, chưa coi là thành công.
- Với `preserve-template-scaffold`, phải ưu tiên việc giữ scaffold, độ khớp format và loại bỏ residue của nội dung mẫu trong vùng đã thay.