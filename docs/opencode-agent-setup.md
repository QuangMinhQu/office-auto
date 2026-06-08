# OpenCode Agent Workspace Setup

## Mục tiêu

Tài liệu này chốt các cấu hình đã thêm để OpenCode và Copilot Agent dùng workspace này ổn định hơn, ít phải nhớ lệnh tay hơn, và tận dụng được native OfficeCLI tool path.

## Những gì đã được bật

### Global environment

- `officecli` đã được xác nhận chạy ổn trên máy hiện tại.
- OfficeCLI base skills cho OpenCode đã được cài:
  - `word`
  - `excel`
  - `pptx`
- OfficeCLI MCP đã được đăng ký cho VS Code.
- MCP server local `office-auto` đã được thêm cho workspace để expose trực tiếp workflow DOCX chuẩn.

### Shared workspace config

- [.vscode/mcp.json](../.vscode/mcp.json): share OfficeCLI MCP server và `office-auto` local MCP server theo kiểu workspace-local config, để repo tự mang theo tool registration cần thiết.
- [.vscode/settings.json](../.vscode/settings.json): bật `chat.mcp.autoStart` và cấu hình `unittest` đúng theo repo này.
- [.vscode/tasks.json](../.vscode/tasks.json): task sẵn cho build DOCX chuẩn, in latest review summary, và chạy unit tests.
- [.vscode/extensions.json](../.vscode/extensions.json): gợi ý extension Python/Pylance và SuperDoc cho screen review DOCX.

## Workflow khuyến nghị

1. Dùng `Office Auto: Build DOCX Report` để chạy wrapper đầy đủ.
2. Dùng `Office Auto: Latest Review Summary` để lấy nhanh đường dẫn tới `review_report.json`, `review_report.md`, `review_screen.html` của run mới nhất.
3. Nếu cần check nhanh repo health, dùng `Office Auto: Run Unit Tests`.
4. Nếu cần debug MCP flow trực tiếp, mở server `office-auto` qua MCP Inspector.

## Lý do cấu hình này phù hợp

- Repo này đã có pipeline deterministic mạnh; điều thiếu là agent-access path và workspace automation.
- OfficeCLI MCP vẫn là execution path native phù hợp nhất cho phần thực thi Office, còn `office-auto` MCP server giúp agent gọi trọn DOCX pipeline ngay trong workspace.
- Review layer mới đã có artifact riêng, nên task `Latest Review Summary` giúp agent/human vào đúng output thay vì dò tay trong `.office-auto/state`.

## Điều chưa cấu hình trực tiếp

- Chưa thêm `securityronin/docx-mcp` vào workspace MCP vì máy hiện tại chưa có `uvx`, còn package runner sẵn có là `npx`; tránh commit một config DOCX MCP bị gãy ngay khi mở workspace.
- Nếu sau này cài `uvx`, có thể thêm một server review/redline riêng bên cạnh `officecli` và `office-auto` thay vì thay thế chúng.
- Không giữ repo-local PPTX wrapper nữa vì workflow chuẩn hiện tại chỉ chốt đường DOCX; khi cần PPTX thì dùng `officecli-pptx` như skill tham chiếu, không dùng pipeline cũ mồ côi.

## Helper script

- [scripts/latest_review_artifacts.py](../scripts/latest_review_artifacts.py): in summary của run mới nhất hoặc run cụ thể, gồm status và đường dẫn review artifacts.
