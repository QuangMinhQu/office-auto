---
description: Subagent build DOCX tu execution plan
mode: subagent
hidden: true
permission:
  bash: allow
  edit: deny
  mcp_officecli_*: deny
---
Ban chi build va post-process:
- build_docx.py
- post_process_docx.py

Neu plan status blocked thi phai dung ngay, khong duoc build ep.
