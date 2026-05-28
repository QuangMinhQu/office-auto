# Task: Tạo report.pptx theo contract preserve-template-scaffold

Mục tiêu là sinh `report.pptx` từ `slide_content.md` nhưng không được đối xử `format_template.pptx` như một bộ theme/style rời rạc. File đích phải giữ nguyên scaffold trình chiếu của template và chỉ thay hoặc thêm phần nội dung slide theo narrative đã có trong Markdown.

## Skill alignment

- Skill tham chiếu cú pháp là `.opencode/skills/officecli-pptx`.
- Skill này chỉ được dùng để tra cứu lệnh, schema element, prop name, path và execution rule của OfficeCLI.
- Không dùng `officecli-pptx` như workflow orchestrator. Workflow phải đi qua artifact JSON và bounded mutation plan.
- Thứ tự tra cứu khi cần command detail: `SKILL.md` -> `references/view-query.md` -> `references/elements.md` -> `references/text-formatting.md` -> `references/layouts-masters.md` -> `references/batch-resident.md` -> `officecli help pptx ...`.

## Chế độ thực hiện

- `mode`: preserve-template-scaffold
- `template_file`: `format_template.pptx`
- `target_file`: `report.pptx`
- `source_file`: `slide_content.md`
- `source_scope`: full-document

## Thành phần phải giữ

- Slide master, slide layouts và theme của template.
- Title slide hoặc opening slide nếu template đang có.
- Kích thước slide, background, font theme, color palette.
- Placeholder bindings, textbox regions và content slots do layout định nghĩa.
- Header/footer, slide number, date/footer placeholder nếu template có.
- Notes pages, section ordering và mọi ràng buộc cấu trúc ở cấp presentation package nếu template đang dùng.

## Thành phần được phép thay

- Vùng slide nội dung chính của deck, được xác định bằng `replace_ranges` hoặc mapping placeholder trong `plan.json`.
- Được phép thêm slide mới nếu cần để phủ hết nội dung của `slide_content.md`, nhưng phải dựa trên layout có sẵn hoặc layout-compatible trong template.
- Ưu tiên điền nội dung vào placeholder/textbox region đã được layout định nghĩa trước khi thêm shape mới.
- Mọi slide mới phải có `slide-to-layout mapping` rõ trong `plan.json` và nằm trong insertion zone hoặc replace range đã resolve từ `template_profile.json`.
- Nếu chưa xác định được `replace_ranges` hoặc `slide-placement strategy` một cách có căn cứ, agent phải dừng ở trạng thái `blocked`, không được tự ý xóa toàn bộ deck rồi sinh lại từ đầu.

## Contract bắt buộc

```yaml
mode: preserve-template-scaffold
template_file: format_template.pptx
target_file: report.pptx
source_file: slide_content.md
source_scope: full-document
preserve:
	- title-slide
	- slide-masters-and-layouts
	- theme-colors-fonts
	- slide-size-and-background
	- placeholder-bindings
	- layout-placeholder-regions-and-content-slots
	- headers-footers-and-slide-numbers
	- notes-pages-if-present
	- presentation-structure
replace_ranges:
	- strategy: after-title-slide-to-end-of-main-story
		required: true
post_conditions:
	- title-slide-still-present-if-template-had-it
	- masters-and-layouts-preserved
	- placeholder-bindings-not-broken
	- layout-mapping-resolved-in-plan
	- slide-order-matches-source-outline
	- no-template-slide-residue-inside-replaced-range
	- no-offslide-or-overflow-text-in-final-deck
```

## Hard gate bắt buộc

Agent không được kết luận xong chỉ vì `validate` pass.

Trước khi bàn giao `report.pptx`, agent phải tự chứng minh tất cả các điều sau:

1. Scaffold của template vẫn còn, tối thiểu gồm slide master, layout binding, theme, slide size và footer/slide number nếu template có.
2. `replace_ranges` hoặc slide-placement plan đã được resolve bằng artifact, không phải suy đoán tay trong prompt.
3. Outline của deck kết quả khớp outline/narrative của `slide_content.md` theo thứ tự hợp lý.
4. Không còn residue của nội dung mẫu cũ bên trong các slide đã thay hoặc vùng đã remap.
5. Không có các mẫu lỗi semantic hoặc markdown residue sau trong text extract của deck:
	 - `# `
	 - raw code fence marker
	 - `{{`
	 - `Click to add text`
	 - `Lorem ipsum`
