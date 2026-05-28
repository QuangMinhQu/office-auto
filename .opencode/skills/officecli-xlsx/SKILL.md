---
name: officecli-xlsx
description: Skill tham chiếu nhanh cho OfficeCLI với `.xlsx`. Dùng khi task đụng sheet, row, cell, formula, style hoặc import/export dữ liệu bảng tính.
---

# SKILL: OFFICECLI_XLSX

## Khi nào load
- Task thao tác `.xlsx`.
- Cần đọc/ghi cell, row, formula, style hoặc import CSV/TSV vào workbook.
- Cần query workbook structure trước khi mutate.

## Quy tắc
- Bắt đầu bằng `officecli --version` nếu execution path cần OfficeCLI.
- Nếu chưa chắc schema, dùng `officecli help xlsx <element> --json` hoặc `officecli help xlsx <verb> <element>`.
- Với mutation nhiều bước, ưu tiên resident mode hoặc batch mode.
- Nếu OfficeCLI MCP đã đăng ký, ưu tiên MCP tool calls.

## Tham chiếu
- `references/core.md`
