# DOCX Issue List 01: Performance Bottlenecks

## Mục tiêu

Track này tập trung vào nguyên nhân làm pipeline DOCX chậm hoặc time-out khi build tài liệu lớn.

## Issue hiện tại

1. Planner có thể chọn `selected_replace_range` quá rộng, khiến pipeline xóa gần toàn bộ body thay vì bounded replacement thật sự.
2. Builder đang mutate DOCX bằng rất nhiều OfficeCLI calls nhỏ, nên cost tăng mạnh khi template có body lớn.
3. Wrapper trước đây không có timing theo step, làm session nhìn như treo dù bottleneck nằm ở một bước cụ thể.

## Bằng chứng trong repo

- [.office-auto/state/chuong2-md-case/template_profile.json](../.office-auto/state/chuong2-md-case/template_profile.json) ghi `direct_body_child_count` rất lớn.
- [.office-auto/state/chuong2-md-case/plan.json](../.office-auto/state/chuong2-md-case/plan.json) cho thấy range đang trùm gần toàn bộ main story.
- [.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py) thực hiện `remove -> add -> set -> append run` theo từng mutation nhỏ.
- [scripts/build_report.py](../scripts/build_report.py) hiện đã ghi `pipeline_report.json` để đo timing từng bước.

## Đã cải tiến trong workspace

1. [plan_mapping.py](../.opencode/skills/md-to-docx-pipeline/scripts/plan_mapping.py) nay có `template_guardrails` để phát hiện `whole-body-rewrite`, `oversized-template-body` và `full-document-template-disguised-as-format`.
2. [compile_execution_plan.py](../.opencode/skills/md-to-docx-pipeline/scripts/compile_execution_plan.py) không compile tiếp nếu `plan.json` đã `blocked`.
3. [build_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py) nay ghi `estimated_minimum_officecli_calls` để lượng hóa cost build tối thiểu.
4. [scripts/build_report.py](../scripts/build_report.py) ghi `pipeline_report.json` với timing theo step.

## Hướng xử lý tiếp theo

1. Thêm một mode rewrite ở cấp package-part hoặc one-pass XML rewrite cho `word/document.xml` thay vì hàng trăm mutation OfficeCLI rời.
2. Tách `format_template.docx` thật sự thành scaffold template mỏng: giữ front matter, section settings, header/footer, field parts và prototype paragraphs sạch.
3. Nếu template body quá lớn nhưng preserve-part signals quá yếu, builder nên block sớm và gợi ý tạo minimal scaffold template.
4. Thêm benchmark case có body nhỏ, body vừa và body lớn để đo cost theo `remove_count`, `render_ops` và `estimated_minimum_officecli_calls`.

## Definition of done

- `plan.json` không còn chọn whole-body rewrite cho các template format-only hợp lệ.
- `build_report.json` có cost estimate và không còn hoàn tất im lặng khi remove batch fail.
- `pipeline_report.json` chỉ rõ bước chậm nhất và thời lượng từng step.
- Một template lớn không còn làm session “đơ” mà không có diagnostics cụ thể.