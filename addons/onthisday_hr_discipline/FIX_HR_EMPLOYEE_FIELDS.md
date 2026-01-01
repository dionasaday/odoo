# แก้ปัญหา Many2many fields ใน hr.employee

## ปัญหา
Error: `Cannot read properties of undefined (reading 'relation')` เมื่อเข้าหน้า Employee

## สาเหตุ
Fields ใน `hr.employee` ที่เป็น Many2many ยังไม่มี relation metadata ที่ครบถ้วน:
- `kpi_missing_subordinate_ids`
- `message_partner_ids`  
- `related_contact_ids`

## การแก้ไข

### อัพเดท Database Metadata
```sql
-- แก้ไข hr.employee.kpi_missing_subordinate_ids
UPDATE ir_model_fields 
SET relation_table = 'hr_employee_kpi_missing_subordinate_rel',
    column1 = 'employee_id',
    column2 = 'kpi_missing_subordinate_id'
WHERE model = 'hr.employee' 
  AND name = 'kpi_missing_subordinate_ids';

-- แก้ไข hr.employee.message_partner_ids (มาจาก mail.thread)
UPDATE ir_model_fields 
SET relation_table = 'mail_followers',
    column1 = 'res_id',
    column2 = 'partner_id'
WHERE model = 'hr.employee' 
  AND name = 'message_partner_ids';

-- แก้ไข hr.employee.related_contact_ids
UPDATE ir_model_fields 
SET relation_table = 'hr_employee_related_contact_rel',
    column1 = 'employee_id',
    column2 = 'partner_id'
WHERE model = 'hr.employee' 
  AND name = 'related_contact_ids';
```

## ขั้นตอนต่อไป

1. **Restart Odoo Server** (จำเป็น)
2. **Hard Reload Browser** (Ctrl+Shift+R หรือ Cmd+Shift+R)

## หมายเหตุ

Fields เหล่านี้ส่วนใหญ่มาจาก:
- `kpi_missing_subordinate_ids`: จากโมดูล HR KPI ที่อาจถูก disable
- `message_partner_ids`: จาก `mail.thread` mixin (core Odoo)
- `related_contact_ids`: จากโมดูลที่ extend hr.employee

Odoo client-side JavaScript ต้องการ relation metadata ที่ครบถ้วนเพื่อ render fields อย่างถูกต้อง

