# Tóm tắt state gần nhất của OpenCode cho report.docx

Tài liệu này gom các value chính trong state của run gần nhất để dùng khi trao đổi với thầy. Run hiện tại là manual-run, target file là report.docx, và pipeline đã chạy xong với QA pass.

## 1. Thông tin tổng quan

| Trường | Giá trị |
| --- | --- |
| Run dir | .office-auto/state/manual-run |
| Status | completed |
| Mode | preserve-template-scaffold |
| Source file | chuong_2.md |
| Template file | format_template.docx |
| Effective template | .office-auto/state/manual-run/effective_template.docx |
| Target file | report.docx |
| OfficeCLI version | 1.0.102 |
| Started at | 2026-05-31T16:37:29+00:00 |
| Finished at | 2026-05-31T16:45:56+00:00 |
| Duration | 507.108 seconds |
| Failed step | null |
| Review attention count | 4 |

## 2. Các artifact có trong state

State này chứa nhiều file phụ trợ. Các file quan trọng nhất là:

- run.json: cấu hình run và selected replace range.
- preflight.json: thông tin khởi tạo pipeline.
- template_preparation_report.json: kết quả derive effective template.
- source_template_profile.json: profile của template gốc format_template.docx.
- template_profile.json: profile của effective template.
- input_report.json: kết quả xử lý đầu vào Markdown.
- content_ast.json: AST của nội dung Markdown đã normalize.
- content_outline.json: outline sinh từ nội dung nguồn.
- plan.json: kế hoạch mapping và execution strategy.
- execution_plan.json: operation graph thực thi.
- build_report.json: kết quả build DOCX.
- roundtrip_report.json: kiểm tra MarkItDown roundtrip.
- qa_report.json: QA gate cuối.
- review_report.json và review_report.md: kết quả review format/semantic.

## 3. Cấu hình state và replace range

### Run config

| Trường | Giá trị |
| --- | --- |
| mode_requested | preserve-template-scaffold |
| mode | preserve-template-scaffold |
| source_file | chuong_2.md |
| template_file | .office-auto/state/manual-run/effective_template.docx |
| target_file | report.docx |
| preserve | page-setup, section-breaks, styles-and-numbering |
| status | ready |

### Selected replace range

| Trường | Giá trị |
| --- | --- |
| name | after-front-matter-to-end-of-main-story |
| status | resolved |
| paragraph_start_index | 14 |
| paragraph_end_index | 13 |
| remove_paths | [] |
| insert_after_path | /body/p[@paraId=00102590] |
| remove_scope | direct-body-children |
| preserve_zones | front-matter |
| preserves_front_matter | true |

### Preserve zone

| Zone | Start | End | Notes |
| --- | --- | --- | --- |
| front-matter | paragraph 0 | paragraph 13 | Bắt đầu tại /body/tbl[1]/tr[1]/tc[1]/p[@paraId=00100000], kết thúc tại /body/p[@paraId=0010001A] |

## 4. Format và mapping quan trọng

### Style map

| Role | Style |
| --- | --- |
| h1 | Heading2 |
| h2 | Heading2 |
| h3 | Heading3 |
| body | Normal |
| list | ListParagraph |
| reference | ListParagraph |
| blockquote | Normal |
| code | Normal |

### Render roles

| Render role | Mapped role |
| --- | --- |
| heading_level_1 | h1 |
| heading_level_2 | h2 |
| heading_level_3_plus | h3 |
| paragraph | body |
| list_item | list |
| reference | reference |
| blockquote | blockquote |
| code_block | code |
| table | table |

### Prototype roles

Tất cả các role sau đều trỏ về cùng một prototype path trong effective template:

- body: /body/p[@paraId=0010000C]
- reference: /body/p[@paraId=0010000C]
- blockquote: /body/p[@paraId=0010000C]
- code: /body/p[@paraId=0010000C]

### Template profile chính

