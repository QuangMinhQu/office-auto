# Project Memory

- Workspace: office-auto
- Primary flow: preserve-template-scaffold for DOCX
- Default architecture: inspect template raw -> LLM writes execution_ops.json -> validate -> apply -> read result
- Style contract: heading paragraphs must keep style inheritance from template; avoid direct font/size overrides on heading roles.
- Roundtrip contract: use Pandoc DOCX->Markdown with docx+styles reader for semantic QA.
- Tooling contract: do not call OfficeCLI MCP tools directly; use bash CLI or custom tools wrappers.
