---
name: docx-mcp-tools
description: Wrapper toolset for invoking DOCX pipeline scripts as callable OpenCode custom tools.
license: MIT
---

# SKILL: DOCX_MCP_TOOLS

## Muc tieu
Cung cap bo primitive callable de agent reasoning DOCX ma khong can compose shell command dai trong prompt.

## Cac tool chinh
- `inspectTemplate`
- `validateExecutionOps`
- `applyExecutionOps`
- `prepareInsertPlan`
- `reviewOutput`
- `readResult`
- `runPipeline`

## Contract
- Tool duoc dinh nghia tai `.opencode/tools/docx_pipeline.ts`.
- Script runtime la Python, execute qua Bun spawn.
- Tra ve JSON text gom `status`, `failed_step` (neu co), artifact path va payload doc duoc khi phu hop.
- Khong goi truc tiep OfficeCLI MCP tools.

## Khi nao dung skill nay
- Can di theo kien truc moi: inspect raw -> LLM viet ops -> validate -> apply -> read result.
- Can de orchestrator agent retry co dieu kien theo tung primitive.

## Luu y
- Neu run fail, doc artifact trong `run_dir` de xac dinh root cause truoc khi retry.
- Neu validator ra warnings, sua `execution_ops.json` truoc khi apply.
