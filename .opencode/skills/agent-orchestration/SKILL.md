---
name: agent-orchestration
description: Two-layer OpenCode agent topology for DOCX pipeline with retry-safe dispatch.
license: MIT
---

# SKILL: AGENT_ORCHESTRATION

## Topology
- Primary: `orchestrator`
- Subagents (hidden): `docx-profiler`, `docx-builder`, `docx-qa`

## Routing
1. `docx-profiler`: profile + parse + planning + compile execution plan
2. `docx-builder`: build + post process
3. `docx-qa`: roundtrip + qa + review

## Retry contract
- Primary bắt buộc đọc artifact status sau mỗi phase.
- Nếu phase fail, re-dispatch đúng subagent với context bổ sung.
- Không chốt complete nếu chưa có `qa_report.json` status passed.

## Permission contract
- Tất cả agents: `mcp_officecli_*: deny`
- OfficeCLI chỉ được dùng qua bash commandline/custom tools wrappers.

## Session memory
- Bootstrap context qua:
  - `.opencode/memory/project.md`
  - `.opencode/memory/task_current.md`
- Cập nhật `task_current.md` sau mỗi phase để resumable/
