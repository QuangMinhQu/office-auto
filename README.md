# office-auto

Repo này dùng OpenCode + OfficeCLI để tự động hóa thao tác tài liệu Office theo hướng giữ nguyên scaffold của template, thay vì coi template chỉ là nguồn style rời rạc. Trọng tâm hiện tại là pipeline Markdown -> DOCX với contract `preserve-template-scaffold`, kèm phần mở rộng cho PPTX và định hướng cho XLSX.

## Mục tiêu của repo

- Biến yêu cầu nghiệp vụ trong `task.md` thành workflow có artifact rõ ràng.
- Tách phần reasoning ngắn của agent khỏi phần execute deterministic bằng Python scripts.
- Giữ các thành phần cấu trúc của template như header, footer, TOC, section break, numbering, style map và page setup.
- Dùng OfficeCLI native làm execution layer chính, hạn chế sửa OOXML thô trực tiếp.

## Cấu trúc repo

```text
office-auto/
├── chuong_2.md
├── task.md
├── update.md
├── format_template.docx
├── report.docx
├── done/
├── scripts/
│   ├── build_report.py
│   └── build_report_pptx.py
├── slides/
│   ├── slide_content.md
│   └── task.md
└── .opencode/
    ├── AGENTS.md
    └── skills/
        ├── docx-from-template/
        ├── docx-qa/
        ├── md-to-docx-pipeline/
        ├── md-to-pptx-pipeline/
        ├── officecli-docx/
        ├── officecli-mcp/
        ├── officecli-pptx/
        └── officecli-xlsx/
```

## Thành phần chính

### 1. Tài liệu đầu vào và đầu ra

- `chuong_2.md`: nguồn Markdown chính cho bài toán DOCX.
- `task.md`: contract build DOCX, mô tả mode, phần phải giữ, phần được thay, hard gate và artifact bắt buộc.
- `slides/slide_content.md`: nguồn Markdown cho PPTX.
- `slides/task.md`: contract build PPTX theo cùng triết lý preserve scaffold.
- `format_template.docx`: template Word gốc cần được giữ scaffold.
- `report.docx`: file đích sau khi chạy pipeline DOCX.

### 2. Tài liệu nghiên cứu và ghi nhận tiến độ

- `update.md`: tổng hợp định hướng mở rộng skill cho XLSX và PPTX.
- `done/`: chứa tài liệu phân tích, issue, metric và kết luận thiết kế đã chốt.

### 3. Runtime orchestration

- `.opencode/AGENTS.md`: luật routing theo intent, đặc biệt cho DOCX.
- `.opencode/skills/`: nơi định nghĩa skill orchestration, command reference và QA gate.
- `scripts/`: wrapper Python ở root để chạy pipeline theo contract cố định.

## Cấu trúc skills trong OpenCode

Repo chia skill theo vai trò, không chỉ theo định dạng file.

### DOCX stack

- `docx-from-template`: orchestrator chính cho tác vụ Word. Skill này quyết định mode, phase và invariant.
- `md-to-docx-pipeline`: execution pipeline ngoài context, sinh artifact JSON và gọi các script Python để parse, profile, plan, build, QA.
- `docx-qa`: delivery gate cho DOCX, kiểm package, structure, range và semantic trước khi bàn giao.
- `officecli-docx`: command reference. Chỉ load khi cần cú pháp `officecli`, schema element, `prop`, `numId`, `ilvl` hoặc rule resident/batch mode.

### PPTX stack

- `md-to-pptx-pipeline`: pipeline tương tự DOCX nhưng áp cho slide deck.
- `officecli-pptx`: command reference cho thao tác slide, layout, placeholder, shape, theme.

### Hạ tầng bổ sung

- `officecli-xlsx`: khung skill cho spreadsheet automation.
- `officecli-mcp`: phần định tuyến khi dùng OfficeCLI qua MCP thay vì shell subprocess.

## Cách skill DOCX được tổ chức

