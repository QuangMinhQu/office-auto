---
name: officecli-pptx
description: "Skill tham chiếu cú pháp OfficeCLI cho PPTX. Chỉ load khi cần lệnh, schema element, prop name, path hoặc execution rule cụ thể; không dùng làm orchestrator mặc định cho mọi tác vụ presentation."
---

# SKILL: OFFICECLI_PPTX

## Mục tiêu
Skill này là entrypoint ngắn để tra cứu cú pháp OfficeCLI cho `.pptx`.

Không dùng skill này làm workflow chính cho mọi tác vụ presentation.
Skill chỉ nên được load khi cần xác nhận lệnh, schema hoặc execution discipline ở mức OfficeCLI.

## Khi nào cần load
- Khi cần lệnh `officecli` cụ thể cho `slide`, `shape`, `textbox`, `picture`, `table`, `chart`, `notes`, `layout` hoặc `master`.
- Khi chưa chắc `prop`, `type`, `path`, placeholder binding hoặc selector query cua presentation.
- Khi cần quy tắc resident mode, batch mode, live preview, watch server hoặc guardrail L3 cho `.pptx`.

## Khi nào không cần load
- Chỉ để đọc task thô hoặc lên kế hoạch pipeline high-level.
- Chỉ để parse Markdown, profile scaffold hoặc sinh artifact JSON mà chưa cần command chi tiết.
- Khi workflow khac da sinh du `content_ast`, `content_outline`, `template_profile`, `plan` va QA artifact va khong can tra cuu cu phap OfficeCLI.

## Quy tắc bắt buộc

### 1. Help-first
Khi không chắc cú pháp, phải hỏi help trước khi đoán:

```bash
officecli --version
officecli help pptx
officecli help pptx <element>
officecli help pptx <verb> <element>
officecli help pptx <element> --json
```

Với mutation, đây là hard rule:
- Trước mỗi `officecli add` hoặc `officecli set`, nếu chưa chắc schema, phải chạy `officecli help pptx <element> --json`.
- Nếu agent đã có OfficeCLI MCP server, ưu tiên MCP tool calls tương đương thay vì shell.

### 2. Kỷ luật shell
- Luôn quote file path và semantic path như `"/slide[1]/shape[2]"`.
- Nếu text co dau `$`, ngoac hoac ky tu dac biet, dung single quote cho gia tri text.
- Khong chen path dang selector CSS-like vao shell ma khong quote.
- Khi target la placeholder hoac layout-derived shape, profile bang `get` hoac `query` truoc roi moi mutate.

### 3. Kỷ luật thực thi
- Mở file bằng `officecli open` và đóng bằng `officecli close` trong cùng terminal.
- Với multi-step mutation lớn, ưu tiên resident mode hoặc một `batch` JSON array duy nhất.
- Sau thao tác cấu trúc như add slide, reorder, remap layout, insert chart/media hoặc đổi placeholder text, kiểm tra lại bằng `get`, `view` hoặc `query` trước khi chồng thêm lệnh.
- Không dump toàn bộ presentation vào context nếu chỉ cần title slide, một layout hoặc một slide branch.
- Sau `close`, kiểm tra lại bằng `view`, `query`, `validate` hoặc preview artifact tùy workflow.

## Thứ tự tra cứu
1. Đọc skill này để biết nên tra cứu nhóm nào.
2. Mở file tham chiếu tương ứng trong `references/`.
3. Nếu vẫn chưa chắc, chạy `officecli help ...` và lấy đúng cú pháp theo version đang cài.

## Danh mục tham chiếu
- `references/view-query.md`: `view`, `get`, `query`, slide tree, selector engine, placeholder resolution.
- `references/elements.md`: slide, shape, picture, table, chart, textbox, group, connector, 3D model, zoom.
- `references/text-formatting.md`: paragraph, run, bullet/numbering, rich text, placeholder text.
- `references/visual-properties.md`: fill, outline, effects, transform, z-order, color resolution.
- `references/layouts-masters.md`: layouts, masters, theme, placeholder inheritance, slide size.
- `references/animations-transitions.md`: animations, timing, transitions, morph.
- `references/notes-media.md`: notes, audio, video, playback, hyperlinks.
- `references/batch-resident.md`: resident mode, batch mode, live preview, watch server.
- `references/raw-l3.md`: `raw`, `raw-set`, `add-part`, relationship migration, guardrail L3.
- `references/core.md`: quick ops legacy cheat sheet.

## Boundary
Neu task chu yeu la profile scaffold, resolve `replace_ranges`, lap `slide-to-layout mapping` hoac chay QA package/semantic, dung workflow pipeline de dieu phoi. Chi load skill nay khi can quyet dinh cu phap OfficeCLI that su.
