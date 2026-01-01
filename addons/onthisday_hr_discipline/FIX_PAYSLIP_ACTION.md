# แก้ปัญหา Action ที่อ้างอิง hr.payslip

## ปัญหา
Error: `KeyError: 'hr.payslip'` เมื่อเข้าหน้า Payroll

## สาเหตุ
`ir.actions.act_window` record ID 991 มี `search_view_id` ที่อ้างอิง model `hr.payslip`
แต่ `hr.payslip` ไม่มีใน Odoo registry เพราะ `hr_payroll_community` module ถูก disable

## การแก้ไข

### อัพเดท Action Record
```sql
UPDATE ir_actions_act_window 
SET search_view_id = NULL 
WHERE id = 991;
```

หรือลบ action ทั้งหมด (ถ้าไม่จำเป็น):
```sql
DELETE FROM ir_actions_act_window WHERE id = 991;
```

## ตรวจสอบ Actions อื่นที่อาจมีปัญหา

```sql
-- หา actions ที่อ้างอิง hr.payslip
SELECT id, name, res_model, search_view_id 
FROM ir_actions_act_window 
WHERE res_model = 'hr.payslip' 
   OR search_view_id IN (
       SELECT id FROM ir_ui_view WHERE model = 'hr.payslip'
   );
```

## ขั้นตอนต่อไป

1. **Restart Odoo Server** (ถ้ายังไม่ได้ restart)
2. **Hard Reload Browser** (Ctrl+Shift+R หรือ Cmd+Shift+R)

## หมายเหตุ

ถ้ามี actions อื่นที่อ้างอิง `hr.payslip` อาจต้องแก้ไขหรือลบออกเช่นกัน
เพื่อป้องกัน error ในอนาคต

