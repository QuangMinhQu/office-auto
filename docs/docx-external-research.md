# DOCX External Research Notes

## Mục tiêu

Tài liệu này chốt lại external knowledge và các GitHub repos uy tín liên quan trực tiếp đến hướng phát triển workspace DOCX.

## Repo và kết luận chính

### 1. Microsoft MarkItDown

Repo: https://github.com/microsoft/markitdown

Kết luận:

- Đây là reader/converter nhiều định dạng sang Markdown cho LLM/text analysis, không phải high-fidelity DOCX writer.
- Phù hợp nhất với workspace này ở 2 điểm: input normalization và output roundtrip QA.
- Tài liệu của repo cũng nhấn mạnh nên gọi API hẹp như `convert_local()` thay vì `convert()` khi chạy trong pipeline server-side hoặc input ít tin cậy.

### 2. Mammoth

Repo: https://github.com/mwilliamson/python-mammoth

Kết luận:

- Mammoth chuyển DOCX sang HTML/Markdown dựa trên semantic styles, cố tình bỏ qua phần lớn visual formatting.
- Custom style map của Mammoth rất hữu ích để xây `markitdown_style_map.txt` hoặc semantic oracle cho roundtrip.
- Repo cảnh báo rõ về security và pathological performance với untrusted documents, nên các bước conversion nên có timeout/memory guard nếu mở ra cho user input rộng.

### 3. Open XML SDK

Repo: https://github.com/dotnet/Open-XML-SDK

Kết luận:

- Đây là low-level framework cho Open XML packages, gần với cách OOXML thật sự hoạt động.
- Repo và docs liên quan nhấn mạnh các high-performance scenarios và việc thao tác trên packages/parts thay vì suy nghĩ theo Word UI object model.
- Bài học áp dụng: với replacement lớn, hướng đúng là one-pass rewrite ở part level hoặc streaming reader/writer, không phải hàng trăm mutation nhỏ lên package.

### 4. Docxtemplater

Repo: https://github.com/open-xml-templating/docxtemplater

Kết luận:

- Templating engine rất mạnh cho placeholder/loop/conditional trên template DOCX/PPTX/XLSX.
- Bài học lớn nhất không phải chuyển repo này sang docxtemplater, mà là kỷ luật template-first: template cần có vùng thay thế rõ, placeholders rõ, modules rõ, thay vì coi cả tài liệu cũ là format template.

### 5. python-docx-template

Repo: https://github.com/elapouya/python-docx-template

Kết luận:

- Cũng đi theo triết lý: tạo template bằng Word, chèn tags vào template, rồi render từ context.
- Bài học áp dụng là template nên do người biên tập chuẩn bị để render ổn định; khi không có placeholder discipline, renderer phải chịu nhiều heuristic và rủi ro hơn.

## Hướng phù hợp nhất cho workspace này

1. Giữ OfficeCLI và builder hiện tại làm writer path chính vì đây mới là đường preserve scaffold trong repo.
2. Giữ MarkItDown và Mammoth ở vai trò semantic reader: normalize input, extract sample semantic grounding, và roundtrip QA.
3. Thêm strategy builder mới cho replacement lớn, theo tinh thần package-part rewrite thay vì mutate-by-command quá nhiều.
4. Siết template discipline: format file user cung cấp cần được phân loại là `scaffold template`, `full historical document`, hay `sample semantic document`, không được nhập nhằng.

## Kết luận kỹ thuật ngắn

- Không có external repo nào gợi ý rằng MarkItDown/Mammoth nên thay thế DOCX writer trong bài toán preserve format.
- Các repo writer/template mạnh đều dựa vào template discipline rất rõ.
- Các repo low-level Open XML cho thấy muốn scale tốt thì phải giảm số mutation trên package và tiến dần tới part-level rewrite.

## Nghiên cứu mới: làm DOCX trực tiếp trong VS Code và qua MCP

### Tóm tắt nhanh

- Các lựa chọn mới chia thành 3 nhóm rõ ràng: `editor/viewer trong VS Code`, `agent integration cho DOCX`, và `viewer read-only`.
- Với workspace này, giá trị lớn nhất không nằm ở việc thay toàn bộ builder hiện tại, mà ở việc thêm lớp `review`, `redline/comment`, và `debug/inspection` sau bước build.
- Phần `preserve-template-scaffold` và bounded replacement hiện tại vẫn nên giữ làm đường build chính vì nó deterministic hơn và đã có roundtrip + QA artifacts bọc quanh.

### 1. SuperDoc

Nguồn:

- VS Code Marketplace: SuperDoc for VS Code

Kết luận:

