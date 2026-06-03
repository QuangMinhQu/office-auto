# Task: Default DOCX Workflow For The New Architecture

Tài liệu này là contract mặc định để agent chạy đúng kiến trúc mới khi người dùng chỉ đưa prompt ngắn.

## Mặc định của repo

- `mode`: `preserve-template-scaffold`
- `source_file`: `noidung.md`
- `template_file`: `format_template.docx`
- `target_file`: `report.docx`
- `run_dir`: `.office-auto/state/<run_id>`

Nếu người dùng đang yêu cầu workflow build DOCX chuẩn và không override file path, agent dùng bộ mặc định này.
Không được coi `manual-run` hay artifact cũ trong workspace là ngữ cảnh mặc định của session mới.

## Primitive flow bắt buộc (LLM-as-Reasoning-Engine)

Pipeline mới gồm 5 bước theo kiến trúc issue.md:

1. **Inspect**: Chạy `docx_inspect.py` để lấy raw dump template → `docx_inspect_output.json`
2. **LLM Reasoning**: Đọc `docx_inspect_output.json` + `noidung.md`, tự suy luận style map, heading levels, spacing intent, và viết `execution_ops.json`
3. **Validate**: Chạy `docx_validate_ops.py` để warn-only validate ops. Nếu có warnings, LLM tự sửa `execution_ops.json`
4. **Execute**: Chạy `execute_execution_ops.py` để apply ops cơ học lên template → `report.docx`
5. **Read Result**: Chạy `docx_read_result.py` để read back và verify. So với markdown nguồn, nếu chưa đúng thì sửa ops và repeat từ bước 3

### Supported ops (6 ops)

- `insert_paragraph_after`: Insert paragraph sau anchor với style/text
- `insert_paragraph_before`: Insert paragraph trước anchor
- `remove`: Xóa element tại path
- `update_text`: Update text của paragraph tại path
- `insert_table`: Insert table sau anchor
- `set_page_layout`: Set margins, paper_size, orientation

## Required artifacts

```yaml
mode: preserve-template-scaffold
source_file: noidung.md
template_file: format_template.docx
target_file: report.docx
required_artifacts:
	- preflight.json
	- run.json
	- template_inspection_raw.json
	- execution_ops.json
	- execution_ops_validation.json
	- plan.json
	- execution_plan.json
	- build_report.json
	- post_process_report.json
	- result_readback.json
```

## Hard gate

Agent không được coi task là xong nếu thiếu một trong các điều sau:

1. `execution_ops.json` đã được ghi trong run dir.
2. Validator không còn warnings nghiêm trọng chưa xử lý.
3. `build_report.json.status == completed`.
4. `result_readback.json` cho thấy heading/body/TOC/field phù hợp với markdown nguồn và template intent.
5. Scaffold quan trọng của template vẫn còn: header/footer, section settings, TOC hoặc field cấu trúc nếu template có.
6. Không có dấu hiệu duplicate heading pattern hoặc residue template rõ ràng trong output readback.

## Anti-patterns bị cấm

- Đẩy reasoning sang `parse_markdown.py`, `plan_mapping.py`, `compile_execution_plan.py` trong flow mặc định.
- Dùng `scripts/build_report.py` như default path khi chưa thử primitive flow mới.
- Chỉ kiểm `validate` rồi kết luận xong.
- Xóa sạch `w:body` vì muốn “đồng bộ nội dung nhanh”.

## Kết quả mong muốn

- `report.docx` phản ánh nội dung của `noidung.md` trong vùng nội dung chính.
- Template vẫn giữ scaffold hình thức.
- Run để lại đủ artifact để agent có thể retry theo primitive flow mà không phải quay lại planner cũ.