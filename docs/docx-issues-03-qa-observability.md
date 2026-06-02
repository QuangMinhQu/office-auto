# DOCX Issue List 03: QA And Observability Gaps

## Mục tiêu

Track này đảm bảo mỗi run đều để lại đủ artifact để biết rõ vì sao pass hoặc fail, thay vì chỉ biết “build chậm” hoặc “QA fail”.

## Issue hiện tại

1. Trước đây wrapper không ghi step timing, nên khó biết bottleneck nằm ở input, planning, build hay roundtrip.
2. Build step có thể fail trong quá trình mutate nhưng không để lại artifact rõ ràng.
3. QA hiện mạnh ở structural checks nhưng diagnosis theo nguyên nhân gốc vẫn còn rải rác giữa nhiều file.
4. Run state schema chưa phản ánh rõ wrapper-level artifact.

## Đã cải tiến trong workspace

1. [scripts/build_report.py](../scripts/build_report.py) giờ ghi `pipeline_report.json` với `started_at`, `finished_at`, `duration_seconds`, `failed_step` và danh sách step reports.
2. [.office-auto/run.schema.json](../.office-auto/run.schema.json) đã có artifact slot `pipeline_report`.
3. [build_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py) giờ ghi `build_report.json` trạng thái `failed` trước khi exit non-zero nếu build nổ giữa chừng.
4. [README.md](../README.md) đã mô tả `pipeline_report.json` như artifact chính thức.
5. [scripts/latest_review_artifacts.py](../scripts/latest_review_artifacts.py) đã gom status của `pipeline_report`, `qa_report` và `review_report` thành summary nhanh cho run mới nhất.
6. [review_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/review_docx.py) đã trở thành lớp review chính thức sau QA, để screen-review drift trình bày thay vì chỉ đọc JSON thô.

## Hướng xử lý tiếp theo

1. Gắn `risk_flags` từ `plan.json` sang wrapper summary để trước khi build đã thấy run này là `safe`, `warning`, hay `blocked`.
2. Nếu pipeline hướng đến input user không tin cậy hơn hiện tại, thêm timeout/memory guard cho các bước Pandoc và parser markdown.
3. Nếu review layer phát hiện drift lặp lại theo pattern, thêm rule-based triage để ưu tiên paragraph đáng ngờ nhất trong `review_report.md`.

## Definition of done

- Một run fail vẫn có `preflight.json`, `pipeline_report.json` và `build_report.json` hoặc artifact tương đương.
- Có thể nhìn một file summary là biết step nào chậm nhất, step nào fail và review/QA đang ở trạng thái nào.
- Schema run state không còn thiếu artifact wrapper-level.
- QA output không còn chỉ nói fail/pass mà còn gợi đúng nhóm nguyên nhân gốc.