- Đây là lựa chọn mạnh nhất cho `human-in-the-loop review` ngay trong VS Code: render DOCX đầy đủ, edit in place, tracked changes, comments, live reload, auto-save.
- Điểm khác biệt thực sự quan trọng là SuperDoc có integration server đi kèm, nên agent có thể đọc/sửa/comment trực tiếp lên `.docx` và người dùng nhìn thấy thay đổi realtime trong editor.
- Vì có UI render + edit, nó phù hợp nhất làm lớp review cuối cho `report.docx` sau khi pipeline đã build xong.
- Nó không phải thay thế trực tiếp tốt cho builder deterministic hiện tại. Lý do: workflow của SuperDoc nghiêng về editor/session-based editing, còn pipeline hiện tại cần bounded replacement, artifact hóa từng stage, và fail-closed khi range chưa resolve.
- Cần lưu ý license AGPL-3.0 cho bản open-source; nếu nhúng sâu vào sản phẩm/phân phối thì phải xem kỹ nghĩa vụ license.

Fit với pipeline:

- Nên nhúng vào bước `post-build review`.
- Có thể dùng để mở `report.docx` hoặc output smoke case ngay trong VS Code thay cho phải mở Word ngoài editor.
- Có thể dùng để cho agent tạo `tracked changes` và `comments` trên output thay vì sửa thẳng file cuối một cách silent.
- Không nên dùng để thay `scripts/build_docx.py` ở giai đoạn này.

### 2. securityronin/docx-mcp

Nguồn:

- mcpservers.org listing và docs cho `docx-mcp`

Kết luận:

- Đây là MCP candidate mạnh nhất nếu mục tiêu là cho agent thao tác DOCX ở mức review/professional editing, không cần UI riêng.
- Điểm mạnh khác biệt: tracked changes thật, comments, footnotes, headers/footers, protection, structural audit, diff ra `.docx` có redlines, và change-summary dạng text.
- Hướng tiếp cận là edit OOXML trực tiếp và validate trước khi save; điều này gần hơn với nhu cầu tài liệu pháp lý/báo cáo chính thức so với các wrapper mức cao.
- Nó đặc biệt hợp với workflow `build xong -> agent redline -> reviewer duyệt`.
- Nó cũng có `create_from_markdown(..., template_path=...)`, nhưng hướng đó vẫn là một pipeline khác. Chưa có bằng chứng nó hiểu preserve zones, resolved replace ranges, hay semantic-grounding contracts của repo này tốt hơn pipeline hiện tại.

Fit với pipeline:

- Ứng viên tốt nhất để thêm bước `post-build redline/comment/audit`.
- Có thể thay hoặc bổ sung một phần `qa_docx.py` ở lớp audit OOXML nâng cao, nhất là các check kiểu headings, bookmarks, footnotes, watermark, comments.
- Có thể thêm mode `review-docx` hoặc `annotate-docx` thay vì thay builder chính.
- Không nên thay toàn bộ đường build chính ngay bây giờ.

### 3. Office-Word-MCP-Server

Nguồn:

- GitHub repo `GongRzhe/Office-Word-MCP-Server`

Kết luận:

- Tool này giàu tính năng và cộng đồng dùng lớn hơn, hỗ trợ nhiều thao tác content/table/list/formatting/comment extraction.
- Tuy nhiên repo hiện đã bị archive vào tháng 3/2026, tức là không còn là lựa chọn tốt nhất cho dependency chiến lược mới.
- Nó phù hợp hơn như nguồn tham khảo capability surface hoặc fallback thử nghiệm, không phải nền tảng nên đầu tư tích hợp sâu.

Fit với pipeline:

- Không nên chọn làm hướng chính để nhúng mới.
- Nếu cần POC nhanh cho vài thao tác paragraph/table/comment extraction thì có thể thử, nhưng không nên đặt vào luồng chính.

### 4. hongkongkiwi/docx-mcp

Nguồn:

- GitHub repo `hongkongkiwi/docx-mcp`

Kết luận:

- Đây là một integration server thuần Rust, thiên về create/edit/convert/manage tài liệu với nhiều tool cơ bản và một số security knobs tốt như readonly, whitelist, blacklist, sandbox, size limit.
- Nó mạnh ở document automation đa dụng, conversion sang PDF/images, extract text, table/list/heading creation.
- Nhưng capability bề mặt hiện đọc được có vẻ nghiêng về general document automation hơn là tracked-review workflow sâu kiểu legal redline/comment threads.
- Với repo này, nó có thể chồng lấn nhiều với những gì OfficeCLI + builder hiện đã làm, nhưng chưa thể hiện rõ lợi thế quyết định về preserve-template-scaffold.

Fit với pipeline:

