---
name: officecli-mcp
description: Thiết lập OfficeCLI MCP, cài base skills cho agent và ưu tiên native tool calling thay vì shell subprocess khi môi trường đã sẵn sàng.
---

# SKILL: OFFICECLI_MCP

## Mục tiêu
Skill này dùng khi cần đăng ký OfficeCLI với agent, cài base skill OfficeCLI hoặc chuẩn hóa môi trường chạy native.

## Lệnh thật của version hiện tại

```bash
officecli mcp list
officecli mcp vscode
officecli mcp uninstall vscode
officecli skills list
officecli skills install
officecli skills install word opencode
officecli skills install excel opencode
officecli skills install pptx opencode
officecli install opencode
```

## Quy tắc
- Nếu agent hiện tại đã có MCP registration phù hợp, ưu tiên tool calls thay vì shell command.
- `officecli install <target>` là đường one-step khi cần binary + skills + MCP đồng bộ một lần.
- Với repo này, base skill OfficeCLI cài từ binary không thay thế các skill tùy biến trong `.opencode/skills`; chúng bổ sung cho nhau.

## Cách nghĩ đúng
- MCP = execution path ưu tiên cho mutation Office.
- Shell = fallback khi agent chưa có MCP registration hoặc task là bootstrap chính môi trường.
- Không dùng cú pháp cũ kiểu `officecli --install-skill`; version hiện tại đi qua `officecli skills install ...`.