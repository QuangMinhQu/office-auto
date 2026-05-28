# OfficeCLI DOCX: L3 Raw XML Guardrail

Dùng file này chỉ khi L1/L2 không đủ.

## Lệnh L3

```bash
officecli raw "$FILE" /document
officecli raw "$FILE" /settings
officecli raw-set "$FILE" /settings --xpath '//*[local-name()="updateFields"]' --action replace --xml '<w:updateFields xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:val="true" />'
officecli add-part "$FILE" /document
```

## Khi nào được phép dùng
- Cần inspect XML edge-case mà `view/get/query` không expose.
- Cần mutate một feature OfficeCLI chưa có prop L2 tương ứng.
- Cần inject custom XML part hoặc relationship đặc thù.

## Khi nào không được dùng
- Chỉ vì đã quen sửa XML trực tiếp.
- Khi `toc`, `field`, `section`, `header/footer`, `paragraph`, `run` đã đủ để làm việc.

## Ghi log bắt buộc
Nếu dùng L3, phải ghi vào `build_report.json` tối thiểu:

```json
{
  "l3_fallback": {
    "reason": "L2 không expose prop cần thiết",
    "command": "raw-set",
    "target_part": "/settings"
  }
}
```