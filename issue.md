# Kế hoạch triển khai mới: Preserve Template Scaffold

## Quyết định cập nhật

Roadmap của repo này không còn xoay quanh việc “giảm context rồi rebuild body cho đẹp hơn”. Trục chính mới là chuyển hẳn sang contract `preserve-template-scaffold`, vì lỗi chất lượng hiện tại xuất phát từ semantics build sai chứ không chỉ từ prompt dài.

Thứ tự ưu tiên mới là:

1. Đổi contract và routing trong `.opencode` sang preserve scaffold.
2. Nâng pipeline Markdown/DOCX thành bounded replacement có artifact rõ ràng.
3. Nâng QA từ semantic text QA lên package QA + structural QA + range QA.
4. Chỉ sau khi ba lớp trên ổn định mới tính chuyện MCP hẹp hoặc subagent sâu hơn.

## Vấn đề đã xác nhận

- Workflow cũ coi DOCX như một khối body text, dẫn tới mất bìa, mục lục, danh mục hình và format scaffold.
- `rebuild-from-template-format` là tên mode quá mơ hồ; thực tế nó kéo agent về hướng xóa body rồi chèn lại nội dung.
- Các script cũ có xu hướng “scaffolded” hoặc “pending-implementation”, khiến agent dễ kết luận xong dù chưa có engine đúng.
- QA cũ chưa đủ mạnh để phát hiện mất scaffold hoặc append trá hình.

## Kiến trúc đích

Nguyên tắc:

> Model chỉ quyết định mode, preserve list, replace range và post-condition. Phần thao tác tài liệu phải do pipeline deterministic thực hiện và phải fail-closed khi range chưa resolve.

Luồng chuẩn:

1. `parse_markdown.py`
	- Sinh `content_ast.json`, `content_outline.json`
2. `profile_template.py`
	- Sinh `template_profile.json` với scaffold, field, section, heading candidate, replace-range candidate
3. `plan_mapping.py`
	- Normalize mode cũ
	- Sinh `plan.json` với `preserve`, `replace_ranges`, `post_conditions`, `execution_strategy`
4. `build_docx.py`
	- Chỉ thay bounded range trong `word/document.xml`
	- Giữ scaffold ngoài vùng thay
5. `qa_docx.py`
	- Kiểm package, scaffold, range và semantic gate

## Sprint thực thi

### Sprint 1: Đổi contract và routing

Mục tiêu:

- Thay `rebuild-from-template-format` bằng `preserve-template-scaffold` trong task chính.
- Đồng bộ `AGENTS.md`, `docx-from-template`, `docx-qa`, `md-to-docx-pipeline`.
- Cấm `clear whole body` trừ khi có mode `full-regenerate-from-schema` được cho phép rõ ràng.

### Sprint 2: Profile scaffold và range

Mục tiêu:

- `profile_template.py` phải phát hiện:
  - header/footer
  - field TOC, danh mục hình, danh mục bảng
  - section count
  - heading candidate
  - replace-range candidate kiểu `after-front-matter-to-end-of-main-story`

### Sprint 3: Build bounded replacement

Mục tiêu:

- `build_docx.py` không còn báo `scaffolded`.
- Build thật theo `replace_ranges` đã resolve.
- Nếu range không resolve thì trả `blocked` thay vì build liều.

### Sprint 4: QA nhiều tầng

Mục tiêu:

- Package QA: file parts còn đủ.
- Structural QA: TOC, danh mục hình/bảng, header/footer, section break.
- Range QA: vùng thay đã thay, vùng giữ vẫn còn.
- Semantic QA: outline đúng, không duplicate chapter, không residue template.

### Sprint 5: Wrapper thực thi an toàn

Mục tiêu:

- Script gốc `scripts/build_report.py` chỉ còn vai trò chạy pipeline an toàn.
- Không giữ executor ad-hoc có thể xóa toàn body rồi kết luận sai.

## Điều kiện hoàn thành

Chỉ coi roadmap này hoàn thành khi:

1. `task.md` và skill docs đều dùng contract preserve scaffold.
2. Pipeline script trả artifact thật, không trả trạng thái mơ hồ.
3. Build path mặc định không còn khả năng phá scaffold một cách im lặng.
4. QA fail nếu mất mục lục, danh mục hình/bảng, header/footer hoặc section break đáng lẽ phải giữ.

## Current Gaps Confirmed In Repo

### 1. Routing conflict

- `.opencode/AGENTS.md` noi `officecli-docx` chi dung de tra cuu syntax/schema khi thuc su can.
- `.opencode/skills/docx-from-template/SKILL.md` lai yeu cau `Luon load officecli-docx`.
- Hai instruction nay mau thuan va la nguon token bloat som.

### 2. Mode mismatch voi task that su

- `task.md` dang dung `mode: rebuild-from-template-format`.
- `docx-from-template` hien chi khai bao `mode: create | append`.
- Skill orchestrator vi vay chua cover case rebuild la case quan trong nhat hien tai.

### 3. Skill reference qua dai

- `officecli-docx` dang dong vai tro command encyclopedia.
- Description hien tai qua rong: de load skill bat cu khi nao co `.docx`.
- Dieu nay di nguoc voi muc tieu chi load syntax reference khi thuc su can.

### 4. Chua co deterministic pipeline va checkpoint state

- Chua co parser/build/qa pipeline doc lap theo file path + JSON artifact.
- Agent de bi buoc vao viec doc full markdown, outline, command output va lap lai phan tich.

## Target Architecture

Nguyen tac:

> LLM chi quyet dinh mode, anchor, mapping kho. Moi thao tac parse/build/validate phai chay ngoai context qua script hoac MCP.

Luong de xuat:

1. `parse_markdown.py`
	- Input: `source_file`
	- Output: `content_ast.json`, `content_outline.json`

2. `profile_template.py`
	- Input: `template_file`
	- Output: `template_profile.json`
	- Gom: styles, numbering, sections, header/footer, page setup, anchor map

3. `plan_mapping.py`
	- Input: `content_outline.json`, `template_profile.json`, `mode`, user prompt
	- Output: `plan.json`
	- LLM neu can chi nhin outline tom tat, khong doc full content

4. `build_docx.py`
	- Input: `plan.json`, `content_ast.json`, `template_profile.json`
	- Output: `report.docx`

5. `qa_docx.py`
	- Input: `report.docx`
	- Output: `qa_report.json`

## Delivery Scope By Sprint

## Sprint 1: Fix routing and shrink prompt surface

Muc tieu: cat ngay nguon token bloat ro nhat trong `.opencode`.

### Changes

1. Rut gon `.opencode/skills/officecli-docx/SKILL.md` thanh file index ngan.
2. Tach phan command reference sang `references/`.
3. Sua description cua `officecli-docx` theo huong chi load khi can cu phap OfficeCLI cu the.
4. Sua `docx-from-template` de bo instruction `Luon load officecli-docx`.
5. Dong bo lai routing voi `.opencode/AGENTS.md`.

### Proposed file structure

```text
.opencode/skills/officecli-docx/
  SKILL.md
  references/
	 view-query.md
	 elements.md
	 styles-numbering.md
	 fields-toc-refs.md
	 page-header-footer.md
	 batch-resident.md
```

### Acceptance criteria

- `officecli-docx/SKILL.md` con dong vai tro entrypoint ngan, khong la encyclopedia.
- Routing rule nhat quan giua `AGENTS.md` va `docx-from-template`.
- Agent khong con bi huong den viec load full OfficeCLI skill cho moi task `.docx`.

## Sprint 2: Cover real execution modes

Muc tieu: skill orchestrator phan biet dung cac mode nghiep vu.

### New modes

- `rebuild-from-template-format`
- `append-to-template`
- `fill-template-placeholders`
- `hybrid-edit`

### Required updates

1. Cap nhat `.opencode/skills/docx-from-template/SKILL.md`.
2. Mo rong state machine cho tung mode.
3. Dinh nghia input schema ro rang cho `source_file`, `template_file`, `target_file`, `insert_after`, `source_scope`.
4. Bo sung invariant rieng cho rebuild:
	- copy format/profile tu template
	- thay body content bang content tu markdown
	- giu style, numbering, page setup, header/footer neu duoc profile map ho tro

