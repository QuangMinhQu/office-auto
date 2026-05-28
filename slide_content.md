# Báo cáo Tuần 1 — Tự động hóa soạn thảo văn bản theo hình thức mẫu qua thiết kế Skills và tích hợp OfficeCLI

---

# 1. Giới thiệu / Bối cảnh Task

Báo cáo này trình bày tiến độ tuần đầu tiên trong quá trình xây dựng hệ thống tự động hóa tạo tài liệu văn phòng (Office Automation) từ nội dung Markdown, sử dụng mô hình ngôn ngữ lớn (LLM) kết hợp pipeline thực thi có kiểm soát chạy trên nền tảng OpenCode + Qwen.

## 1.1. Bài toán cụ thể

Task tuần 1 là sinh file `report.docx` từ nguồn nội dung `chuong_2.md`, nhưng **không phá vỡ scaffold hình thức** của file template `format_template.docx`. Các thành phần bắt buộc phải bảo toàn bao gồm: trang bìa, mục lục (TOC), danh mục hình, danh mục bảng, header/footer, section break, page number fields và toàn bộ numbering/style definition.

## 1.2. Thách thức cốt lõi

Thách thức căn bản không nằm ở việc thiếu prompt hay thiếu context. Vấn đề là workflow truyền thống đối xử tài liệu Office như một **khối văn bản thuần túy**, trong khi DOCX thực chất là một gói **Open XML** gồm nhiều part quan hệ chặt chẽ với nhau (`word/document.xml`, `word/styles.xml`, `word/numbering.xml`, header/footer parts,...). Chiến lược "xóa toàn bộ body rồi đổ nội dung mới vào" gần như chắc chắn sẽ phá hủy các phần hình thức này.

Từ đó, mode thực thi đúng phải là **`preserve-template-scaffold`** — chỉ thay thế vùng nội dung chính được xác định bởi anchor rõ ràng, trong khi toàn bộ scaffold phải được giữ nguyên và xác minh sau build.

---

# 2. Công việc liên quan (Related Work)

## 2.1. Agent Skills trong hệ thống LLM-based Agent

Trong các hệ thống agentic hiện đại như **OpenCode + Qwen**, **Skill** là đơn vị điều phối hành vi của agent — tương đương một *system prompt có scope hẹp* được load có điều kiện khi task phù hợp với mô tả của Skill đó.

Theo best practice của Anthropic và OpenCode:

- Skill nên **ngắn gọn, chỉ đóng vai trò điều phối** — không mang logic thực thi vào bên trong.
- Chi tiết phức tạp phải được **externalize** ra artifact (JSON), plan file và validator script riêng.
- Workflow phức tạp phải đi qua chu trình: `plan → validate → execute → verify`.
- Với mô hình reasoning như Qwen, **decision boundary phải rất rõ ràng** — nếu Skill name và description chỉ nói theo format file (`.docx`, `.xlsx`) thay vì theo intent thực sự, model dễ load sai Skill.

Trong project này, Skill đóng vai trò **quyết định mode** (ví dụ: `preserve-template-scaffold`, `replace-main-content-range`) và **khai báo contract** — phần nào cần giữ, phần nào được thay, anchor xác định phạm vi thay thế. Qwen chỉ nên ra quyết định ở tầng intent, phần sửa tài liệu thực sự phải giao cho execution engine.

Hiện tại, repo đã tổ chức **7 Skills** theo phân tầng rõ ràng:

| Skill | Vai trò |
|---|---|
| `docx-from-template` | Orchestrator chính cho tác vụ Word |
| `md-to-docx-pipeline` | Pipeline parse → profile → plan → build → QA ngoài context |
| `docx-qa` | Delivery gate: package QA, structural QA, range QA, semantic QA |
| `officecli-docx` | Command reference cho OfficeCLI với DOCX |
| `officecli-pptx` | Command reference cho OfficeCLI với PPTX |
| `officecli-xlsx` | Command reference cho OfficeCLI với XLSX |
| `officecli-mcp` | Cài đặt và đăng ký OfficeCLI MCP server cho agent |

Nguyên tắc routing được định nghĩa rõ trong `AGENTS.md`: với mọi task `preserve-template-scaffold` hoặc Markdown-to-DOCX, agent phải load `docx-from-template` trước, sau đó load `md-to-docx-pipeline`, và cuối cùng load `docx-qa` trước khi bàn giao.

## 2.2. OfficeCLI — Execution Engine cho Tài liệu Office