| Trường | Effective template |
| --- | --- |
| template_file | .office-auto/state/manual-run/effective_template.docx |
| paragraphs | 13 |
| tables | 1 |
| images | 0 |
| equations | 0 |
| headings | 0 |
| styleDistribution | Normal: 13 |
| fontUsage | Times New Roman: 10 |
| fontSizeUsage | 10pt: 10 |

### Source template profile chính

| Trường | Source template |
| --- | --- |
| template_file | format_template.docx |
| paragraphs | 3302 |
| tables | 104 |
| images | 5 |
| equations | 0 |
| headings | 0 |
| styleDistribution | Normal: 3293, Normal (Web): 9 |
| fontUsage | Times New Roman: 3494, Arial: 21 |
| fontSizeUsage | 10pt: 3515 |

## 5. Kết quả semantic grounding và input

### Input report

| Trường | Giá trị |
| --- | --- |
| status | completed |
| source_file | chuong_2.md |
| normalized_file | .office-auto/state/manual-run/normalized.md |
| source_extension | .md |
| mode | pass-through |
| converter | none |
| style_map_used | false |

### Content AST và outline

| Trường | Giá trị |
| --- | --- |
| content_ast parser | markdown-it-py |
| content_ast block_count | 188 |
| content_outline heading_count | 99 |
| sample_outline heading_count | 0 |
| sample_content_report converter | MarkItDown |
| sample_content_report style_map_used | true |

### Source render window

| Trường | Giá trị |
| --- | --- |
| strategy | skip-prefix-covered-by-template-scaffold |
| start_block_index | 7 |
| start_line | 17 |
| trimmed_prefix_block_count | 7 |
| shared_cover_signals | decree, government, motto, nation, serial |
| anchor_text | CHƯƠNG I. NHỮNG QUY ĐỊNH CHUNG |

## 6. Template preparation và execution graph

### Template preparation report

| Trường | Giá trị |
| --- | --- |
| status | prepared |
| source_template_file | format_template.docx |
| effective_template_file | .office-auto/state/manual-run/effective_template.docx |
| selected_candidate | after-front-matter-to-end-of-main-story |
| removed_child_count | 3392 |
| cache_key | 60affc41fd9763e9 |
| cache_hit | false |

### Guardrails của template preparation

| Trường | Giá trị |
| --- | --- |
| direct_body_child_count | 3406 |
| selected_range_remove_count | 3392 |
| selected_range_remove_ratio | 0.9959 |
| preserve_part_signal_count | 0 |
| risk_flags | oversized-template-body, whole-body-rewrite, full-document-template-disguised-as-format, weak-heading-prototypes |
| build_allowed | false |
| blocking_reasons | Template hiện tại buộc pipeline xóa gần toàn bộ body nhưng không có đủ preserve-part signals; cần template scaffold mỏng hơn hoặc strategy rewrite khác. |

### Plan report

| Trường | Giá trị |
| --- | --- |
| contract_version | 2.0 |
| heading_count | 98 |
| source_heading_count_raw | 99 |
| has_numbering | true |
| execution_strategy | officecli-operation-graph |
| status | ready-for-execution |
| semantic_grounding file | .office-auto/state/manual-run/normalized.md |
| post_conditions | headers-footers-preserved, section-breaks-preserved, heading-style-mapped-to-template, prototype-driven-rendering-used-for-paragraph-blocks, no-template-body-residue-inside-replaced-range, toc-fields-preserved-or-rewritten-for-refresh, replace-range-operates-on-direct-body-children |

## 7. Build, QA, review

### Build report

| Trường | Giá trị |
| --- | --- |
| status | completed |
| body_children_before | 1 |
| body_children_after | 2 |
| remove_scope | direct-body-children |
| removed_child_count | 0 |
| inserted_block_count | 181 |
| render_summary | paragraph_like_ops: 180, table_ops: 1 |
| resident_mode | true |
| prefer_direct_create | true |
| batched_simple_paragraph_ops | 178 |
| estimated_minimum_officecli_calls | 380 |

