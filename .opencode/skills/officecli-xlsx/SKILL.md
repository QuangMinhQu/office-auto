---
name: officecli-xlsx
description: "Skill tham chiếu cú pháp OfficeCLI cho XLSX. Chỉ load khi cần lệnh, schema element, prop name, path hoặc execution rule cụ thể; không dùng làm orchestrator mặc định cho mọi tác vụ spreadsheet."
---

# SKILL: OFFICECLI_XLSX

## Mục tiêu
Skill này là entrypoint ngắn để tra cứu cú pháp OfficeCLI cho `.xlsx`.

Không dùng skill này làm workflow chính cho mọi tác vụ spreadsheet.
Skill chỉ nên được load khi cần xác nhận lệnh, schema hoặc execution discipline ở mức OfficeCLI.

## Khi nào cần load
- Khi cần lệnh `officecli` cụ thể cho `sheet`, `row`, `column`, `cell`, `table`, `formula`, `chart` hoặc `pivot`.
- Khi chưa chắc `prop`, `type`, `path`, Excel notation hay selector query của workbook.
- Khi cần quy tắc resident mode, batch mode hoặc guardrail L3 cho `.xlsx`.

## Khi nào không cần load
- Chỉ để đọc task thô hoặc lên kế hoạch pipeline high-level.
- Chỉ để parse, map dữ liệu hoặc chuẩn bị artifact JSON mà chưa cần command chi tiết.
- Khi workflow khác đã sinh đủ `content_ast`, `template_profile`, `plan` hoặc QA artifact và không cần tra cứu cú pháp OfficeCLI.

## Quy tắc bắt buộc

### 1. Help-first
Khi không chắc cú pháp, phải hỏi help trước khi đoán:

```bash
officecli --version
officecli help xlsx
officecli help xlsx <element>
officecli help xlsx <verb> <element>
officecli help xlsx <element> --json
```

Với mutation, đây là hard rule:
- Trước mỗi `officecli add` hoặc `officecli set`, nếu chưa chắc schema, phải chạy `officecli help xlsx <element> --json`.
- Nếu agent đã có OfficeCLI MCP server, ưu tiên MCP tool calls tương đương thay vì shell.

### 2. Kỷ luật shell
- Luôn quote file path và semantic path như `"/Sheet1/row[1]/cell[1]"`.
- Nếu dùng Excel notation như `Sheet1!A1:D10`, vẫn phải quote toàn bộ đối số để tránh shell tách ký tự đặc biệt.
- Nếu text hoặc formula có `$`, khoảng trắng hoặc `>`, dùng single quote cho giá trị.
- Không trộn path notation và Excel notation trong cùng một đối số nếu chưa kiểm tra help trước.

### 3. Kỷ luật thực thi
- Mở file bằng `officecli open` và đóng bằng `officecli close` trong cùng terminal.
- Với multi-step mutation lớn, ưu tiên resident mode hoặc một `batch` JSON array duy nhất.
- Sau thao tác cấu trúc như thêm sheet, table, chart, pivot hoặc merge cells, kiểm tra lại bằng `get`, `view` hoặc `query` trước khi chồng thêm lệnh.
- Không dump toàn bộ workbook vào context nếu chỉ cần một sheet, range hoặc branch nhỏ.
- Sau `close`, kiểm tra lại bằng `view`, `get`, `query` hoặc `validate` tùy workflow.

## Thứ tự tra cứu
1. Đọc skill này để biết nên tra cứu nhóm nào.
2. Mở file tham chiếu tương ứng trong `references/`.
3. Nếu vẫn chưa chắc, chạy `officecli help ...` và lấy đúng cú pháp theo version đang cài.

## Danh mục tham chiếu
- `references/view-query.md`: `view`, `get`, `query`, workbook tree, named range, sparse cells.
- `references/elements.md`: sheet, row, column, cell, table, chart, picture, shape, pivot table.
- `references/formulas-functions.md`: formula, named formula, array formula, lỗi công thức.
- `references/styles-formatting.md`: font, fill, border, alignment, number format, conditional formatting.
- `references/data-operations.md`: import/export, sort, filter, data validation, find/replace.
- `references/advanced-features.md`: freeze panes, protection, comments, hyperlinks, page setup.
- `references/batch-resident.md`: resident mode, batch mode, execution discipline, rollback.
- `references/raw-l3.md`: `raw`, `raw-set`, `add-part`, schema ordering, guardrail L3.
- `references/core.md`: quick ops legacy cheat sheet.

## Boundary
Nếu task chủ yếu là parse dữ liệu, map workbook hoặc lập kế hoạch pipeline, đừng nhồi command detail vào prompt. Chỉ load skill này khi cần quyết định cú pháp OfficeCLI thật sự.
