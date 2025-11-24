# 📊 คำอธิบาย: Import Dashboard Configuration

## ❓ คำถาม: Import Dashboard Configuration ของ "My Company (Chicago)" มาทับที่ "บริษัท ออน ดีส เดย์ จำกัด" จะหายไหม?

### คำตอบ: **ข้อมูล Company จะไม่หาย** แต่ Dashboard Configuration จะถูกทับ ✅

---

## 🔍 Dashboard Configuration คืออะไร?

### 1. Dashboard Configuration (`spreadsheet_data`)

- **เป็น GLOBAL Configuration** - ไม่ได้ขึ้นกับ company โดยตรง
- **ใช้ร่วมกันทุก company** - Dashboard configuration เดียวกันใช้กับทุก company
- **เก็บใน `spreadsheet_dashboard` table** - ไม่มี `company_id` field

### 2. Company Data

- **แยกจาก Dashboard Configuration** - Sales orders, invoices, etc. แยกตาม company
- **ไม่หายไป** - การ import Dashboard configuration จะไม่กระทบข้อมูล company

---

## ⚠️ ผลกระทบของการ Import

### ✅ สิ่งที่ **ไม่หายไป**

1. **ข้อมูล Company**
   - Sales orders
   - Invoices
   - Customers
   - Products
   - และข้อมูลอื่นๆ ทั้งหมด

2. **Company Settings**
   - Company name
   - Company address
   - Company settings
   - Theme colors

### ⚠️ สิ่งที่ **จะถูกทับ**

1. **Dashboard Configuration**
   - `spreadsheet_data` จะถูก replace ด้วย configuration ใหม่
   - Dashboard structure, charts, formulas จะถูกเปลี่ยน

2. **Dashboard Content**
   - Charts, graphs, tables จะถูกเปลี่ยน
   - Formulas จะถูกเปลี่ยน

---

## 🔍 วิธีทำงานของ Dashboard

### 1. Dashboard Configuration (Global)

```python
# Dashboard configuration เก็บใน spreadsheet_dashboard table
# ไม่มี company_id field
spreadsheet_dashboard = {
    'id': 2,
    'name': 'Sales',
    'spreadsheet_data': {...}  # Global configuration
}
```

### 2. Company Context (Runtime)

```python
# เมื่อ Dashboard ถูกโหลด
# Odoo จะใช้ company context ปัจจุบัน
current_company = self.env.company

# Odoo formulas จะดึงข้อมูลตาม company context
=ODOO.LIST(sale.order, COUNT)  # จะดึงข้อมูลตาม company ปัจจุบัน
```

### 3. Patch ของเรา

```python
# Patch ดึงข้อมูล sales orders ตาม company context
sales_orders = self.env['sale.order'].search([
    ('company_id', '=', current_company.id)
])
```

---

## 📋 สรุป

### ✅ ข้อมูล Company จะไม่หาย

| ข้อมูล | หายไป? | เหตุผล |
|--------|--------|--------|
| Sales Orders | ❌ ไม่หาย | แยกจาก Dashboard configuration |
| Invoices | ❌ ไม่หาย | แยกจาก Dashboard configuration |
| Customers | ❌ ไม่หาย | แยกจาก Dashboard configuration |
| Company Settings | ❌ ไม่หาย | แยกจาก Dashboard configuration |
| Dashboard Configuration | ✅ ถูกทับ | จะถูก replace ด้วย configuration ใหม่ |

### ⚠️ Dashboard Configuration จะถูกทับ

- **Dashboard structure** จะถูกเปลี่ยน
- **Charts, graphs, tables** จะถูกเปลี่ยน
- **Formulas** จะถูกเปลี่ยน
- แต่ **Odoo formulas จะดึงข้อมูลตาม company context** ปัจจุบัน

---

## ✅ วิธี Import ที่ถูกต้อง

### Step 1: Export Dashboard จาก Localhost

