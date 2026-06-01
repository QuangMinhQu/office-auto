# Task: Standard DOCX Workflow For This Repo

Tài liệu này là contract mặc định để agent chạy đúng workflow chuẩn của workspace khi người dùng chỉ đưa prompt ngắn.

## Mặc định của repo

- `mode`: `preserve-template-scaffold`
- `source_file`: `chuong_2.md`
- `template_file`: `format_template.docx`
- `target_file`: `report.docx`
- `run_dir`: `.office-auto/state/<run_id>`
- `wrapper`: `scripts/build_report.py`

Nếu người dùng không override file path, agent phải dùng đúng bộ mặc định này.

## Mục tiêu

- Sinh `report.docx` mới từ `chuong_2.md`.
- Giữ scaffold của `format_template.docx`, không coi template chỉ là nguồn style.
- Để lại đầy đủ artifact để có thể truy nguyên từ input normalization tới review cuối.

## Contract bắt buộc

```yaml
mode: preserve-template-scaffold
source_file: chuong_2.md
template_file: format_template.docx
target_file: report.docx
wrapper: scripts/build_report.py
required_artifacts:
	- preflight.json
	- pipeline_report.json
	- run.json
	- template_preparation_report.json
	- markitdown_style_map.txt
	- normalized.md
	- sample_content.md
	- content_ast.json
	- content_outline.json
	- template_profile.json
	- plan.json
	- execution_plan.json
	- build_report.json
	- roundtrip_report.json
	- qa_report.json
	- review_report.json
	- review_report.md
	- review_screen.html
```

## Trình tự phải đi qua

1. `profile_template.py`
2. `prepare_template_scaffold.py` nếu template quá dày
3. `profile_template.py` lại nếu đã sinh `effective_template.docx`
4. `generate_markitdown_style_map.py`
5. `input_processor.py`
6. `extract_sample_content.py`
7. `parse_markdown.py`
8. `plan_mapping.py`
9. `compile_execution_plan.py`
10. `build_docx.py`
11. `roundtrip_markitdown.py`
12. `qa_docx.py`
13. `review_docx.py`

Không được bỏ qua wrapper để nhảy sang vài lệnh OfficeCLI rời rạc rồi kết luận xong.

## Hard gate

Agent không được coi task là xong nếu thiếu một trong các điều sau:

1. `replace_ranges` đã `resolved` bằng artifact.
2. Scaffold của template vẫn còn: header/footer, section settings, TOC hoặc field cấu trúc nếu template có.
3. `roundtrip_report.json` và `qa_report.json` đã được ghi.
4. `review_report.json` đã được ghi sau QA và phản ánh `qa_status` cuối.
5. Không có dấu hiệu duplicate heading pattern hoặc residue template trong vùng đã thay.
6. Không có placeholder leak bị bỏ qua như lỗi “không quan trọng”.

## Lệnh chuẩn

```bash
python scripts/build_report.py \
	--run-dir .office-auto/state/manual-run \
	--source-file chuong_2.md \
	--template-file format_template.docx \
	--target-file report.docx
```

Sau khi build xong, lấy nhanh artifact mới nhất bằng:

```bash
python scripts/latest_review_artifacts.py
```

## Kết quả mong muốn

- `report.docx` phản ánh nội dung của `chuong_2.md` trong vùng nội dung chính.
- Template vẫn giữ scaffold hình thức.
- Run để lại đủ artifact để biết rõ fail ở bước nào nếu chưa đạt.
- Review artifact đủ để agent hoặc người vận hành soi formatting drift mà QA thuần JSON chưa nói hết.