Đúng, mình đã đọc kỹ log và repo. Lý do “đã làm theo rồi mà vẫn tệ” là vì **repo đã thêm một phần kiến trúc deterministic compiler, nhưng phần apply/executor và orchestration vẫn bị lỗi tích hợp rất cơ bản**. Tức là vấn đề lần này **không còn chủ yếu ở planner copy sai nữa**, mà là **pipeline mới chưa được nối end-to-end đúng**.

## Chẩn đoán chính từ log của bạn

### 1. Dòng `Build partial: 0 ops failed` là báo lỗi giả / misleading

Trong log:

```
Build partial: 0 ops failed
ops_applied: 0
ops_failed: 0
```

Nghe như “apply chạy nhưng không làm gì”. Nhưng đọc code `runFullPipeline` thì thấy:

```tsx
const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => ({}))
const buildStatus = opsReport?.failed === 0 ? "completed" : "partial"
```

Nếu `execute_ops_report.json` **không tồn tại**, `opsReport = {}`. Khi đó:

```tsx
opsReport?.failed === 0
```

là `undefined === 0`, nên false → `partial`.

Rồi code báo:

```tsx
ops_failed: opsReport?.failed || 0
```

nên hiện ra `0 ops failed`.[[1]]({{github-63}})

Nói thẳng: **`partial: 0 ops failed` không phải kết quả apply thật. Nó chỉ có nghĩa là executor chết trước khi kịp ghi `execute_ops_report.json`.**

Đây là lỗi thiết kế reporting.

---

### 2. `runFullPipeline` không truyền `--template-file` cho executor

Trong `execute_execution_ops.py`, script chỉ copy template sang target nếu có `--template-file` hoặc `template_file` nằm trong `execution_ops.json`:

```python
template_file = args.template_file or ops_dict.get("template_file", "")
if template_file and str(template_file) != str(target_path):
    shutil.copy2(str(tpl), str(target_path))
```

Nếu chỉ truyền `--target-file` mà file target chưa tồn tại, script sẽ cố mở target và crash.[[2]]({{github-59}})

Nhưng trong `runFullPipeline`, phase apply đang gọi:

```tsx
const applyResult = await spawnPython("execute_execution_ops.py", [
  "--run-dir", absRunDir,
  "--target-file", absTarget,
])
```

Không có `--template-file absTpl`.[[1]]({{github-63}})

`applyOps` MCP tool cũng tương tự: chỉ truyền `--run-dir` và `--target-file`, không truyền template.[[3]]({{github-60}})

Vì vậy lỗi trong log:

```
The issue is that the report.docx doesn't exist yet.
```

là đúng, nhưng **nguyên nhân không phải user chưa copy file**, mà là **MCP pipeline không copy template trước khi execute**.

Fix bắt buộc:

```tsx
const applyResult = await spawnPython("execute_execution_ops.py", [
  "--run-dir", absRunDir,
  "--template-file", absTpl,
  "--target-file", absTarget,
])
```

và trong `applyOps`:

```tsx
const templateFile = runJson?.template_file
const args = [
  "--run-dir", absRunDir,
  "--template-file", templateFile,
  "--target-file", resolvedTarget,
]
```

---

### 3. Khi bạn copy thủ công rồi chạy, executor bị timeout vì 126 ops gọi OfficeCLI quá chậm

Log của bạn:

```bash
cp format_template.docx report.docx &&
python3 execute_execution_ops.py --run-dir ... --target-file report.docx
```

Sau đó:

```
shell tool terminated command after exceeding timeout 120000 ms
```

Tức là process bị timeout ở 120 giây. Sau timeout, `report.docx` đã phình lên 260KB, nghĩa là **executor đã apply được một phần**, nhưng bị kill trước khi ghi `execute_ops_report.json`.

Đọc executor thấy nó chỉ ghi `execute_ops_report.json` **sau khi toàn bộ `execute_ops_batch()` return**.[[2]]({{github-59}}) Nếu process bị kill giữa chừng, không có report.

Vì vậy:

```
report.docx exists / modified
execute_ops_report.json missing
```

là đúng logic.