**OfficeCLI** là công cụ thao tác file Office (DOCX, PPTX, XLSX) ở tầng **Open XML structure**, không phải ở tầng văn bản thuần túy. Đây là điểm khác biệt then chốt so với `python-docx` hay các thư viện Python thông thường vốn có giới hạn về fidelity khi đụng đến master/layout/theme/advanced formatting.

OfficeCLI cung cấp ba tầng thao tác:

- **L1 (High-level):** Các lệnh `add`, `set`, `remove`, `move` thao tác trên element có tên rõ ràng.
- **L2 (Mid-level):** Thao tác field-level, numbering, style binding, TOC field rewrite.
- **L3 (Raw):** `raw`, `raw-set`, `add-part` — chỉ được dùng khi L1/L2 không hỗ trợ, và bắt buộc phải có giải trình trong `build_report.json`.

Vai trò của OfficeCLI trong hệ thống là **tầng thực thi dưới cùng**. Qwen sinh `plan.json` với operation intent, script validator kiểm tra plan, sau đó executor convert plan thành lệnh OfficeCLI theo một trong hai đường:

- **Resident mode:** `officecli open` → chuỗi `add/set/remove` → `officecli save` → `officecli close`
- **Batch mode:** Gom toàn bộ mutation vào một JSON array duy nhất, chạy `officecli batch`

Phân tầng này phù hợp với nguyên tắc *giảm degrees of freedom* — model không cần hiểu OOXML, chỉ cần hiểu intent và contract. Sau mỗi lần `close`, bắt buộc phải chạy `officecli validate <file> --json` như integrity gate tối thiểu.

---

# 3. Công việc đã Thực hiện trong Tuần

## 3.1. Thiết kế và triển khai pipeline `md-to-docx-pipeline`

Pipeline 5 bước đã được thiết kế và triển khai hoàn chỉnh dưới dạng các script Python độc lập tại `.opencode/skills/md-to-docx-pipeline/scripts/`:

```
parse_markdown.py  →  profile_template.py  →  plan_mapping.py  →  build_docx.py  →  qa_docx.py
```

Mỗi script có contract input/output rõ ràng và viết artifact JSON ra `run_dir` để agent chỉ cần thấy file path và summary JSON ngắn — không cần load toàn bộ nội dung Markdown hay XML vào context.

### Trách nhiệm từng script

| Script | Input | Output | Trách nhiệm chính |
|---|---|---|---|
| `parse_markdown.py` | `--source-file`, `--run-dir` | `content_ast.json`, `content_outline.json` | Parse Markdown thành AST có cấu trúc |
| `profile_template.py` | `--template-file`, `--run-dir` | `template_profile.json` | Phát hiện scaffold, TOC field, section, style, numbering, replace-range candidate |
| `plan_mapping.py` | `--mode`, `--run-dir`, paths | `plan.json`, cập nhật `run.json` | Normalize mode cũ, sinh `preserve`/`replace_ranges`/`post_conditions` |
| `build_docx.py` | `--run-dir` | `build_report.json` | Bounded replacement theo plan; fail-closed nếu range chưa resolve |
| `qa_docx.py` | `--run-dir` | `qa_report.json` | 4-tầng QA: package, structural, range, semantic |

## 3.2. Thiết kế hệ thống Skills phân tầng

7 Skills đã được tổ chức và viết theo nguyên tắc **phân tầng theo intent**, không chỉ theo extension file. Routing rule được định nghĩa tập trung tại `.opencode/AGENTS.md` để agent biết khi nào load skill nào và theo thứ tự nào.

Skill `md-to-docx-pipeline` được thiết kế với nguyên tắc **progressive disclosure**: Skill chỉ expose file path, mode, artifact path và summary JSON ngắn cho agent — toàn bộ detail về XML structure, command syntax và QA threshold được giấu trong script và artifact ngoài context.

## 3.3. Xây dựng Hard Gate và QA Contract

Hard gate cho mode `preserve-template-scaffold` được định nghĩa cụ thể, yêu cầu agent phải chứng minh đủ 6 điều kiện trước khi finalize, bao gồm:

- Scaffold còn nguyên: header/footer, section settings, TOC field, list-of-figures field
- `replace_ranges` ở trạng thái `resolved` trong `plan.json`, không phải suy đoán
- Outline file kết quả khớp `chuong_2.md` theo thứ tự
- Không có residue nội dung template cũ trong vùng đã thay
- Không có duplicate pattern: `CHƯƠNG 1. CHƯƠNG 1`, `4.1. 1.1.`,...

QA được tổ chức thành **4 tầng** trong `qa_docx.py`: Package QA → Structural QA → Range QA → Semantic QA.

## 3.4. Artifact và State Management

