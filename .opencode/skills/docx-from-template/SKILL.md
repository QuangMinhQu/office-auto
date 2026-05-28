---
name: docx-from-template
description: Tạo hoặc cập nhật file Word (.docx) từ template theo workflow điều phối ngắn cho các mode rebuild, append, fill placeholder và hybrid, có checkpoint rõ ràng và không kéo toàn bộ nội dung vào context.
license: MIT
---

# SKILL: DOCX_FROM_TEMPLATE

## Mục tiêu
Skill này là orchestrator cho tác vụ tạo hoặc cập nhật `.docx` từ template.

Skill này không dạy cú pháp OfficeCLI chi tiết.
Khi cần lệnh hoặc schema cụ thể, mới load `officecli-docx`.
Khi cần parse, profile, plan, build, QA qua artifact JSON, load `md-to-docx-pipeline`.
Khi cần delivery gate cho TOC, references, appendix, cross-reference, header/footer, load `docx-qa`.

## Khi nào dùng skill này
- Tạo `report.docx` từ `format_template.docx`.
- Rebuild toàn bộ thân bài từ Markdown nhưng giữ format của template.
- Append chương hoặc mục mới vào file hiện có.
- Fill placeholder trong template định kỳ.
- Hybrid edit: vừa append, vừa update các phần phụ thuộc như TOC hoặc references.

## Modes hỗ trợ
- `preserve-template-scaffold`
- `replace-main-content-range`
- `fill-declared-placeholders`
- `append-structured-section`
- `full-regenerate-from-schema`

`rebuild-from-template-format` là mode cũ và phải được normalize sang `preserve-template-scaffold` ngay khi phát hiện.

## Inputs bắt buộc
- `template_file`
- `mode`

## Inputs theo mode

### `preserve-template-scaffold`
- `source_file`
- `target_file`
- `source_scope`: `full-document` | `section`
- `preserve`
- `replace_ranges`
- `post_conditions`

### `replace-main-content-range`
- `source_file`
- `target_file`
- `replace_ranges`

### `append-structured-section`
- `source_file`
- `target_file`
- `insert_after`

### `fill-declared-placeholders`
- `target_file` hoặc `template_file`
- `placeholder_data`

### `full-regenerate-from-schema`
- `schema_file` hoặc contract tái tạo tương đương
- `target_file`

## Invariants
- Không bỏ qua thứ tự phase.
- Không đoán `prop`, `type`, `numId`, `ilvl`; nếu thiếu thì tra `officecli-docx`.
- `style` và `numbering` là hai lớp khác nhau.
- Mọi mode có thay đổi cấu trúc phải rà TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer.
- Không đọc tràn lan full Markdown hoặc dump full DOCX XML vào context khi artifact JSON là đủ.
- Không được coi `body` là toàn bộ tài liệu. Với DOCX, scaffold ngoài vùng nội dung chính là phần của output bắt buộc phải giữ.
- Không được dùng chiến lược `clear whole body` trừ khi mode là `full-regenerate-from-schema` và người dùng đã chấp nhận rõ ràng.

## Invariant quan trọng cho append
Nếu `mode=append-structured-section` và `target_file` chưa tồn tại, phải sao chép `template_file` sang `target_file` trước khi chèn nội dung mới.

## Invariant quan trọng cho preserve scaffold
Nếu `mode=preserve-template-scaffold`, template không chỉ là nguồn style và layout:
- Giữ style, numbering, page setup, header/footer, section settings và các field cấu trúc khi phù hợp.
- Chỉ thay vùng nội dung được xác định trong `replace_ranges`.
- Không được xóa trắng toàn bộ `w:body` rồi đổ text mới vào.
- Nếu chưa resolve được `replace_ranges`, phải fail-closed thay vì build liều.

## Routing tối thiểu
- Luôn bắt đầu bằng workflow ngắn trong skill này.
- Chỉ load `officecli-docx` khi cần command syntax cụ thể.
- Load `md-to-docx-pipeline` khi cần sinh hoặc tiêu thụ artifact ngoài context.
- Load `docx-qa` trước khi bàn giao file, hoặc sớm hơn nếu task có TOC, references, appendix, danh mục hình/bảng, cross-reference, header/footer.

