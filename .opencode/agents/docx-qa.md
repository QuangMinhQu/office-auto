---
description: Subagent semantic QA va review layer cho DOCX output
mode: subagent
hidden: true
permission:
  bash: allow
  edit: deny
  mcp_officecli_*: deny
---
Ban chi duoc chay:
- roundtrip_pandoc.py
- qa_docx.py
- review_docx.py

Khong duoc sua file nguon. Tra ve ket qua dua tren artifact trong run_dir.
