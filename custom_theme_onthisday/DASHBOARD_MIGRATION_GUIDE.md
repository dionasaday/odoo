# 📊 คู่มือ Export/Import Dashboard Configuration

## 🎯 วัตถุประสงค์

Export Dashboard configuration จาก **localhost** (ที่ทำงานปกติ) ไปยัง **production** (ที่ยังไม่มี configuration)

---

## 📋 ขั้นตอนการ Export/Import

### วิธีที่ 1: ใช้ Python Scripts (แนะนำ)

#### Step 1: Export จาก Localhost

```bash
# Export Dashboard "Sales" จาก localhost
cd /opt/odoo/custom_addons
python3 export_dashboard.py odoo16 Sales dashboard_sales_config.json
```

**Output:**
```
✅ Dashboard exported successfully!
   Dashboard: Sales
   ID: 2
   Data Length: 12345 bytes
   Output File: dashboard_sales_config.json
```

#### Step 2: Copy ไฟล์ไปยัง Production Server

```bash
# Copy ไฟล์ไปยัง production server
scp dashboard_sales_config.json user@production-server:/opt/odoo/custom_addons/
```

#### Step 3: Import ไปยัง Production

```bash
# Import Dashboard "Sales" ไปยัง production
cd /opt/odoo/custom_addons
python3 import_dashboard.py odoo16_production Sales dashboard_sales_config.json
```

**Output:**
```
✅ Dashboard 'Sales' updated!
   ID: 2
✅ Dashboard configuration imported successfully!
   Dashboard: Sales
   Data Length: 12345 bytes

⚠️  Next steps:
   1. Restart Odoo: sudo systemctl restart odoo
   2. Clear browser cache (Ctrl+Shift+R)
   3. Open Dashboard in Odoo
```

---

### วิธีที่ 2: ใช้ SQL Query โดยตรง

#### Step 1: Export จาก Localhost

```bash
# Export spreadsheet_data จาก localhost
sudo -u odoo psql -d odoo16 -c "
COPY (
    SELECT 
        id,
        name,
        spreadsheet_data::text
    FROM spreadsheet_dashboard
    WHERE name = 'Sales'
) TO STDOUT;
" > dashboard_sales_config.txt
```

#### Step 2: Import ไปยัง Production

```bash
# Import spreadsheet_data ไปยัง production
# 1. อ่านข้อมูลจากไฟล์
DASHBOARD_DATA=$(cat dashboard_sales_config.txt)

# 2. Update database
sudo -u odoo psql -d odoo16_production -c "
UPDATE spreadsheet_dashboard
SET spreadsheet_data = '$DASHBOARD_DATA'::jsonb
WHERE name = 'Sales';
"
```

---

### วิธีที่ 3: ใช้ Odoo Shell

#### Step 1: Export จาก Localhost

```bash
# เข้าสู่ Odoo shell
odoo-bin shell -d odoo16

# ใน Python shell
>>> dashboard = env['spreadsheet.dashboard'].search([('name', '=', 'Sales')])
>>> data = dashboard.spreadsheet_data
>>> import json
>>> with open('/tmp/dashboard_sales.json', 'w') as f:
...     json.dump(data, f, indent=2)
>>> print(f"Exported: {len(str(data))} bytes")
```

#### Step 2: Import ไปยัง Production

```bash
# เข้าสู่ Odoo shell
odoo-bin shell -d odoo16_production

# ใน Python shell
>>> import json
>>> with open('/tmp/dashboard_sales.json', 'r') as f:
...     data = json.load(f)
>>> dashboard = env['spreadsheet.dashboard'].search([('name', '=', 'Sales')])
>>> dashboard.spreadsheet_data = data
>>> dashboard.save()
>>> print("Dashboard updated!")
```

---

## 🔍 ตรวจสอบ Dashboard Configuration

### ตรวจสอบว่า Dashboard มีข้อมูลหรือไม่

```bash
# ตรวจสอบ Dashboard ใน database
sudo -u odoo psql -d odoo16 -c "
SELECT 
    id,
    name,
    CASE 
        WHEN spreadsheet_data IS NULL THEN 'NULL'
        WHEN spreadsheet_data::text = '' THEN 'EMPTY'
        ELSE 'HAS_DATA'
    END as status,
    LENGTH(spreadsheet_data::text) as data_length
FROM spreadsheet_dashboard
ORDER BY name;
"
```

