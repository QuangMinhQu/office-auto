---
name: docx-mcp-tools
description: Wrapper toolset for invoking DOCX pipeline scripts as MCP tools via office-auto server.
license: MIT
---

# SKILL: DOCX_MCP_TOOLS

## Muc tieu
Cung cap bo primitive callable de agent reasoning DOCX ma khong can compose shell command dai trong prompt.
Bo tool nay duoc expose qua MCP server `office-auto`.

## Cac tool chinh
- `inspectTemplate` — Run docx_inspect.py, return compact inspection
- `validateOps` — Validate execution_ops.json (warn-only)
- `applyOps` — Execute ops on target DOCX
- `runQA` — Run quality checks on built DOCX
- `reviewOutput` — Compare built DOCX vs source markdown
- `refreshFields` — Refresh TOC/field codes via LibreOffice or mark-dirty
- `runFullPipeline` — Orchestrate full pipeline from inspect → refresh
- `prepareInsertPlan` — Aggregate inspection + markdown into planning scaffold

## Contract
- All tools defined in `mcp/office-auto-server.ts` and `mcp/tools/*.ts`.
- Script runtime la Python, execute qua spawn.
- Tra ve JSON text gom `ok`, artifact paths, va payload doc duoc khi phu hop.

## Khi nao dung skill nay
- Can di theo kien truc moi: inspect → LLM writes ops → validate → apply → QA → review → refresh.
- Can retry co dieu kien theo tung primitive.

## Luu y
- Neu run fail, doc artifact trong `run_dir` de xac dinh root cause truoc khi retry.
- Neu validator ra warnings, sua `execution_ops.json` truoc khi apply.
- Moi tool nhan `run_dir` va return structured JSON.