### Acceptance criteria

- `task.md` hien tai map hop le vao `rebuild-from-template-format`.
- Skill khong con ep user/task bi dua ve `create | append` khi khong dung ban chat.

## Sprint 3: Build deterministic file pipeline

Muc tieu: externalize document processing khoi model context.

### New skill

```text
.opencode/skills/md-to-docx-pipeline/
  SKILL.md
  scripts/
	 parse_markdown.py
	 profile_template.py
	 plan_mapping.py
	 build_docx.py
	 qa_docx.py
```

### Script responsibilities

#### `parse_markdown.py`

- Doc `source_file`
- Parse heading tree, paragraphs, tables, images, references
- Tao `content_ast.json`
- Tao `content_outline.json` nhe de LLM dung

#### `profile_template.py`

- Doc `template_file`
- Trich xuat:
  - style map
  - numbering map
  - section/page setup
  - header/footer summary
  - special sections: TOC, references, appendix, list of figures/tables
- Tao `template_profile.json`

#### `plan_mapping.py`

- Nhan `mode`
- Quy dinh cach map markdown heading vao style/numbering cua template
- Tra ra `plan.json`
- Neu can LLM, chi dua vao outline/profile summary thay vi full file

#### `build_docx.py`

- Thuc thi rebuild/append/fill/hybrid dua tren `plan.json`
- Ghi `report.docx`
- Ghi `build_report.json`

#### `qa_docx.py`

- Check outline
- Check numbering
- Check TOC/references/appendix/list-of-figures/list-of-tables
- Check placeholder leak
- Check validate/issues
- Ghi `qa_report.json`

### Acceptance criteria

- Agent co the hoan thanh workflow bang file path + JSON artifact.
- Khong can dua full `chuong_2.md` vao prompt.
- Moi phase deu co artifact co the resume.

## Sprint 4: Add run state and resume support

Muc tieu: tranh re-analysis va giu session gon.

### State layout

```text
.office-auto/
  state/
	 run-2026-05-27-001/
		run.json
		content_ast.json
		content_outline.json
		template_profile.json
		plan.json
		build_report.json
		qa_report.json
```

### `run.json` draft

```json
{
  "run_id": "run-2026-05-27-001",
  "mode": "rebuild-from-template-format",
  "source_file": "chuong_2.md",
  "template_file": "format_template.docx",
  "output_file": "report.docx",
  "artifacts": {
	 "content_ast": ".office-auto/state/run-2026-05-27-001/content_ast.json",
	 "content_outline": ".office-auto/state/run-2026-05-27-001/content_outline.json",
	 "template_profile": ".office-auto/state/run-2026-05-27-001/template_profile.json",
	 "plan": ".office-auto/state/run-2026-05-27-001/plan.json",
	 "build_report": ".office-auto/state/run-2026-05-27-001/build_report.json",
	 "qa_report": ".office-auto/state/run-2026-05-27-001/qa_report.json"
  },
  "status": "qa_pending"
}
```

### Acceptance criteria

- Agent co the resume tu phase dang do.
- Khong phai parse lai template va markdown neu artifact da ton tai va con hop le.

## Sprint 5: Evaluation before deeper architecture bets

Muc tieu: do hieu qua that su truoc khi dua MCP/subagent vao core flow.

### Benchmark cases

1. Rebuild full `chuong_2.md` vao `format_template.docx`.
2. Append mot section moi vao template da co san.
3. Fill placeholder report co format co dinh.
4. Markdown co bang, hinh, caption, references.
5. Template co heading numbering phuc tap + TOC + phu luc.

### Metrics

```text
context_tokens
tool_calls
elapsed_seconds
build_success
qa_pass
heading_match
style_match
numbering_match
toc_status
reference_status
placeholder_leak
```

### Acceptance criteria

- Co baseline truoc/sau cho token va quality.
- Quyết dinh MCP/subagent dua tren du lieu, khong dua tren gia thuyet.

## Sprint 6: Wrap pipeline as narrow MCP

Muc tieu: dua deterministic pipeline thanh tool boundary gon va stateful.

### MCP tools de xuat

