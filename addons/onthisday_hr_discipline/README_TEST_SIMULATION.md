# คู่มือการทดสอบจำลอง: การแจ้งเตือนเมื่อมาสายครบ 5 ครั้ง

## วัตถุประสงค์

ทดสอบระบบวินัยและการแจ้งเตือนโดยจำลองสถานการณ์ที่พนักงาน "ณัฐพล สุภา" มาสายครบ 5 ครั้ง เพื่อตรวจสอบว่า:
- ระบบสร้าง Lateness Logs ถูกต้องหรือไม่
- ระบบสร้าง Discipline Case อัตโนมัติเมื่อครบ 5 ครั้งหรือไม่
- ระบบส่งอีเมลแจ้งเตือนหรือไม่

## วิธีใช้งาน

### วิธีที่ 1: รันผ่าน Odoo Shell (แนะนำ)

```bash
cd /Users/nattaphonsupa/odoo-16
python3 odoo-bin shell -d <database_name> < custom_addons/onthisday_hr_discipline/test_simulation_lateness.py
```

**ตัวอย่าง:**
```bash
python3 odoo-bin shell -d nt < custom_addons/onthisday_hr_discipline/test_simulation_lateness.py
```

### วิธีที่ 2: Copy Code ไปรันใน Odoo Shell

1. เปิด Odoo shell:
```bash
python3 odoo-bin shell -d <database_name>
```

2. Copy และ paste code ต่อไปนี้:

```python
from datetime import datetime, timedelta
import pytz
from odoo import api, fields

# หาพนักงาน
employee = env['hr.employee'].sudo().search([('name', 'ilike', 'ณัฐพล สุภา')], limit=1)
if not employee:
    print("ไม่พบพนักงาน")
else:
    print(f"พบ: {employee.name}")
    
    # ตั้งค่า
    company = employee.company_id or env.company
    lateness_count = 5
    lateness_minutes = 15  # มาสาย 15 นาที
    
    # สร้าง attendance
    Attendance = env['hr.attendance'].sudo()
    tz = pytz.timezone('Asia/Bangkok')
    UTC = pytz.UTC
    
    start_date = fields.Date.today() - timedelta(days=10)
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    
    attendances = []
    for i in range(lateness_count):
        check_in_date = start_date + timedelta(days=i*2)
        check_in_time = base_time.replace(year=check_in_date.year, month=check_in_date.month, day=check_in_date.day) + timedelta(minutes=lateness_minutes)
        local_dt = tz.localize(check_in_time)
        check_in_utc = local_dt.astimezone(UTC).replace(tzinfo=None)
        check_out_utc = check_in_utc + timedelta(hours=8)
        
        att = Attendance.create({
            'employee_id': employee.id,
            'check_in': check_in_utc,
            'check_out': check_out_utc,
        })
        attendances.append(att)
        print(f"สร้าง Attendance {i+1}: {check_in_date.strftime('%Y-%m-%d')}")
    
    # Trigger การคำนวณ
    for att in attendances:
        att.write({'discipline_processed': False, 'lateness_minutes': 0})
    attendances._compute_lateness_and_discipline()
    
    # ตรวจสอบผลลัพธ์
    logs = env['hr.lateness.log'].sudo().search([('employee_id', '=', employee.id), ('attendance_id', 'in', [a.id for a in attendances])])
    cases = env['hr.discipline.case'].sudo().search([('employee_id', '=', employee.id), ('is_attendance_auto', '=', True)])
    
    print(f"\nLateness Logs: {len(logs)}")
    print(f"Discipline Cases: {len(cases)}")
```

### วิธีที่ 3: สร้าง Custom Script ใน Odoo UI

1. ไปที่ **Settings > Technical > Actions > Server Actions**
2. สร้าง Server Action ใหม่
3. Copy code จาก `test_simulation_lateness.py` มาใส่
4. รันผ่านเมนูที่ต้องการ

## ผลลัพธ์ที่คาดหวัง

### 1. Lateness Logs
- ควรสร้าง 5 รายการ (ถ้าสาย >= min_minutes)
- แต่ละรายการมี `minutes` = 15 (หรือตามที่ตั้งค่า)
- ผูกกับ attendance ที่สร้าง

### 2. Discipline Case
- ควรสร้าง 1 เคส เมื่อครบ 5 ครั้ง
- Status ควรเป็น 'confirmed'
- มี `is_attendance_auto` = True
- ผูกกับ Lateness Logs 5 รายการ