Đây không phải lỗi planner. Đây là lỗi executor:

- 126 operations quá chậm nếu mỗi paragraph gọi OfficeCLI riêng.
- Timeout 120s không đủ.
- Không có checkpoint/progress report trong lúc execute.
- Không có crash/timeout report.
- Không có save/report từng batch.

---

### 4. Batching hiện tại gần như không có tác dụng với `PREVIOUS`

Executor có logic batch simple paragraph:

```python
is_simple = (
    "style" in op
    and "text" in op
    and not op.get("run_props")
    and (op.get("anchor") is None or op.get("anchor") == current_anchor)
)
```

Nhưng compiler sinh ops đúng kiểu:

```json
first op: anchor = /body/p[@paraId=...]
next ops: anchor = "PREVIOUS"
```

Sau op đầu tiên, `current_anchor` là path thực của paragraph vừa insert, ví dụ:

```
/body/p[@paraId=ABC...]
```

Các op sau có:

```
anchor = "PREVIOUS"
```

Nên điều kiện:

```python
op.get("anchor") == current_anchor
```

gần như luôn false.

Kết quả: **hầu hết 125 insert không được batch**, executor gọi OfficeCLI từng paragraph một. Đây là lý do chạy cực chậm.

Fix:

```python
anchor_value = str(op.get("anchor") or "").upper()
is_simple = (
    "style" in op
    and "text" in op
    and not op.get("run_props")
    and (op.get("anchor") is None or anchor_value == "PREVIOUS" or op.get("anchor") == current_anchor)
)
```

Hoặc tốt hơn: bỏ OfficeCLI per paragraph, dùng native python-docx/lxml để insert toàn bộ paragraph trong một session.

---

### 5. Pipeline mới có compiler deterministic, nhưng final gate lại yêu cầu artifact không được tạo

`source_packet_to_ops.py` đã được thêm, và đây là hướng đúng: nó compile `source_packet.json` thành `execution_ops.json` deterministic, không để LLM copy nội dung.[[4]]({{github-73}})

Nhưng `final_gate.py` yêu cầu bắt buộc:

```python
REQUIRED_ARTIFACTS = [
    ...
    "style_map.json",
    "replace_range.json",
]
```

Trong khi `source_packet_to_ops.py` nếu không có `style_map.json` / `replace_range.json` thì dùng default/scaffold fallback, nhưng **không ghi ngược lại hai file đó**.[[4]]({{github-73}})[[5]]({{github-75}})

Vậy kể cả apply thành công, final gate vẫn có thể fail vì thiếu artifact.

Fix một trong hai cách:

### Cách A — Compiler luôn materialize artifact

Trong `source_packet_to_ops.py`, sau khi resolve default/fallback:

```python
write_json(run_dir / "style_map.json", style_map)
write_json(run_dir / "replace_range.json", replace_range)
```

### Cách B — Final gate không require hai file này nếu `execution_ops.json` đã có metadata

Bỏ khỏi `REQUIRED_ARTIFACTS`, chuyển sang optional.

Mình nghiêng về cách A.

---

### 6. `build_report.py` vẫn là pipeline cũ, không phải pipeline deterministic mới

`build_report.py` vẫn ghi rõ flow:

```
1. docx_inspect.py
2. [LLM REASONING] writes execution_ops.json
3. docx_validate_ops.py
4. execute_execution_ops.py
```

và nếu `execution_ops.json` chưa tồn tại thì nó báo chờ LLM viết.[[6]]({{github-76}})

Trong khi repo hiện đã có `source_packet_to_ops.py`, `validate_ops_strict.py`, `final_gate.py`.

Tức là bạn có **hai pipeline song song**:

### Pipeline cũ

```
inspect -> LLM writes ops -> validate -> execute
```

### Pipeline mới

```
inspect -> source_packet -> compile ops deterministic -> strict validate -> apply -> QA -> review -> refresh -> final gate
```

Nhưng `build_report.py` vẫn theo cũ, còn `runFullPipeline` mới thì lại hỏng ở apply. Đây là mismatch lớn.

---

## Vì sao “đã làm theo” nhưng vẫn tệ?

