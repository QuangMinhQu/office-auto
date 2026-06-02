---
name: docx-mcp-tools
description: Wrapper toolset for invoking DOCX pipeline scripts as callable OpenCode custom tools.
license: MIT
---

# SKILL: DOCX_MCP_TOOLS

## Muc tieu
Cung cap bo tool callable de agent dieu phoi pipeline ma khong can compose shell command dai trong prompt.

## Cac tool chinh
- `docx_pipeline_profileTemplate`
- `docx_pipeline_buildDocx`
- `docx_pipeline_qaDocx`
- `docx_pipeline_runFullPipeline`

## Contract
- Tool duoc dinh nghia tai `.opencode/tools/docx_pipeline.ts`.
- Script runtime la Python, execute qua Bun spawn.
- Tra ve JSON text gom `status`, `failed_step` (neu co), stdout/stderr cho debug.
- Khong goi truc tiep OfficeCLI MCP tools.

## Khi nao dung skill nay
- Can chia workflow profile/build/qa thanh cac action typed va co argument schema.
- Can de orchestrator agent retry co dieu kien theo tung pha.

## Luu y
- Neu run fail, doc artifact trong `run_dir` de xac dinh root cause truoc khi retry.
- Neu `plan.json` blocked thi khong duoc force build.