Luồng chuẩn cho Word trong repo này là:

1. `docx-from-template` nhận task và normalize mode nếu cần.
2. `md-to-docx-pipeline` tạo artifact phục vụ build ngoài context.
3. `officecli-docx` chỉ được kéo vào khi thiếu command syntax cụ thể.
4. `docx-qa` là hard gate cuối, không cho chốt chỉ vì `validate` pass.

Điểm quan trọng là repo không coi `officecli-docx` là workflow chính. Skill đó chỉ là từ điển lệnh; logic điều phối nằm ở `docx-from-template`, còn execution deterministic nằm ở `md-to-docx-pipeline`.

## Python scripts trong repo

### Root wrappers

- `scripts/build_report.py`: wrapper chạy pipeline DOCX end-to-end. Script này gọi lần lượt `parse_markdown.py`, `profile_template.py`, `plan_mapping.py`, `build_docx.py`, `qa_docx.py` trong `.opencode/skills/md-to-docx-pipeline/scripts/`.
- `scripts/build_report_pptx.py`: wrapper tương tự cho pipeline PPTX.

### DOCX pipeline scripts

Nằm trong `.opencode/skills/md-to-docx-pipeline/scripts/`.

- `parse_markdown.py`: parse Markdown thành `content_ast.json` và `content_outline.json`.
- `profile_template.py`: profile template DOCX để phát hiện scaffold, style catalog, numbering, heading, TOC, list-of-figures, list-of-tables, section count và candidate replace range.
- `plan_mapping.py`: lập `plan.json`, normalize mode cũ sang mode mới, resolve `preserve`, `replace_ranges`, `post_conditions` và execution strategy.
- `build_docx.py`: thực thi bounded replacement bằng OfficeCLI resident mode, không cho phép build nếu range chưa resolve.
- `qa_docx.py`: kiểm structural QA, range QA và semantic QA; fail nếu mất scaffold, còn residue template hoặc xuất hiện duplicate heading pattern.
- `run_officecli_batch.py`: helper để chạy một batch JSON qua `officecli batch` khi cần.
- `officecli_native.py`: lớp tiện ích bọc các lời gọi OfficeCLI native.

### PPTX pipeline scripts

Nằm trong `.opencode/skills/md-to-pptx-pipeline/scripts/` với tư duy tương tự: parse Markdown, profile template, lập plan slide-to-layout, build deck và QA deck.

## Methodology kỹ cho DOCX trong OpenCode

Đây là phần quan trọng nhất của repo.

### 1. Template không phải chỉ là nguồn style

Mode chuẩn hiện tại là `preserve-template-scaffold`. Trong mode này, template DOCX phải được xem là một package có cấu trúc, không phải một bộ style tách rời. Vì vậy pipeline phải giữ:

- cover hoặc front matter nếu có
- TOC
- list of figures hoặc list of tables nếu template có
- header, footer, page number
- section break, page setup, document settings
- styles và numbering bindings

Pipeline chỉ được thay vùng nội dung chính đã được resolve trong `plan.json`.

### 2. Bounded replacement thay cho clear-whole-body

Repo này chủ ý tránh anti-pattern sau:

- xóa trắng toàn bộ `w:body`
- đổ lại text từ Markdown
- kết luận thành công chỉ vì file mở được hoặc `validate` pass

Thay vào đó, pipeline phải profile template trước, xác định `replace_ranges`, sau đó chỉ remove/add trong phạm vi được phép thay. Nếu chưa resolve được range, build phải `blocked` hoặc `failed`, không được build liều.

### 3. Tách reasoning khỏi execution

Methodology của repo là đẩy state ra artifact JSON để agent không phải giữ toàn bộ Markdown hay XML trong context. Bộ artifact chuẩn cho DOCX gồm:

- `preflight.json`
- `run.json`
- `content_ast.json`
- `content_outline.json`
- `template_profile.json`
- `plan.json`
- `build_report.json`
- `qa_report.json`

