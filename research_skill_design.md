# Research: Thiết kế skill cho OpenCode + Qwen + OfficeCLI

## Kết luận ngắn

Vấn đề hiện tại không phải do thiếu prompt hay thiếu context. Vấn đề là workflow đang đối xử tài liệu Office như một khối nội dung thuần văn bản, trong khi DOCX, PPTX, XLSX là các gói Open XML gồm nhiều part quan hệ với nhau. Nếu build theo kiểu "xóa body rồi đổ text mới vào", kết quả gần như chắc chắn sẽ làm mất hoặc phá các phần hình thức như bìa, mục lục, danh mục hình, numbering, section, layout, placeholder, slide master, workbook structure.

Vì vậy, hướng đúng là:

1. Skill phải ngắn, chỉ đóng vai trò điều phối.
2. Quy tắc định dạng phải được externalize thành artifact, plan và validator.
3. Tác vụ Office phải được chia theo "preserve structure" và "replace content" thay vì chỉ theo định dạng file.
4. Qwen/OpenCode chỉ nên quyết định mode, anchor, mapping; phần sửa tài liệu phải do OfficeCLI hoặc engine chuyên biệt thực hiện.

## Nguồn uy tín đã đối chiếu

### 1. Thiết kế skill và context

- Anthropic, Skill authoring best practices:
  https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices
- Anthropic, Effective context engineering for AI agents:
  https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
- OpenCode, Agents:
  https://opencode.ai/docs/agents/
- OpenCode, Agent Skills:
  https://opencode.ai/docs/skills/

### 2. Tool use / function calling cho Qwen

- Qwen docs, Function Calling:
  https://qwen.readthedocs.io/en/latest/framework/function_call.html

### 3. OfficeCLI

- OfficeCLI, command mcp:
  https://github.com/iOfficeAI/OfficeCLI/wiki/command-mcp
- OfficeCLI, command batch:
  https://github.com/iOfficeAI/OfficeCLI/wiki/command-batch

### 4. Cấu trúc chuẩn Open XML

- Microsoft Learn, Structure of a WordprocessingML document:
  https://learn.microsoft.com/en-us/office/open-xml/word/structure-of-a-wordprocessingml-document
- Microsoft Learn, Structure of a PresentationML document:
  https://learn.microsoft.com/en-us/office/open-xml/presentation/structure-of-a-presentationml-document
- Microsoft Learn, Structure of a SpreadsheetML document:
  https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document

### 5. Thư viện thao tác file

- python-docx, Working with documents:
  https://python-docx.readthedocs.io/en/latest/user/documents.html
- python-pptx:
  https://python-pptx.readthedocs.io/en/latest/
- openpyxl:
  https://openpyxl.readthedocs.io/en/stable/

## Những gì nguồn nói rất rõ

### A. Skill phải ngắn và progressive disclosure

Anthropic và OpenCode đều nhất quán ở 4 điểm:

1. `SKILL.md` nên ngắn, dễ discover, description phải nói rõ khi nào dùng.
2. Chi tiết dài phải tách ra reference file hoặc script.
3. Workflow phức tạp phải có plan -> validate -> execute -> verify.
4. Script nên làm việc deterministic thay vì bắt model tự viết logic mỗi lần.

Điều này khớp trực tiếp với repo của bạn: hướng rút gọn `officecli-docx` và externalize pipeline là đúng. Tuy nhiên mới đúng ở mức kiến trúc, chưa đúng ở mức engine thực thi.

### B. Với Qwen, tool calling phải đơn giản và schema rõ

Qwen docs nhấn mạnh:

1. Tool/function schema phải rõ, ít mơ hồ.
2. Nên dùng template/tool-calling format chuẩn thay vì ReAct tự do cho reasoning model.
3. Phải chuẩn bị cho corner case tool call malformed hoặc lập luận đúng nhưng args sai.

Suy ra cho workspace này:

1. Không nên để một skill dài vừa giải thích chiến lược, vừa mang cả command reference, vừa giao quyền suy luận tự do về cách sửa OOXML.
2. Cần ít mode hơn nhưng mode nào cũng có contract rất cứng.
3. `@task.md` phải dẫn đến một pipeline có schema input/output rõ, không phải một chuỗi suy luận mở.

### C. DOCX/PPTX/XLSX không phải là một "body text"

Microsoft Learn mô tả rất rõ:

- DOCX gồm nhiều story/part: main document, header, footer, footnote, endnote, comments, settings, styles...
- PPTX gồm presentation part, slide master, slide layout, slide, notes, handout master, theme...
- XLSX gồm workbook, worksheet, shared strings, tables, charts, pivot caches, conditional formatting...

Tức là nếu workflow chỉ thay nội dung thân bài thì:

1. DOCX có thể mất bìa, mục lục, danh mục hình, section break, numbering binding.
2. PPTX có thể vỡ layout/placeholder/master khi thêm shape trực tiếp thay vì map vào layout.
3. XLSX có thể giữ dữ liệu nhưng hỏng table range, chart binding, named range, pivot cache.

### D. Thư viện Python phổ thông có giới hạn giữ format

`python-docx` nói khá thẳng: mở rồi lưu file hiện có sẽ để yên nhiều thứ mà nó chưa hiểu, nhưng nó không phải công cụ lý tưởng để tái cấu trúc tài liệu phức tạp với yêu cầu fidelity cao. `python-pptx` và `openpyxl` hữu ích cho lớp thao tác logic, nhưng càng đụng sâu vào master/layout/theme/advanced formatting thì càng cần hiểu cấu trúc Open XML hoặc dùng tool chuyên biệt.

Nói cách khác:

1. `python-docx` phù hợp cho phân tích, dựng plan, chỉnh một số phần có kiểm soát.
2. Không nên dùng nó như engine duy nhất để "rebuild từ template mà vẫn giữ đầy đủ hình thức".
3. Nếu OfficeCLI đã có batch/MCP/unified tool cho Office artifact thì nên đẩy phần sửa tài liệu sang đó hoặc sang OOXML-level operations có validation.

## Kết luận trực tiếp cho lỗi hiện tại

Log hiện tại cho thấy run gần nhất đã "đúng nội dung" hơn, nhưng lại mất các phần như tiêu đề, mục lục, danh mục hình, và format phần thân cũng không bám template. Điều này phù hợp hoàn toàn với một lỗi thiết kế mode:

`rebuild-from-template-format` hiện đang bị hiểu thành:

- lấy template làm nguồn style mơ hồ
- xóa phần body hiện có
- đổ lại heading/paragraph từ markdown

Trong khi mode đúng phải là:

- preserve document scaffolding
- preserve front matter và field-based sections
- xác định đâu là vùng nội dung chính được phép thay
- chỉ thay vùng đó bằng content mới
- sau đó refresh/kiểm tra các field liên quan

Nói gọn: đang "replace whole body", trong khi bài toán thật là "replace bounded content regions while preserving document scaffolding".

## Thiết kế skill phù hợp hơn cho Qwen 35B + OpenCode

### 1. Tách skill theo quyết định, không tách theo file format thuần túy

Không nên chỉ có:

- `officecli-docx`
- `officecli-pptx`
- `officecli-xlsx`

Nên có lớp skill theo intent:

- `office-preserve-structure`
- `office-replace-content`
- `office-template-fill`
- `office-semantic-qa`
- `officecli-reference`

Vì với Qwen, decision boundary phải rất rõ. Nếu skill name và description chỉ nói theo format file, model dễ load sai skill nhưng vẫn làm sai mode.

### 2. Chia mode theo invariant tài liệu

Đề xuất mode mới:

- `preserve-template-scaffold`
  Giữ nguyên bìa, mục lục, danh mục hình/bảng, section, header/footer, field, layout. Chỉ thay nội dung ở vùng thân bài được chỉ định.