6. Không có placeholder, layout hoặc scaffold bị mất rồi bị coi là “không quan trọng”.
7. Không có slide bị tràn chữ rõ rệt, text nằm ngoài khung hiển thị hoặc title/bullet bị lặp vô lý giữa các slide.
8. Mọi slide mới hoặc slide đã remap đều chứng minh được layout đã dùng và placeholder targets đã điền là gì.
9. Nếu task phải xuống L3 (`raw`, `raw-set`, `add-part`), phải ghi rõ lý do, target part và hậu kiểm structural sau mutation.

Nếu chưa chứng minh được các điều trên, agent phải coi task là chưa xong.

## Quy trình tối thiểu phải đi qua

1. Parse `slide_content.md` thành `content_ast.json` và `content_outline.json`.
2. Profile `format_template.pptx` để lấy `template_profile.json`, bao gồm master, layouts, placeholders, theme, slide size, footer/slide number, notes presence và candidate replace range hoặc insertion zone.
3. Lập `plan.json` với `preserve`, `replace_ranges`, `post_conditions`, slide-to-layout mapping, placeholder remap plan, execution strategy và fallback boundary.
4. Build `report.pptx` theo bounded replacement hoặc bounded slide insertion, không dùng chiến lược xóa sạch toàn bộ slide deck rồi dựng lại tùy ý.
5. Trong build step, ưu tiên mutate placeholder/textbox có sẵn; chỉ thêm shape mới khi layout hiện có không đủ slot và quyết định đó đã được ghi trong `plan.json`.
6. Chạy QA package + structural + layout + semantic + residue scan trước khi finalize.

## Artifact bắt buộc

- `content_ast.json`: AST toàn tài liệu Markdown để trace narrative source.
- `content_outline.json`: outline slide-level sẽ dùng để đối chiếu thứ tự deck cuối.
- `template_profile.json`: bằng chứng scaffold của template, bao gồm slide master, layouts, placeholder bindings, theme, slide size, footer/slide number, notes presence và replace/insertion candidates.
- `plan.json`: bằng chứng resolve bounded replacement, gồm `preserve`, `replace_ranges`, `slide-to-layout mapping`, placeholder targets, insertion/remap strategy và post-conditions.
- `qa_report.json` hoặc artifact QA tương đương: tổng hợp package, structural, layout, semantic, residue checks và kết luận pass/fail theo hard gate.

## Execution discipline

- Nếu cần tra cứu cú pháp OfficeCLI, phải theo help-first rule của skill `officecli-pptx`.
- Nếu mutation nhiều bước, ưu tiên resident mode hoặc một `batch` JSON array duy nhất thay vì nhiều vòng `open`/`close` rời rạc.
- Sau mỗi thay đổi cấu trúc như thêm slide, đổi layout, chèn chart/media hoặc remap placeholder, phải đọc lại nhánh vừa sửa bằng `get`, `view` hoặc `query`.
- Nếu cần kiểm tra overflow hoặc overlap, phải dùng preview/layout QA thay vì kết luận bằng mắt từ prompt.
- Không được dùng `raw-l3` chỉ vì tiện; chỉ hạ xuống L3 khi L1/L2 không đủ và phải log lý do trong artifact build/QA.

## Kết quả mong muốn

- File đầu ra là `report.pptx`.
- `report.pptx` phản ánh đầy đủ narrative hiện có trong `slide_content.md` dưới dạng deck báo cáo tuần 1.
- Template tiếp tục giữ scaffold trình chiếu thay vì chỉ còn vai trò “nguồn theme/style”.
- File cuối phải có title slide, các slide nội dung và thứ tự trình bày nhất quán với báo cáo trong Markdown.
- File cuối phải validate sạch, không còn placeholder thừa, không mất slide master/layout hoặc footer/slide-number nếu template ban đầu có.
- File cuối không được để lộ raw markdown, duplicate title pattern hoặc text tràn khung hiển thị rõ rệt.