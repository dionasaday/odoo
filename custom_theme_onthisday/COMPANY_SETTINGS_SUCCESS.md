# ✅ Theme Colors ย้ายไป Settings > Companies สำเร็จแล้ว!

## สถานะการติดตั้ง

- ✅ **Module State**: `installed`
- ✅ **Database Columns**: สร้างแล้ว
  - `theme_primary_color` (character varying)
  - `theme_secondary_color` (character varying)
  - `theme_text_color` (character varying)
- ✅ **View Created**: `res.company.form.theme.colors` (ID: 261)
- ✅ **View Active**: `true`
- ✅ **Odoo Status**: ทำงานได้ปกติ

## วิธีใช้งาน

1. **เข้าสู่ระบบ Odoo**
   - ไปที่ `http://localhost:8069`
   - Login เข้าระบบ

2. **ไปที่ Settings > Companies**
   - คลิก **Settings** ในเมนูด้านบน
   - เลือก **Users & Companies** > **Companies**
   - หรือไปที่ **Settings** > **Companies** โดยตรง

3. **เลือกบริษัท**
   - คลิกบริษัทที่ต้องการแก้ไข (เช่น "บริษัท ออน ดีส เดย์ จำกัด")
   - หรือคลิก **New** เพื่อสร้างบริษัทใหม่

4. **หา Theme Colors Section**
   - เปิดหน้าแก้ไขบริษัท
   - ในแท็บ **General Information**
   - ควรเห็น section **"Theme Colors"** หลังจาก field **Color**

5. **แก้ไขสี**
   - **Primary Color**: สีหลัก (เช่น #232222)
     - ใช้ใน Navigation Bar, Buttons, และ UI elements
   - **Secondary Color**: สีรอง (เช่น #623412)
     - ใช้ใน hover states และ active elements
   - **Text Color**: สีข้อความ (เช่น #FFFFFF)
     - ใช้บนพื้นหลังสีหลัก

6. **บันทึกและทดสอบ**
   - คลิก **Save**
   - Refresh browser (Ctrl+Shift+R หรือ Cmd+Shift+R)
   - สีจะเปลี่ยนทันที!

## ตำแหน่งที่ตั้งค่า

**Settings > Users & Companies > Companies > [เลือกบริษัท] > General Information > Theme Colors**

หรือ

**Settings > Companies > [เลือกบริษัท] > General Information > Theme Colors**

## ตัวอย่างค่าเริ่มต้น

- **Primary Color**: `#232222` (Dark Gray)
- **Secondary Color**: `#623412` (Brown)
- **Text Color**: `#FFFFFF` (White)

## ถ้ายังไม่เห็น Theme Colors

1. **Clear Browser Cache**:
   - กด `Ctrl+Shift+Delete` (Windows/Linux)
   - หรือ `Cmd+Shift+Delete` (Mac)
   - เลือก "Clear cached images and files"

2. **Hard Refresh**:
   - กด `Ctrl+Shift+R` (Windows/Linux)
   - หรือ `Cmd+Shift+R` (Mac)

3. **ตรวจสอบ Module**:
   - ไปที่ **Apps**
   - ค้นหา "Custom Theme - On This Day"
   - ตรวจสอบว่า state = "Installed"

4. **Restart Odoo** (ถ้าจำเป็น):
   ```bash
   docker-compose restart odoo
   ```

5. **ตรวจสอบ View**:
   ```sql
   SELECT id, name, model, active FROM ir_ui_view 
   WHERE name LIKE '%company%theme%';
   ```

## ตรวจสอบใน Database

```sql
-- ตรวจสอบ Columns
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'res_company' AND column_name LIKE 'theme%';

-- ตรวจสอบ Module
SELECT name, state FROM ir_module_module 
WHERE name = 'custom_theme_onthisday';

-- ตรวจสอบ View
SELECT id, name, model, active FROM ir_ui_view 
WHERE name LIKE '%company%theme%';

-- ตรวจสอบค่าใน Company
SELECT name, theme_primary_color, theme_secondary_color, theme_text_color 
FROM res_company;
```

## ความแตกต่างจากเดิม

**เดิม**: Theme Colors อยู่ใน Settings > General Settings
**ใหม่**: Theme Colors อยู่ใน Settings > Companies > [เลือกบริษัท] > General Information

**ข้อดี**:
- ✅ แต่ละบริษัทสามารถมีสีธีมที่แตกต่างกันได้
- ✅ เหมาะสำหรับ Multi-company environment
- ✅ สีจะเชื่อมโยงกับบริษัทโดยตรง

## สรุป

✅ Theme Colors ย้ายไป Settings > Companies สำเร็จแล้ว!

ตอนนี้ควรเห็น **Theme Colors** section ในหน้า Companies > General Information แล้ว