- `replace-main-content-range`
  Thay một dải nội dung giữa hai anchor rõ ràng.
- `fill-declared-placeholders`
  Chỉ điền placeholder đã khai báo.
- `append-structured-section`
  Chèn thêm section mới sau anchor cụ thể.
- `full-regenerate-from-schema`
  Dùng khi chấp nhận dựng lại tài liệu gần như từ đầu.

Mode `rebuild-from-template-format` hiện tại quá rộng và quá mơ hồ.

### 3. Skill orchestration phải có ít tự do hơn

Theo best practice của Anthropic, với tác vụ fragile thì nên giảm degrees of freedom.

Áp dụng ở đây:

1. `task.md` không nên chỉ nêu mục tiêu.
2. Nó phải khai báo rõ:
   - preserve phần nào
   - replace phần nào
   - anchor nào dùng để xác định phạm vi
   - field nào phải tồn tại sau build
   - điều kiện fail cứng

Ví dụ contract tốt hơn:

```yaml
mode: preserve-template-scaffold
template_file: format_template.docx
source_file: chuong_2.md
target_file: report.docx
preserve:
  - cover-page
  - title-page
  - toc
  - list-of-figures
  - list-of-tables
  - headers-footers
  - section-breaks
replace_ranges:
  - start_anchor: "CHƯƠNG 1"
    end_anchor: "TÀI LIỆU THAM KHẢO"
post_conditions:
  - toc-still-present
  - list-of-figures-still-present
  - heading-style-mapped
  - numbering-not-duplicated
  - no-template-body-residue-in-replaced-range
```

### 4. OfficeCLI nên là execution layer mặc định

Từ docs OfficeCLI:

1. Có MCP server tích hợp.
2. Có `batch` để gom nhiều thay đổi trong một open/save cycle.
3. Có `view`, `get`, `query`, `set`, `add`, `remove`, `move`, `validate`, `raw`.

Điều này rất hợp với Qwen/OpenCode nếu thiết kế lại như sau:

1. Qwen chỉ sinh `plan.json` với operation intent.
2. Script validator kiểm tra `plan.json`.
3. Executor convert plan thành batch commands hoặc MCP calls.
4. QA đọc output qua `view/query/get/validate`, không chỉ dựa vào text extract.

### 5. QA phải kiểm cả structure, không chỉ semantic text

Hiện QA của repo vẫn thiên về:

- heading count
- duplicate pattern
- text residue

Chưa đủ. Cần 4 tầng QA:

1. Package QA
   - file mở được
   - validate pass
   - part quan trọng còn tồn tại

2. Structural QA
   - DOCX: header/footer, TOC field, list-of-figures field, section count, style map, numbering links
   - PPTX: slide master/layout binding, placeholder count, theme presence, notes/handout preservation
   - XLSX: workbook sheets, named ranges, table refs, chart refs, pivot parts, conditional formatting

3. Range QA
   - vùng cần thay đã thay
   - vùng cần giữ vẫn còn
   - anchor còn hợp lệ

4. Semantic QA
   - outline khớp source
   - không duplicate numbering
   - không mất references

## Thiết kế pipeline nên đổi thế nào

### DOCX

Pipeline đúng nên là:

1. `profile_template.py`
   - phát hiện front matter
   - phát hiện field sections: TOC, list-of-figures, list-of-tables
   - map section breaks
   - map style + numbering
   - xác định content range được thay

2. `plan_mapping.py`
   - map markdown heading -> style id thực tế trong template
   - không quyết định bằng tên style suy đoán nếu chưa verify

3. `build_docx.py`
   - chỉ replace bounded range
   - preserve part ngoài phạm vi
   - dùng OfficeCLI batch hoặc OOXML edit có kiểm tra

4. `qa_docx.py`
   - kiểm TOC/list-of-figures còn tồn tại
   - kiểm heading style thực sự dùng style của template
   - kiểm numbering definition/link không bị vỡ

### PPTX

