---
name: officecli-docx
description: "Skill tham chiếu cú pháp OfficeCLI cho DOCX. Chỉ load khi cần lệnh, schema element, prop name hoặc quy tắc thao tác OfficeCLI cụ thể; không dùng làm orchestrator mặc định cho mọi tác vụ .docx."
---

# SKILL: OFFICECLI_DOCX

## Mục tiêu
Skill này là entrypoint ngắn để tra cứu cú pháp OfficeCLI cho `.docx`.

Không dùng skill này làm workflow chính cho mọi tác vụ Word.
Workflow điều phối nằm ở `docx-from-template`.
Pipeline file-state nằm ở `md-to-docx-pipeline`.

## Khi nào cần load
- Khi cần lệnh `officecli` cụ thể.
- Khi chưa chắc `prop`, `type`, `path`, `field`, `numId`, `ilvl` hoặc schema element.
- Khi cần quy tắc resident mode, batch mode, live preview, hoặc cách kiểm tra field/TOC/footer bằng OfficeCLI.

## Khi nào không cần load
- Chỉ để quyết định mode `rebuild`, `append`, `fill-template`, `hybrid`.
- Chỉ để đọc task và lên kế hoạch pipeline.
- Khi script pipeline đã có artifact JSON đủ dùng và không cần command chi tiết.

## Quy tắc bắt buộc

### 1. Help-first
Khi không chắc cú pháp, phải hỏi help trước khi đoán:

```bash
officecli --version
officecli help docx
officecli help docx <element>
officecli help docx <verb> <element>
officecli help docx <element> --json
```

Với mutation, đây là hard rule:
- Trước mỗi `officecli add` hoặc `officecli set`, nếu chưa chắc schema, phải chạy `officecli help docx <element> --json`.
- Nếu agent đã có một MCP server OfficeCLI thật, ưu tiên MCP tool calls tương đương thay vì shell.

### 2. Kỷ luật shell
- Luôn quote đường dẫn semantic path như `"/body/p[1]"`.
- Nếu text có `$`, dùng single quote cho giá trị text.
- Không tự viết `\n`, `\t`, `\$` vào nội dung sẽ chèn.

### 3. Kỷ luật thực thi
- Mở file bằng `officecli open` và đóng bằng `officecli close` trong cùng terminal.
- Với multi-step mutation lớn, ưu tiên resident mode hoặc một `batch` JSON array duy nhất, không xen kẽ nhiều open/close rời rạc.
- Sau thao tác cấu trúc, kiểm tra lại bằng `get` hoặc `view` trước khi chồng thêm lệnh.
- Không dump toàn bộ document vào context nếu chỉ cần outline hoặc một nhánh nhỏ.
- Sau `close`, kiểm tra lại bằng `view stats` hoặc `validate`.

## Thứ tự tra cứu
1. Đọc skill này để biết nên tra cứu nhóm nào.
2. Mở file tham chiếu tương ứng trong `references/`.
3. Nếu vẫn chưa chắc, chạy `officecli help ...` và lấy đúng cú pháp theo version đang cài.

## Danh mục tham chiếu
- `references/view-query.md`: `view`, `query`, `get`, cách orient tài liệu.
- `references/elements.md`: paragraph, run, table, image, section.
- `references/styles-numbering.md`: styles, numbering, `numId`, `ilvl`.
- `references/fields-toc-refs.md`: TOC, field, references, cross-reference.
- `references/page-header-footer.md`: section, page setup, header/footer, page number.
- `references/batch-resident.md`: resident mode, batch mode, execution discipline.
- `references/raw-l3.md`: `raw`, `raw-set`, `add-part`, guardrail L3.

## Boundary
Nếu task chủ yếu là parse Markdown, profile template, mapping hoặc build qua artifact JSON, hãy quay lại `md-to-docx-pipeline` thay vì nhồi thêm command detail vào prompt.
