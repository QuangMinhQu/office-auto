# DOCX Issue List 04: End-State Roadmap

## Mục tiêu cuối cùng

Workspace này phải đi đến trạng thái: người dùng ném vào nội dung nguồn và file format, pipeline có thể normalize input, hiểu scaffold, build ra một DOCX mới đúng format, và tự chứng minh chất lượng đầu ra.

## Baseline đã chốt hiện tại

1. Input normalization qua `input_processor.py` và MarkItDown đã có mặt trong wrapper chuẩn.
2. Semantic grounding qua `sample_content.md` và `sample_outline.json` đã là một phần của đường chạy mặc định.
3. Wrapper `scripts/build_report.py` đã là entrypoint chuẩn để agent/human đi qua cùng một contract.
4. `roundtrip_markitdown.py` + `qa_docx.py` là gate xác minh chính thức trước bàn giao.
5. `review_docx.py` là lớp screen review chính thức sau QA.
6. Workspace đã có `.opencode/AGENTS.md`, `task.md`, `.vscode/mcp.json`, `.vscode/tasks.json` và helper `scripts/latest_review_artifacts.py` để prompt ngắn vẫn đi đúng flow.

## End-state architecture

1. Input layer: mọi nguồn `.md`, `.docx`, `.pdf`, `.txt`, `.xlsx` được normalize về `normalized.md` bằng [input_processor.py](../.opencode/skills/md-to-docx-pipeline/scripts/input_processor.py) và MarkItDown ở các format phù hợp.
2. Semantic grounding layer: sample file cùng họ template được convert thành `sample_content.md` và `sample_outline.json` để planner có few-shot semantic anchor.
3. Planning layer: [plan_mapping.py](../.opencode/skills/md-to-docx-pipeline/scripts/plan_mapping.py) chỉ cho build tiếp khi range thật sự bounded hoặc khi strategy rewrite khác đã được chứng minh an toàn.
4. Rendering layer: builder có ít mutation hơn, ưu tiên batch hoặc one-pass rewrite ở part-level khi replacement lớn.
5. Post-process layer: `post_process_docx.py` xử lý các XML/package transforms nhỏ không nên trộn vào builder.
6. QA layer: structural QA + semantic roundtrip + issue summary, không finalize chỉ vì file “mở được”.
7. Review layer: `review_docx.py` soi drift trình bày sau QA và tạo artifact để người vận hành nhìn nhanh hơn JSON thuần.
8. Workspace automation layer: prompt ngắn vẫn route đúng nhờ `AGENTS.md`, `task.md`, MCP config, tasks và helper summary.

## Thứ tự ưu tiên kỹ thuật

1. Ổn định template discipline: tạo minimal scaffold template và prototype bank sạch.
2. Giảm mutation cost: thêm strategy rewrite mới cho replacement lớn.
3. Khóa correctness: sửa schema warnings, heading drift và section-break regressions.
4. Mở rộng input contract: normalize ổn định cho nhiều loại input user ném vào.
5. Nâng observability: run summary, benchmark suite, regression dashboards.

## Backlog đề nghị

1. Tạo `post_process_docx.py` và artifact `post_process_report.json`.
2. Thêm `template suitability report` để đánh giá template có phải scaffold hợp lệ hay không trước khi build.
3. Viết benchmark fixtures cho template nhỏ/vừa/lớn.
4. Thêm regression corpus cho references, appendix, tables, nested lists, code block và legal numbering.
5. Tách mode `bounded-replacement` và mode `part-rewrite` thay vì ép tất cả đi chung một builder path.
6. Nếu sau này cần DOCX review/redline qua MCP riêng, thêm server review chuyên dụng bên cạnh OfficeCLI chứ không thay builder hiện tại.

## Definition of done

- Pipeline xử lý được input user đa dạng mà không bắt user viết Markdown tay.
- Template format file được giữ đúng scaffold quan trọng.
- DOCX output pass structural + semantic QA ở phần lớn case chuẩn.
- Khi gặp template hoặc input xấu, pipeline fail rõ ràng với artifact đủ để sửa.