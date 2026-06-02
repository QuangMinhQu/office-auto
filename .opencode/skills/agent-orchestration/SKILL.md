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
- Primary bat buoc doc artifact status sau moi phase.
- Neu phase fail, re-dispatch dung subagent voi context bo sung.
- Khong chot complete neu chua co `qa_report.json` status passed.

## Permission contract
- Tat ca agents: `mcp_officecli_*: deny`
- OfficeCLI chi duoc dung qua bash commandline/custom tools wrappers.

## Session memory
- Bootstrap context qua:
  - `.opencode/memory/project.md`
  - `.opencode/memory/task_current.md`
- Cap nhat `task_current.md` sau moi phase de resumable.