## Execution Contract cho prompt chỉ có `@task.md`
- Nếu task chỉ cung cấp `task.md`, agent vẫn phải tự dựng đầy đủ artifact và không được bỏ qua phase nào.
- Với `mode=preserve-template-scaffold`, thứ tự tối thiểu là:
  1. parse markdown
  2. profile template
  3. lập plan
  4. build file đích
  5. QA semantic + QA schema
- Không được nhảy từ đọc `task.md` sang gọi một chuỗi lệnh build ad-hoc rồi kết luận xong chỉ dựa trên `validate`.

## State Machine

### PHASE 0: Preflight
Mục tiêu: xác nhận mode, file vào/ra, môi trường và đường chạy.

Làm:
- Xác nhận file đầu vào tồn tại.
- Xác nhận `mode` hợp lệ.
- Nếu `mode=append-to-template`, xác nhận `target_file` và `insert_after`.
- Nếu `mode=append-to-template` mà `target_file` chưa tồn tại, sao chép `template_file` sang `target_file`.
- Nếu `mode=rebuild-from-template-format`, xác nhận `source_scope` và output đích.
- Chỉ kiểm tra OfficeCLI khi execution path thực sự cần OfficeCLI.

Checkpoint schema:
```json
{
  "phase": 0,
  "completed": true,
  "mode": "preserve-template-scaffold",
  "working_file": "report.docx",
  "issues": []
}
```

### PHASE 1: Analyze
Mục tiêu: lấy minimum context đủ để quyết định mapping.

Phải lấy:
- outline hoặc AST summary của `source_file`
- template profile rút gọn
- style map cho H1/H2/H3/body
- numbering map nếu template có numbered heading
- các section phụ thuộc: TOC, references, appendix, danh mục hình/bảng, cross-reference
- candidate range cho phần nội dung chính
- bằng chứng scaffold nào phải giữ

Không làm:
- không đọc toàn bộ file Markdown vào prompt nếu `content_outline.json` là đủ
- không dump toàn bộ XML hoặc full command output vào context

Artifact tối thiểu:
```json
{
  "phase": 1,
  "completed": true,
  "analysis": {
    "mode": "preserve-template-scaffold",
    "styles": {
      "h1": "Heading1",
      "h2": "Heading2",
      "h3": "Heading3",
      "body": "Normal"
    },
    "heading_numbering": true,
    "dependent_sections": ["toc", "references"],
    "replace_range_candidate": {
      "strategy": "after-front-matter-to-end-of-main-story",
      "status": "resolved"
    }
  },
  "issues": []
}
```

### PHASE 2: Plan
Mục tiêu: quyết định cách build mà không kéo thêm context không cần thiết.

Kết quả mong đợi:
- `content_ast.json`
- `content_outline.json`
- `template_profile.json`
- `plan.json`

Quy tắc:
- Với `preserve-template-scaffold`, plan phải chỉ rõ scaffold nào được giữ, range nào được thay và điều kiện nào buộc fail nếu range không resolve.
- Với `replace-main-content-range`, plan phải chỉ rõ anchor hoặc chỉ số range đã verify.
- Với `append-structured-section`, plan phải chỉ rõ anchor và thứ tự cập nhật phần phụ thuộc.
- Với `fill-declared-placeholders`, plan phải chỉ rõ placeholder map và chiến lược fallback.
- Với `full-regenerate-from-schema`, plan phải ghi rõ vì sao được phép tái tạo gần như toàn bộ.
- Với mọi mode, plan phải chỉ rõ cách phát hiện `template residue` sau khi build.

### PHASE 3: Execute
Mục tiêu: build file đích theo `plan.json`.

#### `preserve-template-scaffold`
- Khởi tạo file đích từ template.
- Giữ document-level settings cần thiết.
- Chỉ thay bounded range theo `plan.json`.
- Đánh dấu các phần phụ thuộc cần refresh hoặc rebuild.
- Không được chỉ thêm block mới vào body cũ nếu task yêu cầu thay nội dung chính.
- Nếu build engine không chứng minh được range đã resolve hoặc scaffold còn nguyên, phải fail thay vì tiếp tục finalize.

#### `replace-main-content-range`
- Làm việc trên `target_file`.
- Chỉ thay đúng range đã được verify.

