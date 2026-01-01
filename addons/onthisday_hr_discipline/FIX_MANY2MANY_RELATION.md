# แก้ปัญหา "Cannot read properties of undefined (reading 'relation')"

## ปัญหา
Error: `TypeError: Cannot read properties of undefined (reading 'relation')`

เมื่อเข้าหน้า Employee หรือหน้าอื่น ๆ

## สาเหตุ
Field `license_report_user_ids` ใน `res.config.settings` เป็น Many2many related field แต่ metadata ใน database ไม่ครบ:
- มี `relation` แต่ไม่มี `column1` และ `column2`

Odoo client-side JavaScript ต้องการ relation metadata ที่ครบถ้วนเพื่อ render field

## การแก้ไข

### 1. อัพเดท Database Metadata
```sql
UPDATE ir_model_fields 
SET relation = 'res_company_license_report_user_rel', 
    column1 = 'company_id', 
    column2 = 'user_id' 
WHERE model = 'res.config.settings' 
  AND name = 'license_report_user_ids';
```

### 2. Restart Odoo Server
**สำคัญมาก**: ต้อง restart Odoo server เพื่อให้ metadata ใหม่ถูกโหลด

### 3. Hard Reload Browser
- Ctrl+Shift+R (Windows/Linux) หรือ Cmd+Shift+R (Mac)
- หรือเปิด Incognito/Private window

## หมายเหตุ
สำหรับ Many2many related field ใน TransientModel:
- Odoo ORM จะใช้ metadata จาก base field อัตโนมัติ
- แต่ client-side JavaScript ยังต้องการ relation metadata ที่ครบถ้วน
- ดังนั้นต้องอัพเดท database metadata เอง

## ตรวจสอบว่าแก้ไขแล้ว
```sql
SELECT id, name, relation, column1, column2 
FROM ir_model_fields 
WHERE model = 'res.config.settings' 
  AND name = 'license_report_user_ids';
```

ควรได้:
- relation: `res_company_license_report_user_rel`
- column1: `company_id`
- column2: `user_id`