### Roundtrip report

| Trường | Giá trị |
| --- | --- |
| status | passed |
| target_file | report.docx |
| heading_subsequence_ok | true |
| missing_headings | [] |
| extra_headings | [] |
| table_count_source | 1 |
| table_count_roundtrip | 1 |
| body_text_similarity | 0.9999 |
| math_literal_count_source | 0 |
| math_literal_count_roundtrip | 0 |

### QA report

| Trường | Giá trị |
| --- | --- |
| status | passed |
| source_heading_count | 98 |
| output_heading_count | 98 |
| required_preserve | page-setup, section-breaks, styles-and-numbering |
| required_parts_present | true |
| scaffold_preserved | true |
| replace_ranges_resolved | true |
| execution_plan_ready | true |
| outline_ok | true |
| body_replaced_ok | true |
| remove_strategy_ok | true |
| template_residue | false |
| severe_issue_count | 0 |
| toc_refresh_strategy | none |

### Review report

| Trường | Giá trị |
| --- | --- |
| status | completed |
| qa_status | passed |
| baseline file | .office-auto/state/manual-run/effective_template.docx |
| original template | format_template.docx |
| target file | report.docx |
| baseline paragraphs | 17 |
| output paragraphs | 209 |
| inserted paragraphs reviewed | 180 |
| inserted paragraphs with format differences | 1 |
| inserted paragraphs needing attention | 4 |

### Review risk flags

| Risk flag | Count |
| --- | ---: |
| body-centered | 3 |
| font-size-drift | 1 |
| font-family-drift | 1 |

### Suspicious paragraphs từ review

- index 162: body paragraph rỗng, expected Normal, align center, size 10pt, font Arial; actual size 11pt, font null.
- index 164: reference paragraph [1] ISO 19650-1:2018..., risk body-centered.
- index 165: reference paragraph [2] BuildingSMART International..., risk body-centered.
- index 166: reference paragraph [3] Bộ Xây dựng..., risk body-centered.

## 8. Kết luận ngắn để hỏi thầy

Điểm chính của state này là pipeline đã chạy thành công theo mode preserve-template-scaffold, giữ được scaffold đầu tài liệu, map được heading/body theo style của template, và QA/roundtrip đều pass. Tuy nhiên, template preparation report vẫn ghi rõ format_template.docx đang mang rủi ro kiểu full-document disguised-as-format, tức là nếu coi nó như template chuẩn thì phải cẩn thận vì gần như toàn bộ body cũ bị xóa để tạo effective template.

Nếu cần hỏi thầy, có thể xoay quanh 3 câu này:

1. Vì sao template gốc format_template.docx lại bị xem là template quá nặng, dẫn tới selected_range_remove_ratio = 0.9959 và build_allowed = false ở bước preparation?
2. Với output hiện tại, liệu việc giữ page-setup, section-breaks, styles-and-numbering như scaffold là đủ để coi là preserve-template-scaffold đúng nghĩa không?
3. Phần review còn 4 điểm attention về body-centered và drift font-size/font-family, có nên sửa ở source Markdown, style map, hay prototype của template?

## 9. File liên quan

- [run.json](.office-auto/state/manual-run/run.json)
- [plan.json](.office-auto/state/manual-run/plan.json)
- [execution_plan.json](.office-auto/state/manual-run/execution_plan.json)
- [build_report.json](.office-auto/state/manual-run/build_report.json)
- [qa_report.json](.office-auto/state/manual-run/qa_report.json)
- [review_report.md](.office-auto/state/manual-run/review_report.md)
- [review_report.json](.office-auto/state/manual-run/review_report.json)
- [template_profile.json](.office-auto/state/manual-run/template_profile.json)
- [source_template_profile.json](.office-auto/state/manual-run/source_template_profile.json)