Nhờ đó agent chỉ cần quyết định mode, routing và kiểm tra contract; phần thao tác file được Python scripts + OfficeCLI xử lý một cách deterministic.

### 4. Execution discipline với OfficeCLI

Khi build DOCX, repo ưu tiên resident mode:

```text
officecli open
-> remove/add/set theo plan
-> save
-> close
```

Nguyên tắc kèm theo:

- kiểm `officecli --version` ở preflight
- tra help/schema trước khi đoán `prop` hoặc `element`
- không mở/đóng nhiều vòng nếu không có lý do kỹ thuật rõ
- chỉ xuống L3 (`raw`, `raw-set`, `add-part`) khi L1/L2 không đủ và phải ghi rõ vào `build_report.json`

### 5. QA không dừng ở validate

Hard gate của DOCX trong repo này có 4 lớp:

- Package QA: file mở được, `validate` pass, part quan trọng còn tồn tại.
- Structural QA: header/footer, section break, TOC, field, numbering, style map vẫn còn hợp lệ.
- Range QA: `replace_ranges` đã resolve và vùng phải thay đã bị thay thật.
- Semantic QA: outline đầu ra khớp Markdown nguồn, không còn residue template, không có pattern lỗi như `CHƯƠNG 1. CHƯƠNG 1` hoặc `4.1. 1.1.`.

Điểm này là guardrail lớn nhất của repo: `validate pass` một mình không đủ để bàn giao `report.docx`.

## State machine cho DOCX

Luồng kỹ thuật hiện tại của pipeline DOCX:

1. Preflight: xác nhận mode, file vào/ra, OfficeCLI version.
2. Analyze: đọc outline nguồn, profile template, nhận diện scaffold và candidate range.
3. Plan: sinh `plan.json` với `preserve`, `replace_ranges`, `post_conditions`, `execution_strategy`.
4. Execute: copy template sang target rồi thay bounded range bằng OfficeCLI.
5. QA: kiểm package, structure, range và semantic.
6. Finalize: chỉ đánh dấu ready khi tất cả hard gate đều pass.

## Khi nào DOCX build bị chặn

Theo thiết kế hiện tại, pipeline phải fail-closed trong các trường hợp sau:

- không resolve được `replace_ranges`
- mode không đúng với contract
- build làm mất scaffold quan trọng của template
- vẫn còn heading cũ của template trong vùng đã thay
- xuất hiện duplicate numbering hoặc duplicate chapter pattern

Đây là chủ đích thiết kế, không phải limitation tình cờ.

## Cách chạy ở mức repo

Ví dụ chạy wrapper DOCX:

```bash
python scripts/build_report.py \
  --source-file /home/minhquang/office-auto/chuong_2.md \
  --template-file /home/minhquang/office-auto/format_template.docx \
  --target-file /home/minhquang/office-auto/report.docx
```

Ví dụ chạy wrapper PPTX:

```bash
python scripts/build_report_pptx.py
```

Artifacts của mỗi lần chạy được ghi dưới `.office-auto/state/<run_id>/` hoặc thư mục run được chỉ định qua `--run-dir`.

## Định hướng hiện tại

- DOCX là phần được thiết kế chặt nhất và đã có contract, pipeline, QA gate rõ ràng.
- PPTX đang đi theo cùng kiến trúc preserve scaffold nhưng tập trung vào slide master, layout, placeholder và theme.
- XLSX hiện mới ở mức khung skill và cần mở rộng thêm reference chuyên sâu.

## Tóm tắt ngắn

Nếu nhìn repo theo đúng abstraction:

- `task.md` mô tả contract.
- `.opencode/AGENTS.md` mô tả routing rule.
- `docx-from-template` quyết định workflow.
- `md-to-docx-pipeline` thực thi bằng artifact + Python.
- `officecli-docx` cung cấp cú pháp lệnh.
- `docx-qa` là cổng kiểm cuối để đảm bảo không phá scaffold DOCX.
