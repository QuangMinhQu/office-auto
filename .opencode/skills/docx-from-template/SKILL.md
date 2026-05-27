---
name: docx-from-template
description: Tạo hoặc append nội dung vào file Word (.docx) dựa trên template theo workflow ngắn, có checkpoint, phù hợp cho OpenCode/Qwen. Dùng khi cần tạo report.docx từ template, chèn thêm chương mới, giữ nguyên nội dung cũ, giữ numbering heading, và không overwrite body hiện có.
license: MIT
---
# SKILL: DOCX_FROM_TEMPLATE

## Mục tiêu
Skill này là orchestrator ngắn cho tác vụ tạo hoặc append `.docx` từ template.

Skill này KHONG day syntax chi tiet cua `officecli`.
Khi can command, schema element, hoac prop name, load `officecli-docx`.
Khi can kiem tra TOC, references, appendix, cross-reference, header/footer, load `docx-qa` truoc khi ban giao file.

## Khi nao dung skill nay
- Tao file Word moi tu template.
- Append chuong/muc moi vao file da ton tai.
- Giu nguyen noi dung dang co trong template/file dich.
- Tai tao numbering heading `1`, `1.1`, `1.1.1`.
- Tao `report.docx` tu `format_template.docx` va chen noi dung tu `.md`.

## Inputs bat buoc
- `template_file`
- `content`
- `mode`: `create` | `append`

## Inputs bo sung
- `output_file`: bat buoc khi `mode=create`
- `target_file`: bat buoc khi `mode=append`
- `insert_after`: heading/section neo chen sau

## Invariants
- Khong bo qua thu tu phase.
- Khong doan prop name; tra cuu trong `officecli-docx`.
- `style` va `numbering` la 2 lop rieng; heading co so thu tu phai co `numId` + `ilvl` neu template dung numbered headings.
- Neu them noi dung moi, phai ra soat cac phan phu thuoc cau truc tai lieu truoc khi giao file.
- `append` la merge an toan, khong overwrite body cu.

## Invariant rat quan trong cho mode append
Neu `mode=append` va `target_file` CHUA ton tai, khong duoc append vao file rong.
Phai khoi tao `target_file` bang cach sao chep `template_file` sang `target_file` truoc, roi moi append.

Neu bo qua buoc nay, agent rat de:
- mat noi dung chuong truoc do
- append vao sai nen tai lieu
- lam TOC, numbering, header/footer bi lech


## Routing toi thieu
- Luon load `officecli-docx`.
- Load `docx-qa` trong 2 truong hop:
  - truoc khi giao file
  - hoac ngay khi task co TOC, references, appendix, danh muc hinh/bang, cross-reference

## State Machine

### PHASE 0: Preflight
Muc tieu: xac nhan moi truong chay va mode thuc thi.

Lam:
- Xac nhan file dau vao ton tai.
- Neu dang chay tren Linux/WSL va `officecli` moi duoc cai, nap lai shell hien tai truoc khi chay: `source ~/.bashrc && officecli --version`.
- Chi neu dang chay Windows native va `officecli` moi duoc cai, moi prepend PATH tam trong session hien tai truoc khi chay.
- Xac nhan `mode` hop le.
- Neu `mode=append`, xac nhan `target_file` va `insert_after`.
- Neu `mode=append` ma `target_file` chua ton tai, sao chep `template_file` thanh `target_file`.

Checkpoint schema:
```json
{
  "phase": 0,
  "completed": true,
  "mode": "append",
  "working_file": "report.docx",
  "officecli_ready": true,
  "issues": []
}
```

### PHASE 1: Analyze
Muc tieu: lay minimum context can thiet, khong map ca the gioi.

Phai lay:
- outline cua template/file dich
- style phu hop cho H1/H2/H3/body gan diem chen
- numbering map neu heading dang duoc danh so
- cac section phu thuoc: TOC, `TAI LIEU THAM KHAO`, `PHU LUC`, danh muc hinh/bang, cross-reference

Khong lam:
- khong doc tran lan toan file neu khong can
- khong drill-down moi style neu `view stats` va `/styles --depth 2` da du

