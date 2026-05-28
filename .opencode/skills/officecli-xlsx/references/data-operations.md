# OfficeCLI XLSX: Data Operations

Dung file nay khi can nap, xuat hoac bien doi du lieu dang bang.

## Import va export

```bash
officecli import "$FILE" /Sheet1 data.csv
officecli import "$FILE" /Sheet1 data.tsv
officecli export "$FILE" /Sheet1 output.csv
```

- Sau import, doc lai pham vi canh tren bang `get` hoac `query 'cell[value!=""]'` de chac header da vao dung vi tri.

## Data validation

```bash
officecli add "$FILE" /Sheet1 --type dataValidation --prop range='C2:C100' --prop rule='list:Open,In Progress,Done'
officecli add "$FILE" /Sheet1 --type dataValidation --prop range='D2:D100' --prop rule='wholeNumber:1:10'
officecli add "$FILE" /Sheet1 --type dataValidation --prop range='E2:E100' --prop rule='custom:=E2>=TODAY()'
```

## Sort va filter

```bash
officecli set "$FILE" /Sheet1/table[1] --prop sort='Revenue:desc'
officecli set "$FILE" /Sheet1/table[1] --prop filter='Owner=Minh'
officecli set "$FILE" /Sheet1 --prop autoFilter='A1:F50'
```

- Sort/filter nen chay tren table hoac range da xac dinh ro, tranh lay nham row tieu de.

## Find va replace

```bash
officecli query "$FILE" 'cell:contains("draft")'
officecli set "$FILE" 'Sheet1!A2:A100' --prop replace='draft=>final'
```

- Khi replace tren range lon, query truoc va kiem tra mau sau thay doi de tranh sua nham formula.