---
name: md-to-docx-pipeline
description: Deterministic DOCX compiler pipeline — durable workflow + event-sourced state + subagent contracts.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE (v3.1 — Durable Workflow)

## Triết lý (v3.1)

> **LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code, không phải lời nhắc trong prompt. Events.jsonl là nguồn sự thật duy nhất. run.json chỉ là snapshot derived từ events.**

Trong bài toán "lấy markdown đã chia level → đổ vào template DOCX, giữ phần mặc định ít thay đổi":
- LLM **không** copy nội dung.
- LLM **không** sinh hàng trăm ops.
- LLM chỉ quyết định: vùng thay thế, mapping style, exception handling, review.
- Phần còn lại là compiler/script deterministic.
- State không bao giờ bị mất — events.jsonl lưu toàn bộ lịch sử, có thể replay.
- Có thể resume từ bất kỳ điểm nào sau crash.

## Cách dùng (v3.1)

### Default path — Agent phải gọi `createReportFromMarkdown`

```
agent → call createReportFromMarkdown (MCP tool)
  → PipelineSupervisor điều phối graph
  → từng subagent chạy, emit event, tạo artifact
  → final gate code-level quyết định pass/fail
```

### KHÔNG BAO GIỜ gọi trực tiếp các tool thấp cấp

Các tool như `inspectTemplate`, `generateOpsFromSourcePacket`, `applyOps`, `runQA`,... chỉ là internal activities. Gọi trực tiếp sẽ bỏ qua transition guard, event log, và state consistency.

### Resume after crash

```
agent → call resumeReportRun (MCP tool)
  → replay events.jsonl để xác định phase hiện tại
  → verify artifact checksums
  → continue từ phase tiếp theo
```

### Inspect run state

```
agent → call inspectRun (MCP tool)
  → trả về phase, status, artifacts, checks, errors
```

## Trình tự chạy (v3.1 — durable workflow graph)

```
CREATE_RUN
  → INSPECT_TEMPLATE (TemplateInspectorAgent — code-only)
  → PARSE_SOURCE (SourceParserAgent — code-only)
  → MAP_INSERTION (MapperAgent — LLM decision)
  → COMPILE_OPS (CompilerAgent — code-only)
  → VALIDATE_OPS (ValidatorAgent — code-only)
  → APPLY_DOCX (ExecutorAgent — code-only)
  → VERIFY_OUTPUT (VerifierAgent — code-only)
  → QA (QAAgent — code-only)
  → REVIEW (ReviewerAgent — LLM optional)
  → REFRESH_FIELDS (PostProcessorAgent — code-only)
  → FINAL_GATE (FinalGateAgent — code-only)
  → COMPLETE / FAILED
```

### State management

- **events.jsonl** = append-only event log, source of truth
- **run.json** = derived snapshot, rebuilt from events by reducer
- **artifacts.json** = artifact manifest with SHA256 checksums
- **lock** = run-level mutex, chống concurrent execution
- Mỗi phase transition có guard (transitions.ts)
- Mỗi artifact có checksum + producer + phase
- Retry idempotent (cùng idempotency_key + checksum match → skip)

## Artifacts (v3.1 — with manifest + checksum)

| File | Mô tả | Sinh bởi | Phase |
|---|---|---|---|
| `docx_inspect_output.json` | Full template inspection | `docx_inspect.py` | inspected |
| `docx_inspect_styles_for_llm.json` | Compact style summary | `docx_inspect.py` | inspected |
| `docx_inspect_content_map.json` | Front-matter/body anchor map | `docx_inspect.py` | inspected |
| `insert_plan_scaffold.json` | Aggregated scaffold | MapperAgent | mapped |
| `source_packet.json` | Mechanical markdown AST (typed blocks + SHA-256) | `source_packet.py` | source_parsed |
| `style_map.json` | LLM quyết định: markdown level → DOCX style_id | MapperAgent | mapped |
| `replace_range.json` | LLM quyết định: insert anchor + remove paths | MapperAgent | mapped |
| `execution_ops.json` | Deterministic compiled ops | `source_packet_to_ops.py` | compiled |
| `strict_validation.json` | Hard-block validation report | `validate_ops_strict.py` | validated |
| `execution_ops_validation.json` | Warn-only validation + planning report | `docx_validate_ops.py` | validated |
| `planning_report.json` | Coverage report (heading/body/remove counts) | `docx_validate_ops.py` | validated |
| `execute_ops_report.json` | Execution summary | `execute_execution_ops.py` | applied |
| `result_readback.json` | Output DOCX readback | `docx_read_result.py` | verified |
| `coverage_report.json` | Source block coverage verification | `verify_docx_output.py` | verified |
| `qa_report.json` | QA metrics | `qa_docx.py` | qa_passed |
| `review_report.json` | Semantic review | `review_docx.py` | reviewed |
| `post_process_report.json` | TOC/field refresh report | `docx_refresh_fields.py` | refreshed |
| `final_gate.json` | CODE-LEVEL final gate verdict | `final_gate.py` | final_gate |
| `events.jsonl` | Append-only event log (source of truth) | PipelineSupervisor + agents | all |
| `artifacts.json` | Artifact manifest with SHA256 checksums | State layer | all |
| `run.json` | Derived snapshot (cache, rebuilt from events) | Reducer | all |
| `lock` | Run-level mutex file | Lock manager | all |