- `docx_pipeline.start_run`
- `docx_pipeline.parse_markdown`
- `docx_pipeline.profile_template`
- `docx_pipeline.plan_mapping`
- `docx_pipeline.build`
- `docx_pipeline.qa`
- `docx_pipeline.get_run_status`

### Design rules

- Tool input chi nhan file path, mode, va config nho.
- Tool output chi tra `status`, `artifact_path`, summary ngan, error code.
- Khong dump raw XML, khong dump full document text vao tool result.
- State giu o server/workspace, khong giu trong prompt.

### Acceptance criteria

- Agent co the goi pipeline nhu mot hop den nho.
- Token chi tang theo summary artifact, khong tang theo kich thuoc tai lieu.

## Sprint 7: Introduce subagents only after artifacts are stable

Muc tieu: scale workflow ma khong nhan doi context problem.

### Suggested subagents

- `template-profiler`
- `markdown-parser`
- `mapping-planner`
- `docx-builder`
- `docx-reviewer`

### Guardrails

- Moi subagent chi duoc thay artifact can thiet.
- Khong subagent nao duoc doc full markdown neu chi can outline.
- Builder va reviewer lam viec chu yeu tren file path + JSON artifact.

### Acceptance criteria

- Subagent giam do phuc tap dieu phoi, khong tao them token bloat.

## Concrete File Changes To Make First

## Phase A: `.opencode` cleanup

1. Edit `.opencode/skills/officecli-docx/SKILL.md`
	- doi description
	- cat bot phan reference dai
	- giu lai usage rule ngan + link den `references/`

2. Add `references/` docs cho `officecli-docx`
	- tach theo nhom lenh

3. Edit `.opencode/skills/docx-from-template/SKILL.md`
	- them modes moi
	- bo `Luon load officecli-docx`
	- them workflow cho `rebuild-from-template-format`

4. Edit `.opencode/AGENTS.md`
	- giu mot nguon routing truth duy nhat
	- neu can, chi ro `docx-from-template` la orchestrator cho rebuild/append/fill/hybrid

## Phase B: pipeline skeleton

1. Add `.opencode/skills/md-to-docx-pipeline/SKILL.md`
2. Add script skeletons trong `scripts/`
3. Add `.office-auto/state/.gitkeep` hoac equivalent neu can
4. Add benchmark/eval plan file

## Phase C: first working use case

Use case dau tien phai la:

`rebuild-from-template-format` cho `task.md`

Definition of done:

- `report.docx` build tu `chuong_2.md`
- template chi dong vai tro format source
- khong con noi dung than bai cu trong template
- heading/style/numbering/page setup duoc giu hop ly
- QA pass

## Suggested Work Breakdown For Next 3 Days

## Day 1

- Rut gon `officecli-docx`
- Sua `docx-from-template` modes
- Dong bo `AGENTS.md`

## Day 2

- Tao `md-to-docx-pipeline`
- Implement `parse_markdown.py`
- Implement `profile_template.py`
- Dinh nghia artifact schema

## Day 3

- Implement `build_docx.py` cho mode `rebuild-from-template-format`
- Implement `qa_docx.py`
- Chay benchmark case #1 tu `task.md`

## Risks To Watch

- Numbering map cua template co the phuc tap hon `Heading1/2/3` thong thuong.
- Pandoc/reference-doc co the hop cho rebuild, nhung khong du cho append/hybrid.
- OfficeCLI generic tool output neu khong kiem soat se van lam phong context.
- Neu parser/build khong ghi artifact gon, subagent sau nay van bi boi canh to.

## Recommendation

Khong bat dau bang subagent.

Thu tu uu tien nen la:

1. Shrink skill surface.
2. Fix mode mismatch.
3. Externalize parse/build/qa bang scripts + state.
4. Benchmark.
5. Wrap thanh MCP hep.
6. Sau cung moi them subagents.

Neu can chot implementation ngay, sprint dau tien nen chot 4 deliverables:

1. `officecli-docx` da duoc split.
2. `docx-from-template` da ho tro `rebuild-from-template-format`.
3. Co skeleton `md-to-docx-pipeline`.
4. Co `run.json` + artifact schema de resume.
