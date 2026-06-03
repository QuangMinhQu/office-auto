# Project Memory

- Workspace: office-auto
- Primary flow: new philosophy — scripts are hands, LLM is the brain
- Default architecture (issue.md):
    1. docx_inspect.py → raw dump (zero heuristics, zero interpretation)
    2. [LLM reasoning] → reads raw dump + content, writes execution_ops.json
    3. execute_execution_ops.py → mechanical executor
    4. qa_docx.py → metrics
    5. review_docx.py → summary
- Removed from default flow (Python was doing LLM's work):
    profile_template.py, plan_mapping.py, compile_execution_plan.py,
    prepare_template_scaffold.py, patch_template_profile(), template_suitability_report.py
- Style contract: heading paragraphs must keep style inheritance from template; avoid direct font/size overrides on heading roles.
- Tooling contract: do not call OfficeCLI MCP tools directly; use bash CLI or custom tools wrappers.
