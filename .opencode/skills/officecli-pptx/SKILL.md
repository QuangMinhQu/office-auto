---
name: officecli-pptx
description: Skill tham chiếu nhanh cho OfficeCLI với `.pptx`. Dùng khi task đụng slide, shape, textbox, image, notes hoặc layout trình chiếu.
---

# SKILL: OFFICECLI_PPTX

## Khi nào load
- Task thao tác `.pptx`.
- Cần đọc/ghi slide, shape, textbox, image.
- Cần kiểm slide order, placeholder hoặc layout trước khi mutate.

## Quy tắc
- Bắt đầu bằng `officecli --version` nếu execution path cần OfficeCLI.
- Nếu chưa chắc schema, dùng `officecli help pptx <element> --json` hoặc `officecli help pptx <verb> <element>`.
- Với mutation nhiều bước, ưu tiên resident mode hoặc batch mode.
- Nếu OfficeCLI MCP đã đăng ký, ưu tiên MCP tool calls.

## Tham chiếu
- `references/core.md`