- Có thể hữu ích cho nhánh phụ như export preview image/PDF hoặc agent-driven inspection trong môi trường sandboxed.
- Không phải lựa chọn đầu tiên để thay builder hiện tại.

### 5. Read-only viewers

Nguồn:

- `AdamRaichu/vscode-docx-viewer`
- `skfrost19/Docx-Viewer`

Kết luận:

- Đây là lựa chọn chỉ để đọc/preview trong VS Code.
- Chúng có ích cho smoke review nhanh của output `.docx`, nhưng không mở rộng được năng lực agent chỉnh sửa tài liệu.
- Một số viewer còn dựa trên Mammoth/docxjs, tức là phù hợp để xem nhanh chứ không phải oracle cho fidelity tuyệt đối.

Fit với pipeline:

- Chỉ nên coi là tiện ích dev UX.
- Không thay được bất kỳ stage cốt lõi nào.

## Mapping trực tiếp vào pipeline hiện tại

Pipeline hiện tại:

1. profile template
2. prepare scaffold
3. generate style map
4. normalize input
5. extract sample semantic scaffold
6. parse markdown
7. plan mapping
8. compile execution plan
9. build docx
10. roundtrip markitdown
11. qa docx

Khả năng nhúng thực tế:

- `SuperDoc`:
	- Thêm sau bước 9 hoặc 11 để reviewer mở output ngay trong VS Code.
	- Nếu nối MCP của SuperDoc, agent có thể tạo review comments hoặc tracked changes trên `report.docx` sau khi build.
- `securityronin/docx-mcp`:
	- Có thể thêm như bước 11.5: audit/redline/comment/change-summary.
	- Có thể dùng để tạo `report_reviewed.docx` và `report_changes.txt` sau build.
- `hongkongkiwi/docx-mcp`:
	- Hợp hơn cho nhánh phụ export PDF/images hoặc inspect tài liệu trong sandbox.
- `read-only viewers`:
	- Chỉ thêm vào workflow dev/review local.

Những phần chưa nên thay:

- `plan_mapping.py`: MCP/editor tools không thay được logic semantic-grounding và replace-range resolution riêng của repo.
- `compile_execution_plan.py`: đây là chỗ compile deterministic từ AST sang operations; các editor/MCP tools không cung cấp contract tương đương.
- `build_docx.py`: hiện là writer bounded-replacement có báo cáo artifact rõ ràng; đổi sang editor-style mutations sẽ làm mất tính deterministic nếu chưa bọc lại bằng contract tương đương.
- `roundtrip_markitdown.py` và `qa_docx.py`: vẫn cần giữ vì đây là lớp xác minh độc lập với writer/editor.

## Đề xuất kiến trúc

### Phương án tốt nhất hiện tại

1. Giữ pipeline hiện tại làm `generation path` chuẩn.
2. Thêm `SuperDoc` như lớp `review UI` trong VS Code.
3. Thêm `securityronin/docx-mcp` như lớp `agent-side review/audit` tùy chọn sau build.
4. Chỉ cân nhắc thay writer path khi có bằng chứng rõ rằng MCP path mới giữ được cả 4 điều kiện:
	 - preserve scaffold
	 - deterministic replace ranges
	 - artifact hóa từng stage
	 - QA độc lập pass ổn định trên nhiều case

### Integration roadmap thực dụng

Pha 1:

- Không đổi builder.
- Viết note/cấu hình mẫu cho `.vscode/mcp.json` để bật `docx-mcp` ở mode sandbox hoặc readonly trước.
- Dùng SuperDoc để mở `report.docx` và smoke outputs trực tiếp trong VS Code.

Pha 2:

- Thêm script hoặc wrapper `post_review_docx.py` gọi MCP review tool để:
	- audit cấu trúc
	- thêm comments cho các điểm QA fail/marginal
	- xuất change summary text

Pha 3:

- Chỉ nếu thật sự cần tracked changes tự động trên output cuối, cho agent dùng MCP để sinh bản `*_reviewed.docx` riêng thay vì sửa đè `report.docx`.

## Kết luận chốt

- Nếu mục tiêu là `xem và sửa DOCX trong VS Code`, SuperDoc là lựa chọn tốt nhất.
- Nếu mục tiêu là `cho agent redline/comment/audit DOCX thật`, `securityronin/docx-mcp` là hướng đáng thử nhất.
- Nếu mục tiêu là `thay thế pipeline builder hiện tại`, chưa có công cụ nào ở trên chứng minh được là phù hợp hơn đường `OfficeCLI + semantic grounding + deterministic plan/build + roundtrip/QA` đang có.
- Hướng đúng là `bổ sung một review layer`, không phải `đập bỏ generation path`.
