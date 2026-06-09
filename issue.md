Tôi đã đọc toàn bộ logic của repo. Dưới đây là phân tích sâu về **tại sao log có nhiều issue**.

***

# Root Cause Analysis: Office-Auto Pipeline Issues

## Issue #1: `spawn python3 ENOENT` — Nguyên nhân gốc rễ nghiêm trọng nhất

Log đầu tiên cho thấy: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/164711194/a173f3f6-586f-464a-a7fb-284be3b6584c/paste.txt?AWSAccessKeyId=ASIA2F3EMEYEXEMXG4BA&Signature=ugOfcldckmQo6c2AUa%2B%2BZ%2BnXW2E%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEAAaCXVzLWVhc3QtMSJHMEUCIHJibdr%2FIzQwB35bNieSC8nMRgjzYbBpIdxcuJzJJKL4AiEAz1vodt%2FCSugJ9vh%2FUFajvdeXCIw6pYa7bQZRpgnI8hMq%2FAQIyf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARABGgw2OTk3NTMzMDk3MDUiDAVWmn05d94MlviyXyrQBIaqbYLpf73xmuk2gU6rXUXYtFJrfCARUIMmpGdeMCzek9KDuuACrTrgrgWb0ZveT9IhWQtSQMfPPu8y2vgcr8JyIqhxNP1Kyl7kGrkLBi3lJC63RN02zaXzKpe8wDSup8t%2Bhag6C0mvVzaL9%2FoE8MbW9dt%2FSIVlYPpWvtHyAaSHsQseIMhJ0ESMEqrbSjo6R1UceE4kb%2Fe3aoa5Q7c63mkLmsbP3NrQNBYmdkhRu5%2BPliOXTonYZmOYJN26uIFJDNJiCrWx4aQkaXzvqDgKjEDFU3gs8v0d5Kvq8O%2FsrxaqpENyZ6U3dWaJac%2BBsym6L%2Bo2BxlYx5m4up0nhUpsVGxkCkIlALZ9zPfLwQqZ6DCoHEGO7Z89wnyKQszoYmhHzQYfE42xR760qL9okdSIlM8EhMq6I%2BAZOEgSaOtRp6sKQ6gHzI3akqB5Eu6qVFSksQSRnGaa4Cr0sBh9N44%2F9A%2F%2Bczraap2dyixdzzCbdYR%2FDkGYpJqF3f%2BsotJS6UQXUq%2FcQbGVdHbOdDQqcfIcRfk0%2BCztnqqQhjru9xoXFygAc0DeidaY%2FFH5JgtwoO%2FKMFBlAEsYrjm7spsz9Bpjrlvta6izL2o%2Ba4xBuj1L6tqHO31fNd5vZj3BxYvcJetHkF%2F%2B3%2BP5a9nrgF%2FXiUCuvYsT%2FEzKOO685mLJfoWG6vbHAtjUeZK6kw9LCL0EINhyEdpnSjY2CncTrOBN6Bqsn6NWTWS%2BIamBBjNI4wpU%2B0rIMueBLfG3cW8rOJ6KGytrsm40TwALvdIm1cXFcUL9DO4wwo%2Bf0QY6mAG0mwcwBd%2BPsluydQkXlirXAtRvyJX9fmnmjENDpvy%2B3ENebZWemKlSZrRRzuiWTmDqIa1T6yOfs0KWUw787Rtam%2FdmctXE0fqhILLoVLlttf4NTTq%2BomJp2KB%2BxsVruqGDy60NdZWlJKdn0%2F3UEt%2BreZIOQ5eJDZHWBfJRYO2UEaDJJfZxYfwuglnQSp1fZ%2FDX%2F%2FqNBjv9MQ%3D%3D&Expires=1780995477)

```
The office-auto_inspectTemplate tool failed with "spawn python3 ENOENT"
```

**Tại sao xảy ra?** Nhìn vào `pipeline-core.ts`, hàm `runScript` hardcode đường dẫn script như sau: 

```typescript
const scriptPath = `${worktree}/.opencode/skills/md-to-docx-pipeline/scripts/${script}`
const command = ["python3", scriptPath, ...args]
```