#### `append-structured-section`
- Làm việc trên `target_file`.
- Không xoá nội dung cũ.
- Chèn nội dung mới tại anchor đã xác định.

#### `fill-declared-placeholders`
- Áp data vào placeholder.
- Báo rõ placeholder nào chưa map được.

#### `full-regenerate-from-schema`
- Chỉ dùng khi người dùng cho phép.
- Phải ghi rõ các thành phần scaffold chấp nhận tái tạo lại.

Checkpoint schema:
```json
{
  "phase": 3,
  "completed": true,
  "working_file": "report.docx",
  "artifacts": {
    "content_ast": ".office-auto/state/run-001/content_ast.json",
    "template_profile": ".office-auto/state/run-001/template_profile.json",
    "plan": ".office-auto/state/run-001/plan.json"
  },
  "issues": []
}
```

### PHASE 4: QA
Mục tiêu: xác nhận body đúng và các phần phụ thuộc không stale.

Kiểm tra bắt buộc:
- outline
- numbering
- TOC
- references
- appendix
- danh mục hình/bảng
- cross-reference
- header/footer
- placeholder leak
- validate/issues
- semantic text extract
- template residue
- duplicate chapter numbering
- scaffold preservation
- replace range resolution

Nếu một phần phụ thuộc chưa khớp, quay lại PHASE 3.

#### Hard gate riêng cho `preserve-template-scaffold`
- `qa_report.json` phải ghi rõ `source_heading_count`, `output_heading_count`, `residual_template_headings`, `duplicate_heading_patterns`, `body_replaced`, `scaffold_preserved`, `replace_ranges_resolved`.
- Không được coi là pass nếu `body_replaced != true`, `scaffold_preserved != true` hoặc `replace_ranges_resolved != true`.
- Các mẫu lỗi sau phải fail ngay:
  - `CHƯƠNG 1. CHƯƠNG 1`
  - `CHƯƠNG 2. CHƯƠNG 2`
  - `4.1. 1.1.` hoặc `5.1. 2.1.`
  - xuất hiện lại `TÀI LIỆU THAM KHẢO` thành hai chương khác nhau trong cùng tài liệu

### PHASE 5: Finalize
Mục tiêu: chốt artifact và trạng thái bàn giao.

Làm:
- đóng resident mode nếu có
- ghi `build_report.json`
- ghi `qa_report.json`
- cập nhật `run.json`

Output schema:
```json
{
  "phase": 5,
  "completed": true,
  "output_file": "report.docx",
  "final_status": "ready",
  "issues": []
}
```

## Failure Recovery
- Nếu mode không khớp với task, dừng và map lại mode trước khi chạy.
- Nếu thiếu artifact, tạo lại đúng artifact thiếu thay vì đọc lại toàn bộ input vào context.
- Nếu numbering sai, quay lại bước profile template và plan mapping.
- Nếu TOC, references hoặc appendix stale, quay lại execute hoặc repair, không được giao file.
- Nếu kết quả text extract cho thấy template residue hoặc duplicate heading, phải quay lại execute và sửa cách thay bounded range; không được vá bằng cách chỉ xóa vài heading lẻ.

## Anti-patterns
- Load `officecli-docx` như command encyclopedia cho mọi task `.docx`.
- Dùng `append` hoặc `full regenerate` để ép một task thực chất là preserve scaffold.
- Đưa full Markdown hoặc full OfficeCLI output vào prompt khi không cần.
- Chỉ sửa body mà bỏ qua TOC, references, header, footer.
- Xóa sạch `w:body` chỉ vì thấy cần “đồng bộ nội dung nhanh”.

## Delivery Rule
Chỉ coi là xong khi:
- mode đúng với yêu cầu
- artifact đã được ghi đủ để resume
- body mới đã được tạo đúng trong vùng được phép thay
- style, numbering, page setup được giữ hoặc map đúng
- scaffold quan trọng của template vẫn còn
- các phần phụ thuộc đã được rà soát
- QA pass
- với mode preserve scaffold, phải có bằng chứng rõ ràng rằng vùng cũ đã bị thay đúng, scaffold vẫn còn và không còn duplicate chapter patterns trong text extract