### 3. Email Notifications
- ส่งอีเมลไปยังพนักงาน (ถ้ามี email)
- ส่งอีเมลไปยังหัวหน้า (ถ้ามี email)
- ใช้ template `mail_tmpl_lateness_bundle_to_employee` และ `mail_tmpl_lateness_bundle_to_manager`

## การตรวจสอบผลลัพธ์

### ผ่าน Odoo UI:

1. **ตรวจสอบ Lateness Logs:**
   - ไปที่เมนู **วินัยและบทลงโทษ > Lateness Logs**
   - กรองตามพนักงาน "ณัฐพล สุภา"
   - ควรเห็น 5 รายการ

2. **ตรวจสอบ Discipline Cases:**
   - ไปที่เมนู **วินัยและบทลงโทษ > กรณีความผิด**
   - กรองตามพนักงาน "ณัฐพล สุภา"
   - ควรเห็น 1 เคสที่มี description "Auto from Attendance: Lateness reached 5 times"

3. **ตรวจสอบ Email:**
   - ไปที่เมนู **Technical > Email > Messages**
   - กรองตาม recipient หรือ subject
   - ควรเห็น email ที่ส่งออกไป

### ผ่าน Odoo Shell:

```python
# ตรวจสอบ Lateness Logs
logs = env['hr.lateness.log'].sudo().search([
    ('employee_id.name', 'ilike', 'ณัฐพล สุภา')
])
print(f"Lateness Logs: {len(logs)}")
for log in logs:
    print(f"  - {log.date}: {log.minutes} นาที, Case: {log.case_id.name if log.case_id else 'None'}")

# ตรวจสอบ Discipline Cases
cases = env['hr.discipline.case'].sudo().search([
    ('employee_id.name', 'ilike', 'ณัฐพล สุภา'),
    ('is_attendance_auto', '=', True)
])
print(f"\nDiscipline Cases: {len(cases)}")
for case in cases:
    print(f"  - {case.name}: {case.status}, Points: {case.points}, Logs: {len(case.lateness_log_ids)}")
```

## ปัญหาที่อาจพบ

### 1. ไม่พบพนักงาน
- **แก้ไข:** ตรวจสอบชื่อพนักงานในระบบ หรือแก้ไขชื่อใน script

### 2. ไม่สร้าง Lateness Logs
- **สาเหตุที่เป็นไปได้:**
  - มาสายไม่ถึง `lateness_alert_min_minutes` (default 10 นาที)
  - มีการลาอนุมัติในวันนั้น
  - วันที่ย้อนหลังเกิน `discipline_start_date`
- **แก้ไข:** ตรวจสอบการตั้งค่าบริษัทและวันที่สร้าง attendance

### 3. ไม่สร้าง Discipline Case
- **สาเหตุที่เป็นไปได้:**
  - ยังไม่ครบ `lateness_alert_every_n` ครั้ง (default 5)
  - มี logs ที่ถูกผูกกับ case เก่าแล้ว
- **แก้ไข:** ลบ lateness logs เก่าหรือสร้างใหม่

### 4. Case ไม่ถูกยืนยันอัตโนมัติ
- **สาเหตุที่เป็นไปได้:**
  - Method `action_confirm()` ไม่ถูกเรียก
  - มี error ระหว่างการยืนยัน
- **แก้ไข:** ตรวจสอบ logs ใน Odoo หรือ database

## Cleanup (ลบข้อมูลทดสอบ)

หลังจากทดสอบเสร็จ อาจต้องการลบข้อมูลทดสอบ:

```python
# ลบ Lateness Logs
env['hr.lateness.log'].sudo().search([
    ('employee_id.name', 'ilike', 'ณัฐพล สุภา'),
    ('case_id.is_attendance_auto', '=', True)
]).unlink()

# ลบ Discipline Cases
env['hr.discipline.case'].sudo().search([
    ('employee_id.name', 'ilike', 'ณัฐพล สุภา'),
    ('is_attendance_auto', '=', True)
]).unlink()

# ลบ Attendances (ระวัง: อาจลบข้อมูลจริงได้)
# env['hr.attendance'].sudo().search([
#     ('employee_id.name', 'ilike', 'ณัฐพล สุภา'),
#     ('id', 'in', [attendance_ids ที่สร้างจาก test])
# ]).unlink()
```

## หมายเหตุ

- Script นี้จะสร้างข้อมูลจริงใน database
- แนะนำให้ทดสอบใน development/staging environment ก่อน
- Backup database ก่อนทดสอบ
- ข้อมูลที่สร้างสามารถลบได้ด้วย manual cleanup

