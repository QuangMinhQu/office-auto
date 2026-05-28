# OfficeCLI XLSX: Advanced Features

Dung file nay khi task dong den tinh nang workbook nang cao.

## Freeze panes

```bash
officecli set "$FILE" /Sheet1 --prop freezePanes='B2'
```

## Protection

```bash
officecli set "$FILE" /Sheet1 --prop protection.enabled=true
officecli set "$FILE" /Sheet1 --prop protection.password='***'
officecli set "$FILE" / --prop workbookProtection.structure=true
```

- Neu workflow dung secret that su, khong dua gia tri nhay cam vao prompt log.

## Comments va hyperlinks

```bash
officecli add "$FILE" 'Sheet1!B2' --type comment --prop text='Review this variance'
officecli set "$FILE" 'Sheet1!A2' --prop hyperlink='https://example.com'
officecli set "$FILE" 'Sheet1!A3' --prop hyperlink='#Sheet2!A1'
```

## Sparklines

```bash
officecli add "$FILE" /Sheet1 --type sparkline --prop source='B2:G2' --prop destination='H2'
```

## Page setup

```bash
officecli set "$FILE" /Sheet1 --prop printArea='A1:H40'
officecli set "$FILE" /Sheet1 --prop pageSetup.orientation=landscape
officecli set "$FILE" /Sheet1 --prop pageSetup.margins='0.5,0.5,0.75,0.75'
officecli set "$FILE" /Sheet1 --prop headerFooter.oddFooter='Week 1 Report'
```

- Voi file report in an, kiem tra print area va header/footer truoc khi finalize.