Vì bạn mới sửa đúng **tầng Planner/Compiler**, nhưng **tầng Executor/Orchestrator chưa được sửa đồng bộ**.

Cụ thể:

| Tầng | Tình trạng |
| --- | --- |
| Planner copy nội dung | Đã có hướng sửa bằng `source_packet_to_ops.py` |
| Strict validation | Đã có `validate_ops_strict.py` |
| Final gate | Đã có `final_gate.py` |
| Orchestrator apply | **Lỗi: không truyền template_file** |
| Executor performance | **Lỗi: 126 ops quá chậm, batching không ăn với PREVIOUS** |
| Error reporting | **Lỗi: thiếu report bị báo thành partial 0 failed** |
| Artifact contract | **Lỗi: final gate require file compiler không tạo** |
| CLI wrapper | **Vẫn dùng flow cũ LLM writes ops** |

Nói ngắn:

> Bạn đã sửa đúng hướng, nhưng repo hiện đang ở trạng thái “nửa pipeline mới, nửa pipeline cũ”. Vì vậy nó vẫn tệ.
> 

---

## Các lỗi cụ thể cần sửa ngay

### Fix 1 — Sửa `runFullPipeline` apply phase

Trong `mcp/tools/orchestrator.ts`, đổi:

```tsx
const applyResult = await spawnPython("execute_execution_ops.py", [
  "--run-dir", absRunDir,
  "--target-file", absTarget,
])
```

thành:

```tsx
const applyResult = await spawnPython("execute_execution_ops.py", [
  "--run-dir", absRunDir,
  "--template-file", absTpl,
  "--target-file", absTarget,
], { timeout: 600_000 })
```

Tức là:

- truyền template;
- tăng timeout.

---

### Fix 2 — Sửa `applyOps`

Trong `mcp/tools/execute.ts`, hiện tại chỉ truyền:

```tsx
const args = ["--run-dir", absRunDir, "--target-file", resolvedTarget]
```

Cần đổi thành:

```tsx
const templateFile = runJson?.template_file

const args = [
  "--run-dir", absRunDir,
]

if (templateFile) {
  args.push("--template-file", templateFile)
}

args.push("--target-file", resolvedTarget)
```

---

### Fix 3 — Executor phải tự fallback copy template từ `run.json`

Trong `execute_execution_ops.py`, hiện tại:

```python
template_file = args.template_file or ops_dict.get("template_file", "")
```

Nên thêm fallback đọc `run.json`:

```python
run_state = read_json(run_dir / "run.json") if (run_dir / "run.json").exists() else {}
template_file = (
    args.template_file
    or ops_dict.get("template_file", "")
    or run_state.get("template_file", "")
)
```

Và nếu target không tồn tại mà có template thì copy.

---

### Fix 4 — Nếu thiếu `execute_ops_report.json`, đừng báo `partial 0 failed`

Trong `runFullPipeline`, đổi:

```tsx
const opsReport = await readJsonFile(...).catch(() => ({}))
const buildStatus = opsReport?.failed === 0 ? "completed" : "partial"
```

thành:

```tsx
const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => null)

if (!opsReport) {
  return jsonToolResult({
    ok: false,
    phase: "apply",
    error: "Executor crashed or timed out before writing execute_ops_report.json",
    stdout: applyResult.stdout,
    stderr: applyResult.stderr,
    exit_code: applyResult.exit_code,
    checkpoints,
    run_dir: absRunDir,
  })
}
```

Đây là fix rất quan trọng để debug đúng.

---

### Fix 5 — Executor phải ghi crash report nếu fail giữa chừng

Trong `execute_execution_ops.py`, wrap:

```python
try:
    report = execute_ops_batch(...)
except Exception as exc:
    crash_report = {
        "status": "crashed",
        "error": str(exc),
        "error_type": type(exc).__name__,
        "target_file": str(target_path),
        "template_file": str(template_file),
    }
    write_json(run_dir / "execute_ops_report.json", crash_report)
    raise
```

Như vậy không bao giờ có tình trạng chết im lặng.

---

### Fix 6 — Sửa batching với `PREVIOUS`