Artifact toi thieu:
```json
{
  "phase": 1,
  "completed": true,
  "analysis": {
    "anchor": "CƠ SỞ LÝ THUYẾT",
    "insert_before": "KẾT LUẬN",
    "styles": {
      "h1": "Heading1",
      "h2": "Heading2",
      "h3": "Heading3",
      "body": "Normal"
    },
    "heading_numbering": true,
    "numbering_map": {
      "h1": {"numId": 25, "ilvl": 0},
      "h2": {"numId": 1, "ilvl": 1},
      "h3": {"numId": 1, "ilvl": 2}
    },
    "dependent_sections": ["toc", "references"]
  },
  "issues": []
}
```

### PHASE 2: Execute
Muc tieu: tao hoac append noi dung moi ma khong lam hong noi dung cu.

#### Neu mode=create
- Tao file moi.
- Ap dung document-level properties can thiet.
- Tao body theo analysis map.

#### Neu mode=append
- Lam viec tren `target_file`.
- Khong xoa content cu.
- Chen noi dung moi tai neo da xac dinh.
- Neu co numbered headings, tai su dung numbering co san neu phu hop.
- Neu section moi lam thay doi cau truc tai lieu, danh dau cac phan phu thuoc can update.

Quy tac thuc thi:
- Structural first: numbering/page setup/anchor.
- Content next: heading/body/table.
- QA-sensitive sections last: TOC, references, appendix, lists, cross-reference.
- Batch khi co nhieu element cung khu vuc.

Checkpoint schema:
```json
{
  "phase": 2,
  "completed": true,
  "working_file": "report.docx",
  "content_added": {
    "headings": 3,
    "paragraphs": 12,
    "tables": 0
  },
  "dependent_sections_to_review": ["toc", "references"],
  "issues": []
}
```

### PHASE 3: QA
Muc tieu: xac nhan khong chi body dung, ma cac phan phu thuoc cung dung.

Bat buoc kiem tra:
- outline
- heading numbering (`numId`, `ilvl`)
- placeholder ton du
- validate/issues
- header/footer
- TOC
- references
- appendix
- danh muc hinh/bang
- cross-reference/bookmark lien quan

Neu mot phan phu thuoc chua khop, quay lai PHASE 2 va sua. Khong duoc giao file khi body dung nhung TOC/references chua cap nhat.

Checkpoint schema:
```json
{
  "phase": 3,
  "completed": true,
  "validation_passed": true,
  "checks": {
    "outline": true,
    "numbering": true,
    "toc": true,
    "references": true,
    "appendix": true,
    "cross_references": true,
    "header_footer": true
  },
  "issues": []
}
```

### PHASE 4: Finalize
Muc tieu: dong resident mode, xuat artifact, giao file.

Lam:
- `close` file neu dang resident mode
- visual check bang `view html` neu can
- ghi report generation ngan gon

Output schema:
```json
{
  "phase": 4,
  "completed": true,
  "output_file": "report.docx",
  "final_status": "ready",
  "issues": []
}
```

## Failure Recovery
- Neu `officecli` khong nhan lenh tren Linux/WSL session hien tai: `source ~/.bashrc`, kiem tra `which officecli`, roi thu lai.
- Neu `officecli` khong nhan lenh tren Windows session hien tai: prepend PATH tam va thu lai.
- Neu khong tim thay neo chen: chen truoc section cuoi nhu `KET LUAN` hoac `TAI LIEU THAM KHAO`, khong chen sau phan tham chieu.
- Neu numbering sai: dung lai va phan tich `/numbering`, khong doan `numId`.
- Neu TOC/references/appendix chua cap nhat: quay lai PHASE 2, khong skip sang final.
- Neu `append` vao file chua khoi tao: tao `target_file` tu `template_file` roi lam lai.

## Anti-Patterns
- Append vao file rong trong khi user muon giu noi dung template.
- Chi them body moi ma bo qua TOC/references/appendix.
- Chi set `style=Heading2` ma khong set numbering binding.
- Validate xong roi giao file du TOC van hien `Update field to see table of contents` trong truong hop nguoi nhan khong refresh field.
- Rebuild lai toan bo document khi user chi yeu cau append.

## Delivery Rule
Chi duoc coi la xong khi:
- file dich van con noi dung cu
- noi dung moi da duoc chen dung cho
- numbering dung
- cac phan phu thuoc da duoc ra soat/cap nhat
- validation pass