Hai vấn đề song song:
- **`python3` không tồn tại trong PATH** của môi trường runtime (opencode chạy trong Bun environment, không đảm bảo `python3` được resolve). Đây là lý do `ENOENT` — hệ thống không tìm thấy binary `python3`.
- **`office-auto_inspectTemplate`** là tên tool cũ (từ MCP server trực tiếp), trong khi đúng convention phải gọi `docx_pipeline_inspectTemplate` (custom tool wrapper). Agent đã tự fallback nhưng điều này cho thấy có **tool naming mismatch** giữa AGENTS.md và thực tế agent biết tên tool nào. 

***

## Issue #2: Agent Bỏ Qua Quy Tắc `AGENTS.md`

AGENTS.md quy định rõ: 

> **Không gọi trực tiếp** OfficeCLI MCP tools; luôn ưu tiên custom tools trong `.opencode/tools`

Nhưng log cho thấy agent đầu tiên thử gọi `office-auto_inspectTemplate` (MCP tool trực tiếp) thay vì `docx_pipeline_inspectTemplate`. Điều này xảy ra vì:
- **Model (Qwen3.6-35B-A3B-GGUF)** không đọc `AGENTS.md` đủ cẩn thận ở đầu session, hoặc không load memory `project.md`.
- AGENTS.md yêu cầu bước 1 là _"Đọc `.opencode/memory/project.md`"_ nhưng agent đã skip thẳng vào task. 

***

## Issue #3: Orchestrator bị Overload — "Building the document structure..." Loop

Phần log quan trọng nhất và nguy hiểm nhất: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/164711194/a173f3f6-586f-464a-a7fb-284be3b6584c/paste.txt?AWSAccessKeyId=ASIA2F3EMEYEXEMXG4BA&Signature=ugOfcldckmQo6c2AUa%2B%2BZ%2BnXW2E%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEAAaCXVzLWVhc3QtMSJHMEUCIHJibdr%2FIzQwB35bNieSC8nMRgjzYbBpIdxcuJzJJKL4AiEAz1vodt%2FCSugJ9vh%2FUFajvdeXCIw6pYa7bQZRpgnI8hMq%2FAQIyf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARABGgw2OTk3NTMzMDk3MDUiDAVWmn05d94MlviyXyrQBIaqbYLpf73xmuk2gU6rXUXYtFJrfCARUIMmpGdeMCzek9KDuuACrTrgrgWb0ZveT9IhWQtSQMfPPu8y2vgcr8JyIqhxNP1Kyl7kGrkLBi3lJC63RN02zaXzKpe8wDSup8t%2Bhag6C0mvVzaL9%2FoE8MbW9dt%2FSIVlYPpWvtHyAaSHsQseIMhJ0ESMEqrbSjo6R1UceE4kb%2Fe3aoa5Q7c63mkLmsbP3NrQNBYmdkhRu5%2BPliOXTonYZmOYJN26uIFJDNJiCrWx4aQkaXzvqDgKjEDFU3gs8v0d5Kvq8O%2FsrxaqpENyZ6U3dWaJac%2BBsym6L%2Bo2BxlYx5m4up0nhUpsVGxkCkIlALZ9zPfLwQqZ6DCoHEGO7Z89wnyKQszoYmhHzQYfE42xR760qL9okdSIlM8EhMq6I%2BAZOEgSaOtRp6sKQ6gHzI3akqB5Eu6qVFSksQSRnGaa4Cr0sBh9N44%2F9A%2F%2Bczraap2dyixdzzCbdYR%2FDkGYpJqF3f%2BsotJS6UQXUq%2FcQbGVdHbOdDQqcfIcRfk0%2BCztnqqQhjru9xoXFygAc0DeidaY%2FFH5JgtwoO%2FKMFBlAEsYrjm7spsz9Bpjrlvta6izL2o%2Ba4xBuj1L6tqHO31fNd5vZj3BxYvcJetHkF%2F%2B3%2BP5a9nrgF%2FXiUCuvYsT%2FEzKOO685mLJfoWG6vbHAtjUeZK6kw9LCL0EINhyEdpnSjY2CncTrOBN6Bqsn6NWTWS%2BIamBBjNI4wpU%2B0rIMueBLfG3cW8rOJ6KGytrsm40TwALvdIm1cXFcUL9DO4wwo%2Bf0QY6mAG0mwcwBd%2BPsluydQkXlirXAtRvyJX9fmnmjENDpvy%2B3ENebZWemKlSZrRRzuiWTmDqIa1T6yOfs0KWUw787Rtam%2FdmctXE0fqhILLoVLlttf4NTTq%2BomJp2KB%2BxsVruqGDy60NdZWlJKdn0%2F3UEt%2BreZIOQ5eJDZHWBfJRYO2UEaDJJfZxYfwuglnQSp1fZ%2FDX%2F%2FqNBjv9MQ%3D%3D&Expires=1780995477)

