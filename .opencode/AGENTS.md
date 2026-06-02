# Office Auto Bootstrap

## Muc tieu file nay
File nay chi la bootstrap pointer cho orchestration.
Khong duoc coi day la session state va khong duoc su dung artifact cu lam context mac dinh.

## Bat dau moi session
1. Doc `.opencode/memory/project.md` de nap conventions cua repo.
2. Chi doc `.opencode/memory/task_current.md` khi can resume session dang do hoac khi nguoi dung noi ro run hien tai.
3. Neu day la task moi, khoi tao hoac viet lai `task_current.md` theo input thuc te cua session hien tai truoc khi goi pipeline.
4. Chi doc `task.md` khi nguoi dung dang muon di theo workflow build DOCX chuan cua repo.
5. Khong doc `manual-run/`, `.manual-run/`, hoac artifact trong `.office-auto/state/<run_id>/` neu chua xac dinh dung run_id can dung.

## Orchestration contract
- Agent chinh: `orchestrator`.
- Subagents hidden: `docx-profiler`, `docx-builder`, `docx-qa`.
- Khong goi truc tiep OfficeCLI MCP tools; chi duoc dung OfficeCLI qua bash CLI hoac custom tools wrappers.
- Mot session chi duoc chon mot execution surface nhat quan:
	- `docx_pipeline_runFullPipeline` cho full flow end-to-end.
	- `docx_pipeline_profileTemplate`, `docx_pipeline_buildDocx`, `docx_pipeline_qaDocx` cho phase rerun/resume.
- Khong tron phase tool custom voi script bash ad-hoc trong cung mot phase, tru khi dang lam diagnostics co chu dich va co ghi ro ly do.

## Hard gate
- Khong chot complete neu chua co `qa_report.json` status passed.
- Neu phase fail, orchestrator phai redispatch dung subagent pha do.
- Luon uu tien mode `preserve-template-scaffold` cho DOCX report generation.
- Orchestrator khong tu lam phase work khi da co subagent owner cua phase do; vai tro chinh la route, doc artifact, cap nhat session state, va retry co dinh huong.