```bash
cd /opt/odoo/custom_addons

# Export Dashboard "Sales" จาก localhost
python3 export_dashboard.py odoo16 Sales dashboard_sales_config.json
```

### Step 2: Import ไปยัง Production

```bash
# Import Dashboard "Sales" ไปยัง production
python3 import_dashboard.py odoo16_production Sales dashboard_sales_config.json
```

### Step 3: ผลลัพธ์

- ✅ Dashboard configuration จะถูก update
- ✅ Dashboard จะแสดงผลในทุก company
- ✅ Dashboard จะดึงข้อมูลตาม company context ปัจจุบัน
- ✅ ข้อมูล company จะไม่หาย

---

## 🔍 ตัวอย่างการทำงาน

### ก่อน Import

```
Dashboard "Sales":
- Configuration: Empty หรือ configuration เก่า
- เมื่อเปิดใน "My Company (Chicago)": แสดงข้อมูลของ Chicago
- เมื่อเปิดใน "บริษัท ออน ดีส เดย์ จำกัด": แสดงข้อมูลของ ออน ดีส เดย์
```

### หลัง Import

```
Dashboard "Sales":
- Configuration: Configuration ใหม่จาก localhost
- เมื่อเปิดใน "My Company (Chicago)": แสดงข้อมูลของ Chicago (ใช้ configuration ใหม่)
- เมื่อเปิดใน "บริษัท ออน ดีส เดย์ จำกัด": แสดงข้อมูลของ ออน ดีส เดย์ (ใช้ configuration ใหม่)
```

**สรุป**: Dashboard configuration เดียวกัน แต่แสดงข้อมูลตาม company ที่เลือก

---

## ⚠️ ข้อควรระวัง

### 1. Dashboard Configuration จะถูกทับ

- Configuration เดิมจะหายไป
- ควร backup configuration เดิมก่อน (ถ้ามี)

### 2. Odoo Formulas

- Odoo formulas จะดึงข้อมูลตาม company context
- ถ้า formulas hardcode company → อาจแสดงข้อมูลผิด company
- ควรใช้ formulas ที่ใช้ company context

### 3. Multi-Company

- Dashboard configuration เป็น global
- แต่ข้อมูลที่แสดงจะตาม company context
- ตรวจสอบว่า formulas ใช้ company context ถูกต้อง

---

## 📋 Checklist

- [ ] Backup Dashboard configuration เดิม (ถ้ามี)
- [ ] Export Dashboard configuration จาก localhost
- [ ] Import ไปยัง production
- [ ] Restart Odoo
- [ ] Clear browser cache
- [ ] ทดสอบ Dashboard ใน "My Company (Chicago)"
- [ ] ทดสอบ Dashboard ใน "บริษัท ออน ดีส เดย์ จำกัด"
- [ ] ตรวจสอบว่าข้อมูลแสดงผลถูกต้องตาม company

---

## ✅ สรุป

### คำตอบ: ข้อมูล Company จะไม่หาย ✅

**สิ่งที่เกิดขึ้น:**
- ✅ ข้อมูล company (sales orders, invoices, etc.) **ไม่หาย**
- ⚠️ Dashboard configuration **จะถูกทับ** ด้วย configuration ใหม่
- ✅ Dashboard จะแสดงผลในทุก company
- ✅ Dashboard จะดึงข้อมูลตาม company context ปัจจุบัน

**ข้อควรระวัง:**
- Dashboard configuration เดิมจะหายไป (ควร backup ก่อน)
- ตรวจสอบว่า Dashboard แสดงข้อมูลถูกต้องตาม company

---

## 📚 เอกสารที่เกี่ยวข้อง

- `DASHBOARD_MIGRATION_GUIDE.md` - คู่มือ Export/Import Dashboard
- `DASHBOARD_TROUBLESHOOTING.md` - แก้ไขปัญหา Dashboard
- `MULTI_COMPANY_DASHBOARD_FIX.md` - แก้ไขปัญหา Multi-Company