```
Building the document structure... [lặp lại hàng trăm lần]
```

**Root cause:** Orchestrator theo AGENTS.md phải **tự tạo `execution_ops.json` bằng Bash**, không phải để LLM reasoning inline.  Nhưng model (Qwen3.6) đang cố **generate toàn bộ JSON trong thinking/reasoning context** thay vì dùng tool để write file. Điều này gây ra:

| Triệu chứng | Nguyên nhân kỹ thuật |
|---|---|
| Lặp "Building the document structure..." | Model bị stuck trong reasoning loop, không có termination condition |
| Context window bị flood | ~29 ops × mỗi op cần Vietnamese text + JSON escape = rất nhiều tokens |
| Không có tool call nào xảy ra | Model đang "think" không dừng được |
| Session kéo dài 30K+ context tokens | Qwen3.6-35B không có hard stop khi reasoning |

Theo thiết kế đúng trong `docx_pipeline.ts`, Orchestrator phải: 
1. Gọi `inspectTemplate` → lấy `scaffold_summary` nhỏ gọn
2. Spawn **Planner subagent** (0 tool calls) để tạo ops JSON
3. Gọi `validateExecutionOps` → `applyExecutionOps`

Thay vào đó, model đang cố làm TẤT CẢ trong một reasoning pass.

***

## Issue #4: Không Có `run_id` Isolation

Log cho thấy agent tự generate `run_id` bằng shell: [ppl-ai-file-upload.s3.amazonaws](https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/164711194/a173f3f6-586f-464a-a7fb-284be3b6584c/paste.txt?AWSAccessKeyId=ASIA2F3EMEYEXEMXG4BA&Signature=ugOfcldckmQo6c2AUa%2B%2BZ%2BnXW2E%3D&x-amz-security-token=IQoJb3JpZ2luX2VjEAAaCXVzLWVhc3QtMSJHMEUCIHJibdr%2FIzQwB35bNieSC8nMRgjzYbBpIdxcuJzJJKL4AiEAz1vodt%2FCSugJ9vh%2FUFajvdeXCIw6pYa7bQZRpgnI8hMq%2FAQIyf%2F%2F%2F%2F%2F%2F%2F%2F%2F%2FARABGgw2OTk3NTMzMDk3MDUiDAVWmn05d94MlviyXyrQBIaqbYLpf73xmuk2gU6rXUXYtFJrfCARUIMmpGdeMCzek9KDuuACrTrgrgWb0ZveT9IhWQtSQMfPPu8y2vgcr8JyIqhxNP1Kyl7kGrkLBi3lJC63RN02zaXzKpe8wDSup8t%2Bhag6C0mvVzaL9%2FoE8MbW9dt%2FSIVlYPpWvtHyAaSHsQseIMhJ0ESMEqrbSjo6R1UceE4kb%2Fe3aoa5Q7c63mkLmsbP3NrQNBYmdkhRu5%2BPliOXTonYZmOYJN26uIFJDNJiCrWx4aQkaXzvqDgKjEDFU3gs8v0d5Kvq8O%2FsrxaqpENyZ6U3dWaJac%2BBsym6L%2Bo2BxlYx5m4up0nhUpsVGxkCkIlALZ9zPfLwQqZ6DCoHEGO7Z89wnyKQszoYmhHzQYfE42xR760qL9okdSIlM8EhMq6I%2BAZOEgSaOtRp6sKQ6gHzI3akqB5Eu6qVFSksQSRnGaa4Cr0sBh9N44%2F9A%2F%2Bczraap2dyixdzzCbdYR%2FDkGYpJqF3f%2BsotJS6UQXUq%2FcQbGVdHbOdDQqcfIcRfk0%2BCztnqqQhjru9xoXFygAc0DeidaY%2FFH5JgtwoO%2FKMFBlAEsYrjm7spsz9Bpjrlvta6izL2o%2Ba4xBuj1L6tqHO31fNd5vZj3BxYvcJetHkF%2F%2B3%2BP5a9nrgF%2FXiUCuvYsT%2FEzKOO685mLJfoWG6vbHAtjUeZK6kw9LCL0EINhyEdpnSjY2CncTrOBN6Bqsn6NWTWS%2BIamBBjNI4wpU%2B0rIMueBLfG3cW8rOJ6KGytrsm40TwALvdIm1cXFcUL9DO4wwo%2Bf0QY6mAG0mwcwBd%2BPsluydQkXlirXAtRvyJX9fmnmjENDpvy%2B3ENebZWemKlSZrRRzuiWTmDqIa1T6yOfs0KWUw787Rtam%2FdmctXE0fqhILLoVLlttf4NTTq%2BomJp2KB%2BxsVruqGDy60NdZWlJKdn0%2F3UEt%2BreZIOQ5eJDZHWBfJRYO2UEaDJJfZxYfwuglnQSp1fZ%2FDX%2F%2FqNBjv9MQ%3D%3D&Expires=1780995477)