State của mỗi run được lưu tại `.office-auto/state/<run_id>/` với các artifact chuẩn:

```
preflight.json          ← OfficeCLI version, mode, paths
content_ast.json        ← AST của source Markdown
content_outline.json    ← Outline headings của source
template_profile.json   ← Scaffold, field, style, numbering của template
plan.json               ← preserve/replace_ranges/post_conditions đã resolve
build_report.json       ← Kết quả build, refresh strategy, L3 fallback log
qa_report.json          ← Kết quả 4-tầng QA
```

Script entry point `scripts/build_report.py` orchestrate toàn bộ pipeline và verify `officecli --version` làm preflight check bắt buộc trước khi chạy bất kỳ bước nào.

---

# 4. Vấn đề Gặp Phải & Cách Xử Lý

Trong quá trình chạy pipeline, run-005 đã xuất hiện 3 lỗi cụ thể với root cause và fix plan đã được phân tích chi tiết trong `issue.md`.

## 4.1. Lỗi TOC render ra text thô `TOC \o "1-3" \h \z \u`

**Root cause:** `build_docx.py` dùng `ET.tostring()` của stdlib Python để rebuild XML. `ET.tostring()` không preserve namespace prefix — tất cả `xmlns:w=...` bị rewrite thành `ns0`, `ns1`,... dẫn đến Word không nhận ra element thuộc namespace `w:` nữa. Nghiêm trọng hơn, logic `paragraph_index_to_body_child_range` chỉ count `w:p` nhưng không nhận diện `w:sdt` — nếu TOC nằm trong `w:sdt` hoặc trải qua nhiều `w:p` liên tiếp chứa `w:fldChar` + `w:instrText`, những paragraph đó bị include vào `replace_range` và bị xóa, để lại nội dung `instrText` thô.

**Hướng fix:** Trong `profile_template.py`, detect tất cả paragraph thuộc TOC field (từ `w:fldChar[@fldCharType='begin']` chứa `instrText` có `TOC` đến `w:fldChar[@fldCharType='end']`) và **exclude hoàn toàn** các paragraph này khỏi `replace_range` trước khi sinh `plan.json`.

## 4.2. Heading bị double-numbering — `1.2 1.2. Các thách thức...`

**Root cause:** Template đã có `w:numPr` gắn vào heading style (Word tự render số từ `word/numbering.xml`). Trong khi đó, `parse_markdown.py` giữ nguyên prefix số trong heading text từ Markdown (ví dụ: `"1.2. Các thách thức..."`). Kết quả: số từ `w:numPr` (auto) + số từ text (literal) = double-numbering.

**Hướng fix:** Trong `parse_markdown.py`, strip prefix numbering khỏi heading text trước khi lưu vào `block["text"]` — regex xử lý các dạng `CHƯƠNG N.`, `1.`, `1.2.`, `1.2.3.` và tương tự.

## 4.3. References là text thô, không phải auto-numbering

**Root cause:** Script build tạo paragraph references với style `"References"` nhưng không gắn `w:numPr`. Trong template chuẩn, mỗi entry references là một `w:p` linked đến `w:abstractNum` có `w:numFmt` là `decimal` dạng `[%1]` — số `[1]`, `[2]`,... là field value do Word render, không phải text literal. Thêm vào đó, `profile_template.py` chưa extract `style_numbering` map từ `word/styles.xml`.

**Hướng fix (3 bước):** Strip prefix `[N]` trong `parse_markdown.py` → bổ sung `style_numbering` extraction trong `profile_template.py` → gắn `w:numPr` vào paragraph references trong `build_docx.py` khi style của references có numbering trong template profile.

---

# 6. Kế hoạch Tuần Tiếp Theo

- Implement fix cho cả 3 lỗi theo thứ tự ưu tiên: heading double-numbering (1 file, ít dòng, impact ngay) → TOC detection & exclude (phức tạp hơn, cần test kỹ) → references numbering (cần thêm field `style_numbering` vào `profile_template.py` trước).
- Chạy lại pipeline từ bước `parse_markdown.py` sau mỗi fix để verify fix không gây regression.
- Bổ sung `style_numbering` vào schema của `template_profile.json` và cập nhật `run.schema.json` tương ứng.
- Nâng tầng QA trong `qa_docx.py`: thêm kiểm tra TOC hyperlink/anchor còn hợp lệ sau build và kiểm tra numbering definition không bị broken trong `word/numbering.xml`.
- Đánh giá khả năng dùng **batch mode** thay resident mode cho build step để tránh vấn đề mở/đóng file nhiều lần gây mất namespace binding.
