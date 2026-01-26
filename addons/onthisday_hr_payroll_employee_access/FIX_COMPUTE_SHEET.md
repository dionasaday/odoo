# แก้ปัญหา HR Manager ไม่สามารถกด Compute Sheet ได้

## ปัญหา
HR Manager ไม่สามารถกด "Compute Sheet" ได้เพราะมี Access Error จาก security rule "Employee: Own Payslip Lines Only"

## วิธีแก้ไข (เลือกวิธีใดวิธีหนึ่ง)

### วิธีที่ 1: Upgrade Module (แนะนำ)
1. ไปที่ **Apps**
2. ค้นหา "**OnThisDay HR Payroll Employee Access**"
3. คลิก **Upgrade**
4. Refresh หน้าเว็บ (F5)
5. ทดสอบกด "Compute Sheet" อีกครั้ง

### วิธีที่ 2: รัน SQL Script (เร็วที่สุด)
รัน SQL นี้ผ่าน Odoo shell หรือ SQL client:

```sql
DELETE FROM ir_rule 
WHERE name IN (
    'Employee: Own Payslip Lines Only',
    'Employee: Own Payslip Worked Days Only',
    'Employee: Own Payslip Inputs Only'
);
```

**วิธีรัน SQL:**
- ผ่าน Odoo shell: `odoo-bin shell -d <database_name>` แล้วรัน SQL
- ผ่าน SQL client (pgAdmin, DBeaver, etc.): เชื่อมต่อ database แล้วรัน SQL

### วิธีที่ 3: รัน Python Script
```bash
odoo-bin shell -d <database_name>
```
แล้วรัน:
```python
env = api.Environment(cr, SUPERUSER_ID, {})
IrRule = env['ir.rule']
rules = IrRule.search([('name', 'in', [
    'Employee: Own Payslip Lines Only',
    'Employee: Own Payslip Worked Days Only',
    'Employee: Own Payslip Inputs Only'
])])
if rules:
    rules.unlink()
    cr.commit()
    print("✅ Rules deleted!")
```

## สาเหตุ
Security rule "Employee: Own Payslip Lines Only" ถูกสร้างไว้สำหรับพนักงานทั่วไป แต่ rule นี้บล็อกการสร้าง payslip lines สำหรับ HR Manager ด้วย

## การแก้ไขในโค้ด
โค้ดได้ถูกแก้ไขให้ลบ security rules เหล่านี้ออกอัตโนมัติเมื่อ upgrade module เพื่อให้:
- พนักงานทั่วไป: ดูสลิปของตัวเองได้ (read only) ผ่าน security rule ของ `hr.payslip`
- HR Manager/Payroll Officer: สร้างและแก้ไข payslip lines ได้ตามปกติ