**Output:**
```
 id |   name    |  status  | data_length
----+-----------+----------+------------
  2 | Sales     | HAS_DATA |      12345
  3 | Product   | EMPTY    |          0
  1 | Invoicing | EMPTY    |          0
```

---

## ⚠️ ข้อควรระวัง

### 1. Backup Database ก่อน Import

```bash
# Backup production database ก่อน import
sudo -u odoo pg_dump odoo16_production > backup_$(date +%Y%m%d_%H%M%S).sql
```

### 2. ตรวจสอบ Dashboard ID

- Dashboard ID อาจไม่ตรงกันระหว่าง localhost และ production
- ใช้ `name` แทน `id` ในการค้นหา

### 3. ตรวจสอบ Dependencies

- ตรวจสอบว่า Dashboard ใช้ Odoo formulas ที่มีใน production หรือไม่
- ตรวจสอบว่า models ที่ Dashboard ใช้มีใน production หรือไม่

---

## 🚀 หลังจาก Import

### 1. Restart Odoo

```bash
sudo systemctl restart odoo
```

### 2. Clear Browser Cache

- กด `Ctrl+Shift+R` (Windows/Linux)
- หรือ `Cmd+Shift+R` (Mac)

### 3. ตรวจสอบ Dashboard

- เปิด Dashboard ใน Odoo
- ตรวจสอบว่าข้อมูลแสดงผลถูกต้อง
- ตรวจสอบว่า Charts/Graphs ทำงานได้

---

## 📝 ตัวอย่างการใช้งาน

### Export ทั้งหมด Dashboards

```bash
# Export ทุก Dashboard
for dashboard in Sales Product Invoicing; do
    python3 export_dashboard.py odoo16 "$dashboard" "dashboard_${dashboard,,}_config.json"
done
```

### Import ทั้งหมด Dashboards

```bash
# Import ทุก Dashboard
for dashboard in Sales Product Invoicing; do
    python3 import_dashboard.py odoo16_production "$dashboard" "dashboard_${dashboard,,}_config.json"
done
```

---

## 🔧 Troubleshooting

### ปัญหา: Dashboard ยังไม่แสดงผลหลัง Import

**วิธีแก้:**
1. ตรวจสอบว่า `spreadsheet_data` ถูก update หรือไม่:
   ```sql
   SELECT LENGTH(spreadsheet_data::text) FROM spreadsheet_dashboard WHERE name = 'Sales';
   ```

2. Restart Odoo:
   ```bash
   sudo systemctl restart odoo
   ```

3. Clear browser cache และ hard refresh

### ปัญหา: Import แล้วเกิด Error

**วิธีแก้:**
1. ตรวจสอบว่า Dashboard มีอยู่ใน production หรือไม่
2. ตรวจสอบว่า JSON format ถูกต้องหรือไม่
3. ตรวจสอบ logs:
   ```bash
   tail -f /var/log/odoo/odoo-server.log | grep -i dashboard
   ```

---

## ✅ Checklist

- [ ] Export Dashboard จาก localhost
- [ ] Backup production database
- [ ] Copy ไฟล์ config ไปยัง production
- [ ] Import Dashboard ไปยัง production
- [ ] Restart Odoo
- [ ] Clear browser cache
- [ ] ตรวจสอบ Dashboard ใน production
- [ ] ตรวจสอบว่า Charts/Graphs ทำงานได้

---

## 📚 ไฟล์ที่เกี่ยวข้อง

- `export_dashboard.py` - Script สำหรับ export
- `import_dashboard.py` - Script สำหรับ import
- `export_dashboard_config.sh` - Shell script สำหรับ export
- `DASHBOARD_ISSUE_SUMMARY.md` - สรุปปัญหา Dashboard

---

**หมายเหตุ**: Dashboard configuration ที่ export มาจะมี Odoo formulas ที่ดึงข้อมูลจาก database จริง ดังนั้น Dashboard จะแสดงข้อมูลตาม database ที่ import ไป

