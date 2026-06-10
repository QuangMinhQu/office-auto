---
name: md-to-docx-pipeline
description: Deterministic DOCX compiler pipeline — LLM decides mapping, scripts compile.
license: MIT
---

# SKILL: MD_TO_DOCX_PIPELINE

## Triết lý (updated v3)

> **LLM là não cho quyết định mơ hồ; Scripts là tay cho thao tác chính xác; Final gate là code, không phải lời nhắc trong prompt.**

Trong bài toán "lấy markdown đã chia level → đổ vào template DOCX, giữ phần mặc định ít thay đổi":
- LLM **không** copy nội dung.
- LLM **không** sinh hàng trăm ops.
- LLM chỉ quyết định: vùng thay thế, mapping style, exception handling, review.
- Phần còn lại là compiler/script deterministic.

## Trình tự chạy (v3 — deterministic compiler)

```
1. docx_inspect.py        → dump raw template (NO LLM)
2. source_packet.py       → mechanical markdown AST (NO LLM)
3. [LLM/Mapper]           → decide style_map.json + replace_range.json (ONLY ambiguous decisions)
4. source_packet_to_ops.py → deterministic compile AST → execution_ops.json (NO LLM)
5. validate_ops_strict.py → hard-block validation (CODE, not prompt)
6. execute_execution_ops.py → mechanical executor (NO LLM)
7. verify_docx_output.py  → readback + coverage verification (NO LLM)
8. qa_docx.py             → QA metrics (NO LLM)
9. review_docx.py         → semantic review (LLM optional)
10. docx_refresh_fields.py → TOC/field refresh (NO LLM)
11. final_gate.py          → CODE-LEVEL final gate (NO LLM, NO prompt)
```

## Artifacts (v3)
| File | Mô tả | Sinh bởi |
|---|---|---|
| `docx_inspect_output.json` | Full template inspection | `docx_inspect.py` |
| `docx_inspect_styles_for_llm.json` | Compact style summary | `docx_inspect.py` |
| `docx_inspect_content_map.json` | Front-matter/body anchor map | `docx_inspect.py` |
| `insert_plan_scaffold.json` | Aggregated scaffold | MCP tool `scaffold` |
| `source_packet.json` | Mechanical markdown AST (typed blocks + SHA-256) | `source_packet.py` |
| `style_map.json` | LLM quyết định: markdown level → DOCX style_id | MapperAgent (hoặc mặc định) |
| `replace_range.json` | LLM quyết định: insert anchor + remove paths | MapperAgent (hoặc mặc định) |
| `execution_ops.json` | Deterministic compiled ops | `source_packet_to_ops.py` |
| `strict_validation.json` | Hard-block validation report | `validate_ops_strict.py` |
| `execution_ops_validation.json` | Warn-only validation + planning report | `docx_validate_ops.py` |
| `planning_report.json` | Coverage report (heading/body/remove counts) | `docx_validate_ops.py` |
| `execute_ops_report.json` | Execution summary | `execute_execution_ops.py` |
| `result_readback.json` | Output DOCX readback | `docx_read_result.py` |
| `coverage_report.json` | Source block coverage verification | `verify_docx_output.py` |
| `qa_report.json` | QA metrics | `qa_docx.py` |
| `review_report.json` | Semantic review | `review_docx.py` |
| `post_process_report.json` | TOC/field refresh report | `docx_refresh_fields.py` |
| `final_gate.json` | CODE-LEVEL final gate verdict | `final_gate.py` |
| `run.json` | Atomic state machine | MCP tools |

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

## Invariant (v3)

1. First insert op always has explicit paraId-based anchor (never PREVIOUS)
2. All subsequent insert ops use PREVIOUS
3. Remove ops target only body_placeholders (never front_matter)
4. Remove ops never target the first insert anchor
5. Remove ops use `path` (never `at`)
6. Every insert op has `source_block_id` and `source_text_sha256`
7. Text is COPIED VERBATIM (never paraphrased, never truncated)
8. Schema version is always "2"
9. Final gate is CODE, not prompt

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