## LLM Reasoning Chain (v3 — simplified)

### Chỉ 2 quyết định LLM cần đưa ra:

#### 1. Style map
```json
{
  "h1": "<style_id from heading_map.h1>",
  "h2": "<style_id from heading_map.h2>",
  "h3": "<style_id from heading_map.h3>",
  "body": "<body_text_style>",
  "caption": "<caption_style if available, else body>",
  "preserve_zones": ["front_matter", "toc", "headers_footers"]
}
```

#### 2. Replace range
```json
{
  "insert_after_path": "/body/p[@paraId=49349C0D]",
  "remove_paths": [
    "/body/p[@paraId=PLACEHOLDER1]",
    "/body/p[@paraId=PLACEHOLDER2]"
  ],
  "remove_rule": "remove all body placeholders not in front_matter"
}
```

### Không còn:
- ❌ LLM copy 125 blocks thành 125 JSON ops
- ❌ LLM sinh `execution_ops.json` dài hàng KB
- ❌ Planner với `steps: 8` và hard limits 80 ops
- ❌ Chunking content vì sợ context không xử lý nổi

## Invariant (v3.1 — durable workflow)

### State invariants
1. **events.jsonl is source of truth** — run.json is derived snapshot, never directly mutated
2. **Every state transition has a guard** — assertTransitionAllowed() blocks invalid transitions
3. **Every artifact has a manifest entry with SHA256** — no dangling files
4. **Event first, snapshot second** — append event → reduce → write run.json
5. **Subagents only emit events, never mutate state directly**
6. **Lock prevents concurrent execution** — acquireRunLock before any mutation
7. **Retry is idempotent** — same idempotency_key + matching checksum → skip re-execution

### Compilation invariants
8. First insert op always has explicit paraId-based anchor (never PREVIOUS)
9. All subsequent insert ops use PREVIOUS
10. Remove ops target only body_placeholders (never front_matter)
11. Remove ops never target the first insert anchor
12. Remove ops use `path` (never `at`)
13. Every insert op has `source_block_id` and `source_text_sha256`
14. Text is COPIED VERBATIM (never paraphrased, never truncated)
15. Schema version is always "2"
16. Final gate is CODE, not prompt

### Agent invariants
17. Subagent must not modify run.json directly
18. Subagent must not decide the next phase (supervisor routes)
19. Subagent only creates artifacts in its own namespace
20. Subagent must emit events for all side effects
21. Subagent must be idempotent given same idempotency_key

## Public API (v3.1)

### `createReportFromMarkdown` — default path, always use this
```json
{
  "template_file": "...",
  "source_file": "...",
  "target_file": "...",
  "strict": true,
  "require_review": false,
  "log_level": "brief"
}
```

### `resumeReportRun` — resume after crash
```json
{
  "run_dir": ".office-auto/state/20260610_..."
}
```

### `inspectRun` — read current state (read-only)
```json
{
  "run_dir": ".office-auto/state/20260610_..."
}
```

### `retryFailedPhase` — retry a failed phase
```json
{
  "run_dir": ".office-auto/state/20260610_...",
  "phase": "applying"
}
```

### `abortRun` — mark as failed + release lock
```json
{
  "run_dir": ".office-auto/state/20260610_...",
  "reason": "User cancelled"
}
```

## Contract scripts

### `docx_inspect.py`
Raw dump ONLY. No heuristics, no pre-classification. LLM receives raw data for style_map decisions.

### `source_packet.py`
Mechanical markdown block splitter. Types are PURELY syntax-driven (heading, paragraph, caption_candidate, list_item, empty_line). Zero semantics.

### `source_packet_to_ops.py` (NEW — critical)
**Deterministic compiler.** Takes AST + style_map + replace_range → produces execution_ops.json.
- Strips `#` from headings
- Copies text VERBATIM
- Assigns anchor/PREVIOUS mechanically
- Adds source_block_id + hash for traceability
- Appends remove ops after all insert ops

### `validate_ops_strict.py` (NEW — blocking)
**Hard-block validator.** Exit code 1 on high severity errors.
Checks invariants: first anchor explicit, no duplicate blocks, no front_matter removes, no unsupported ops, no `at` in remove ops.

### `docx_validate_ops.py`
Warn-only validator. Still runs for planning_report.json and detailed diagnostics.
Used alongside strict validator but does NOT block apply.

### `execute_execution_ops.py`
Mechanical executor. Reads execution_ops.json, applies ops via OfficeCLI.

### `verify_docx_output.py` (NEW)
Readback + coverage verification. Checks every source_block text appears in output.
Replaces the manual QA step for content coverage.

### `final_gate.py` (NEW — CODE-LEVEL)
Checks ALL required artifacts exist and pass quality thresholds.
Returns `passed: true` only if every check succeeds.
Replaces the prompt-based final gate in orchestrator.md.

## Skeleton Pipeline Config

When template > 500 paragraphs, pipeline automatically enables skeleton mode.
LLM does NOT need to know this — artifact structure is identical.

## Fallback Protocol: all_para_ids empty

1. Check `paragraph_sample` — use `IDX_{body_start_index:05d}` as first anchor
2. After first op → `"anchor": "PREVIOUS"` for all subsequent ops
3. If no anchor is resolvable → abort with explicit error
