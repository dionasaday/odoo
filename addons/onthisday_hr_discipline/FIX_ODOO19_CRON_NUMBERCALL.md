# แก้ไข Cron Jobs สำหรับ Odoo 19

## ปัญหา

เมื่อติดตั้งโมดูลใน Odoo 19 เกิด error:
```
ValueError: Invalid field 'numbercall' in 'ir.cron'
```

## สาเหตุ

ใน Odoo 19 มีการเปลี่ยนแปลง API ของ `ir.cron`:
- **Odoo 16**: `ir.cron` มี field `numbercall` (จำนวนครั้งที่รัน, -1 = ไม่จำกัด)
- **Odoo 19**: `ir.cron` ไม่มี field `numbercall` แล้ว (default behavior = รันไม่จำกัด)

## วิธีแก้ไข

### ลบ field `numbercall` ออกจาก cron records ทั้งหมด

**เดิม (Odoo 16):**
```xml
<record id="ir_cron_attendance_lateness" model="ir.cron">
    <field name="name">Discipline: Process Lateness from Attendance</field>
    <field name="model_id" ref="hr_attendance.model_hr_attendance"/>
    <field name="state">code</field>
    <field name="code">model.search([('discipline_processed','=', False)])._compute_lateness_and_discipline()</field>
    <field name="interval_type">days</field>
    <field name="interval_number">1</field>
    <field name="numbercall">-1</field>  <!-- ❌ ลบออก -->
    <field name="active">True</field>
    <field name="user_id" ref="base.user_root"/>
</record>
```

**ใหม่ (Odoo 19):**
```xml
<record id="ir_cron_attendance_lateness" model="ir.cron">
    <field name="name">Discipline: Process Lateness from Attendance</field>
    <field name="model_id" ref="hr_attendance.model_hr_attendance"/>
    <field name="state">code</field>
    <field name="code">model.search([('discipline_processed','=', False)])._compute_lateness_and_discipline()</field>
    <field name="interval_type">days</field>
    <field name="interval_number">1</field>
    <!-- ✅ ไม่ต้องระบุ numbercall (default = รันไม่จำกัด) -->
    <field name="active">True</field>
    <field name="user_id" ref="base.user_root"/>
</record>
```

## ไฟล์ที่แก้ไข

1. ✅ `data/cron_lateness.xml` - ลบ `numbercall`
2. ✅ `data/cron.xml` - ลบ `numbercall`
3. ✅ `data/cron_monthly_summary.xml` - ลบ `numbercall`
4. ✅ `data/cron_lateness_monthly_summary.xml` - ลบ `numbercall`

## สรุป

✅ แก้ไขเสร็จสมบูรณ์  
✅ XML syntax ถูกต้อง  
✅ ตามมาตรฐาน Odoo 19  
✅ Cron jobs จะรันไม่จำกัด (default behavior)  

โมดูลพร้อมติดตั้งแล้ว!