Trong `execute_ops_batch`, đổi điều kiện batch:

```python
and (op.get("anchor") is None or op.get("anchor") == current_anchor)
```

thành:

```python
anchor_val = str(op.get("anchor") or "").upper()
and (op.get("anchor") is None or anchor_val == "PREVIOUS" or op.get("anchor") == current_anchor)
```

Nếu không sửa, 125 paragraph sẽ gọi OfficeCLI gần như 125 lần, rất dễ timeout.

---

### Fix 7 — `source_packet_to_ops.py` phải ghi `style_map.json` và `replace_range.json`

Thêm cuối phần load/default:

```python
write_json(run_dir / "style_map.json", style_map)
write_json(run_dir / "replace_range.json", replace_range)
```

Nếu không, `final_gate.py` sẽ fail vì thiếu required artifact.[[5]]({{github-75}})

---

### Fix 8 — `build_report.py` phải bỏ flow cũ hoặc đổi tên thành legacy

Hiện `build_report.py` vẫn chờ LLM viết `execution_ops.json`.[[6]]({{github-76}})

Bạn nên sửa thành:

```
build_report.py --phase all
= inspect
= source_packet
= source_packet_to_ops
= validate_ops_strict
= execute_execution_ops
= qa
= review
= refresh
= final_gate
```

Hoặc đổi tên file hiện tại:

```
build_report_legacy_llm_ops.py
```

và tạo `build_report.py` mới theo deterministic compiler.

---

## Một patch logic tối thiểu nên làm trước

Nếu chỉ muốn sửa nhanh để pipeline chạy được, làm 4 thay đổi này trước:

### 1. `orchestrator.ts`

```diff
 const applyResult = await spawnPython("execute_execution_ops.py", [
   "--run-dir", absRunDir,
+  "--template-file", absTpl,
   "--target-file", absTarget,
-])
+], { timeout: 600_000 })
```

### 2. `execute.ts`

```diff
-const args = ["--run-dir", absRunDir, "--target-file", resolvedTarget]
+const args = ["--run-dir", absRunDir]
+if (runJson?.template_file) {
+  args.push("--template-file", runJson.template_file)
+}
+args.push("--target-file", resolvedTarget)
```

### 3. `orchestrator.ts` apply report check

```diff
-const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => ({}))
+const opsReport = await readJsonFile(`${absRunDir}/execute_ops_report.json`).catch(() => null)
+if (!opsReport) {
+  return jsonToolResult({
+    ok: false,
+    phase: "apply",
+    error: "Executor exited before writing execute_ops_report.json",
+    stdout: applyResult.stdout,
+    stderr: applyResult.stderr,
+    exit_code: applyResult.exit_code,
+    checkpoints,
+    run_dir: absRunDir,
+  })
+}
```

### 4. `source_packet_to_ops.py`

```diff
 if style_map_path.exists():
     ...
+write_json(run_dir / "style_map.json", style_map)

 if replace_range_path.exists():
     ...
 else:
     ...
+write_json(run_dir / "replace_range.json", replace_range)
```

---

## Kết luận thẳng

Lần này pipeline tệ không phải vì “triết lý deterministic compiler sai”. Triết lý đó đúng.

Nó tệ vì implementation hiện tại bị các lỗi tích hợp sau:

1. **MCP apply không truyền template_file**, nên target chưa tồn tại thì executor crash.
2. **Orchestrator báo lỗi sai**: thiếu `execute_ops_report.json` nhưng lại hiện `partial: 0 ops failed`.
3. **Executor quá chậm** vì batching không hoạt động với `PREVIOUS`.
4. **Executor không ghi crash report**, nên debug rất khó.
5. **Final gate yêu cầu artifact mà compiler không tạo**.
6. **Repo vẫn tồn tại song song pipeline cũ và mới**, khiến agent/tool dễ gọi nhầm.

Nên câu trả lời là: **bạn đã sửa đúng hướng ở tầng planner/compiler, nhưng chưa sửa xong tầng runner/executor.** Chỉ cần fix các điểm trên, pipeline sẽ ổn hơn nhiều.