```bash
$ date +%Y%m%dT%H%M%S
20260609T082534
```

Nhưng trong `pipeline-core.ts`, `makeAutoRunDir` đã có function tự động tạo run_dir: 

```typescript
export function makeAutoRunDir(worktree: string, suffix = "auto"): string {
  const ts = new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15)
  return `${worktree}/.office-auto/state/${ts}_${suffix}`
}
```

Và `resolveInspectionRunDir` sẽ gọi `makeAutoRunDir` nếu `inputPath` chứa `$(` (shell expansion): 

```typescript
export function resolveInspectionRunDir(worktree: string, inputPath: string): string {
  if (!inputPath || inputPath.includes("$(")) {
    return makeAutoRunDir(worktree, "inspect")  // auto-generate
  }
  ...
}
```

Khi agent truyền `run_dir=".office-auto/state/$(date +%Y%m%dT%H%M%S)_auto"` (shell syntax), TypeScript layer sẽ detect và override bằng timestamp riêng — **khiến run_dir mà agent nghĩ nó đang dùng ≠ run_dir thực tế**, gây lỗi khi đọc artifacts.

***

## Issue #5: Schema Thiếu Validation Gate

Trong `docx_pipeline.ts`, `applyExecutionOps` có annotation: 

```typescript
annotations: {
  idempotentHint: false,  // non-idempotent!
  ...
}
```

Nhưng không có **hard precondition check** nào ở TypeScript layer để ngăn gọi `apply` khi `validation_file` chưa tồn tại. Nếu agent skip validate và gọi thẳng apply (điều xảy ra khi reasoning loop timeout), script Python sẽ fail với error mơ hồ thay vì rõ ràng `"ValidationNotRun"`.

***

## Tóm Tắt Các Lỗi Theo Mức Độ Nghiêm Trọng

| # | Issue | Severity | Fix |
|---|---|---|---|
| 1 | `python3 ENOENT` trong Bun env | 🔴 Critical | Detect Bun và dùng `Bun.spawn` + verify python path |
| 2 | Agent skip AGENTS.md bootstrap | 🔴 Critical | Add hard system prompt enforcement hoặc tool hook |
| 3 | Reasoning loop không terminate | 🟠 High | Giới hạn `thinking_tokens` cho Qwen3, hoặc Planner subagent must use tool call |
| 4 | Shell expansion trong `run_dir` | 🟡 Medium | Validate/sanitize `run_dir` arg trước khi pass vào pipeline |
| 5 | Không có gate validate → apply | 🟡 Medium | Add precondition check trong `applyExecutionOps.execute()` |

***

## Recommendation Cụ Thể

**Fix ngay cho Issue #1** — trong `pipeline-core.ts`, thêm Python path resolution:

```typescript
async function findPython(): Promise<string> {
  for (const candidate of ["python3", "python", "/usr/bin/python3"]) {
    try {
      // test with --version
      const proc = BunRuntime 
        ? BunRuntime.spawn([candidate, "--version"], ...)
        : nodeSpawn(candidate, ["--version"], ...)
      if (exitCode === 0) return candidate
    } catch {}
  }
  throw new Error("Python not found in PATH")
}
```

**Fix cho Issue #3** — Planner subagent nên viết file bằng tool call, không phải inline generation:

```markdown
# Trong skill md-to-docx-pipeline
Planner MUST call: write_file(path="execution_ops.json", content=<json>)
Planner KHÔNG ĐƯỢC generate JSON trong text response
```

Đây là pattern quan trọng: **side-effecting output (file write) phải là tool call, không phải text generation**, để tránh reasoning loop và đảm bảo artifact tồn tại trên disk.