Không build theo kiểu "add textbox vào slide trống" nếu yêu cầu bám template. Phải:

1. detect slide layout và placeholder
2. map content vào placeholder trước
3. chỉ fallback sang add shape khi layout không hỗ trợ
4. QA kiểm slide master/layout/theme còn nguyên

### XLSX

Không build theo kiểu chỉ ghi cell values nếu workbook có format/reporting phức tạp. Phải:

1. preserve workbook scaffold
2. update data ranges có chủ đích
3. repair table refs / named ranges / chart refs / formula scope khi cần
4. QA kiểm workbook structure ngoài dữ liệu

## Đề xuất thay đổi được cuộc chơi

### Đổi cuộc chơi 1: Đổi tên và semantics của mode chính

Thay `rebuild-from-template-format` bằng `preserve-template-scaffold`.

Lý do: tên mới mô tả đúng invariant cần giữ, buộc model hiểu rằng đây không phải regenerate toàn body.

### Đổi cuộc chơi 2: Plan phải khai báo phạm vi replace bằng anchor

Nếu không có anchor thì agent sẽ tiếp tục "replace all body". Đây là gốc của lỗi mất bìa, TOC, danh mục hình.

### Đổi cuộc chơi 3: QA hard gate dựa trên package parts

Không cho pass nếu thiếu bất kỳ scaffold bắt buộc nào:

- DOCX: TOC, list-of-figures, header/footer, section count tối thiểu
- PPTX: slide master/layout/theme
- XLSX: named ranges/table/chart/pivot bindings

### Đổi cuộc chơi 4: Sinh visual snapshot cho QA

Anthropic khuyến nghị dùng visual analysis khi layout quan trọng. Với Office artifact, nên có bước render hoặc screenshot preview để QA so sánh hình thức, ít nhất ở mức:

- số trang / số slide / số sheet
- vị trí TOC / cover / list-of-figures
- presence của heading và spacing lớn

### Đổi cuộc chơi 5: Tách hẳn reference skill khỏi orchestration skill

`officecli-reference` chỉ chứa lệnh.

`office-preserve-structure` mới là skill chính cho tác vụ compliance. Điều này phù hợp cả Anthropic best practices lẫn OpenCode discovery.

## Khuyến nghị thực thi cho repo này

### Nên làm ngay

1. Thêm mode `preserve-template-scaffold` vào skill orchestrator và `task.md`.
2. Thêm schema `preserve`, `replace_ranges`, `post_conditions` vào run plan.
3. Nâng `profile_template.py` để detect front matter, TOC, list-of-figures, section breaks.
4. Thay logic build từ "clear body" sang "replace bounded ranges".
5. Nâng `qa_docx.py` từ text QA lên package-part QA.

### Nên làm sau đó

1. Tạo skill chung cho Office compliance thay vì tách theo từng extension đơn thuần.
2. Chuẩn hóa pattern tương tự cho PPTX và XLSX.
3. Bổ sung eval set có template khó, nhiều field, nhiều section.

### Không nên làm nữa

1. Không tiếp tục tin `validate pass` là đủ.
2. Không tiếp tục dùng text extract làm chỉ báo fidelity chính.
3. Không tiếp tục để model tự quyết định vùng nào cần xóa nếu task chưa khai báo anchor.

## Phán đoán cuối cùng

Các cải tiến mình làm trước đây là đúng hướng ở tầng architecture, nhưng chưa đủ để tạo ra đầu ra Office chất lượng cao. Lý do là chúng mới dừng ở:

- routing tốt hơn
- hard gate tốt hơn
- scaffold pipeline

chứ chưa chạm vào 2 thứ quyết định nhất:

1. semantics đúng của mode preserve-format
2. engine/QA thật ở cấp Open XML structure

Nếu muốn repo này tạo khác biệt thực sự, bước tiếp theo không phải viết thêm prompt, mà là thiết kế lại execution contract quanh `preserve-template-scaffold` rồi cắm build/qa engine tương ứng.