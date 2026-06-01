# DOCX Issue List 02: Correctness Regressions

## Mục tiêu

Track này xử lý các lỗi làm file DOCX đầu ra sai cấu trúc, sai semantics hoặc không ổn định dù build vẫn chạy hết.

## Issue hiện tại

1. Prototype heading có thể bị suy ra từ paragraph `Normal`, kéo theo drift giữa body text và heading semantics.
2. Roundtrip Markdown hiện cho thấy một số body paragraphs bị đọc lại như headings.
3. Validate hiện vẫn có warning schema ở `w:rPr/w:rFonts`, nghĩa là output OOXML chưa sạch.
4. Builder trước đây có xu hướng tiếp tục chạy dù có failure ở remove batch hoặc fallback clone/set.

## Bằng chứng trong repo

- [.office-auto/state/chuong2-md-case/roundtrip.md](../.office-auto/state/chuong2-md-case/roundtrip.md) cho thấy body text có lúc bị roundtrip thành heading Markdown.
- [.office-auto/state/chuong2-md-case/roundtrip_report.json](../.office-auto/state/chuong2-md-case/roundtrip_report.json) đang fail semantic fidelity.
- [.office-auto/state/chuong2-md-case/qa_report.json](../.office-auto/state/chuong2-md-case/qa_report.json) đang fail `outline_ok`, `section_breaks`, `semantic_roundtrip_ok` và `required_parts_present`.
- [profile_template.py](../.opencode/skills/md-to-docx-pipeline/scripts/profile_template.py) đang chọn prototype từ first matching paragraph trong live template body.

## Đã cải tiến trong workspace

1. [plan_mapping.py](../.opencode/skills/md-to-docx-pipeline/scripts/plan_mapping.py) nay gắn cờ `weak-heading-prototypes` khi nhiều heading roles thực chất rơi về style normal/default.
2. [build_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py) đã fail-closed nếu remove batch có lỗi, thay vì tiếp tục sinh file nửa chừng.
3. [build_docx.py](../.opencode/skills/md-to-docx-pipeline/scripts/build_docx.py) ghi `required_prototype_reservations` và `reserved_prototype_count` để debug prototype stability rõ hơn.

## Hướng xử lý tiếp theo

1. Tách prototype bank khỏi main body content: heading/list/reference/code prototypes phải lấy từ một scaffold section chuyên dụng hoặc sample semantic doc, không lấy ngẫu nhiên từ body đang bị thay.
2. Thêm `post_process_docx.py` cho các XML fixes nhẹ sau build, ví dụ run properties normalization hoặc cleanup metadata.
3. Bổ sung QA/repair dành riêng cho heading semantics: nếu roundtrip đẩy body thành heading, phải trace lại prototype style và run props được clone ở paragraph đó.
4. Viết thêm regression tests cho warning `w:rFonts` và cho case heading/body drift.

## Definition of done

- `officecli validate` không còn warning schema mới do pipeline tạo ra.
- `roundtrip_report.json` không còn extra headings giả phát sinh từ body paragraphs.
- `qa_report.json` pass outline, section breaks và semantic roundtrip cho case chuẩn.
- Prototype roles cho `h1/h2/h3` không còn trôi về `Normal` ở template được hỗ trợ.