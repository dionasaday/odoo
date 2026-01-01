# 🔍 ตรวจสอบ: ทำไมสร้าง Attendance 5 วันแล้วไม่มีอะไรเกิดขึ้น

## 📋 ขั้นตอนการตรวจสอบ

### 1. ตรวจสอบ Company Settings

**ไปที่:** Settings → Companies → [เลือก Company] → Tab "Attendance & Discipline"

ตรวจสอบว่า:
- **Grace Minutes (Late):** ควรเป็น 5 (default)
- **Alert when late over (min):** ควรเป็น 10 (default) ← **สำคัญ!**
- **Alert every N occurrences:** ควรเป็น 5 (default)
- **Discipline Start Date:** ควรไม่มี หรือตั้งไว้ก่อนวันที่ attendance

### 2. ตรวจสอบว่า Attendance ถูกประมวลผลหรือไม่

**รันสคริปต์นี้ใน Odoo UI → Settings → Technical → Python Code:**

```python
# หาพนักงาน
employee = env['hr.employee'].search([('name', 'ilike', 'ณัฐพล')], limit=1)
if not employee:
    print("❌ ไม่พบพนักงาน")
else:
    print(f"✅ พนักงาน: {employee.name}")
    
    # ตรวจสอบ company settings
    company = employee.company_id or env.company
    print(f"\n📋 Company Settings:")
    print(f"   Grace Minutes: {getattr(company, 'hr_lateness_grace', 5)}")
    print(f"   Min Minutes: {getattr(company, 'lateness_alert_min_minutes', 10)}")
    print(f"   Every N: {getattr(company, 'lateness_alert_every_n', 5)}")
    print(f"   Start Date: {getattr(company, 'discipline_start_date', 'Not set')}")
    
    # หา attendance ล่าสุด
    attendances = env['hr.attendance'].search([
        ('employee_id', '=', employee.id)
    ], order='check_in desc', limit=5)
    
    print(f"\n📊 Attendance Records:")
    for att in attendances:
        print(f"\n   Date: {att.check_in.date() if att.check_in else 'N/A'}")
        print(f"   Check In: {att.check_in}")
        print(f"   Lateness Minutes: {att.lateness_minutes or 0}")
        print(f"   Discipline Processed: {att.discipline_processed}")
        
        # คำนวณ lateness manual
        if att.check_in and att.employee_id:
            try:
                start_utc = att._get_schedule_start(employee, att.check_in)
                late_min = max(0, int((att.check_in - start_utc).total_seconds() // 60))
                grace = getattr(company, 'hr_lateness_grace', 5) or 5
                effective_late = late_min if late_min > grace else 0
                min_min = getattr(company, 'lateness_alert_min_minutes', 10) or 10
                
                print(f"   Calc: Start={start_utc.strftime('%H:%M')}, Late={late_min}min, Grace={grace}min")
                print(f"   Effective Late: {effective_late}min (min required: {min_min}min)")
                
                if effective_late < min_min:
                    print(f"   ⚠️  ไม่ถึงเกณฑ์ ({effective_late} < {min_min})")
                else:
                    print(f"   ✅ ถึงเกณฑ์ ({effective_late} >= {min_min})")
            except Exception as e:
                print(f"   ❌ Error: {e}")
    
    # ตรวจสอบ lateness logs
    logs = env['hr.lateness.log'].search([
        ('employee_id', '=', employee.id)
    ], order='date desc')
    
    print(f"\n📝 Lateness Logs: {len(logs)} รายการ")
    for log in logs[:10]:
        print(f"   {log.date}: {log.minutes}min, Case: {log.case_id.name if log.case_id else 'None'}")
    
    # ตรวจสอบ discipline cases
    cases = env['hr.discipline.case'].search([
        ('employee_id', '=', employee.id),
        ('is_attendance_auto', '=', True)
    ], order='date desc')
    
    print(f"\n⚖️  Discipline Cases: {len(cases)} เคส")
    for case in cases:
        print(f"   {case.name}: {case.date}, {case.points} points")
    
    # Force reprocess unprocessed attendances
    unprocessed = env['hr.attendance'].search([
        ('employee_id', '=', employee.id),
        ('discipline_processed', '=', False),
        ('check_in', '!=', False)
    ])
    
    if unprocessed:
        print(f"\n🔄 กำลังประมวลผล {len(unprocessed)} attendance ที่ยังไม่ได้ประมวลผล...")
        try:
            unprocessed._compute_lateness_and_discipline()
            print("   ✅ เสร็จแล้ว - รันโค้ดนี้อีกครั้งเพื่อดูผลลัพธ์")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"\n⚠️  ทุก attendance ถูกประมวลผลแล้ว - ตรวจสอบว่าถึงเกณฑ์หรือไม่")
```

### 3. ปัญหาที่อาจเกิดขึ้น

#### ปัญหา 1: เวลาเช็คอินไม่สายจริง

**จากภาพ:** Check In เวลา 08:15-08:25

**ถ้าเวลาเริ่มงานเป็น 08:00:**
- สาย 15-25 นาที → ควรถูกนับ ✓

**ถ้าเวลาเริ่มงานเป็น 09:00:**
- ยังไม่ถึงเวลาเริ่มงาน → **ไม่สาย** ❌
- จะไม่ถูกนับเป็น lateness

**แก้ไข:** ตรวจสอบ `resource.calendar_id` ของพนักงานว่าตั้งเวลาเริ่มงานเป็นเท่าไหร่

#### ปัญหา 2: Effective Lateness ไม่ถึงเกณฑ์

**เงื่อนไข:**
- `effective_late >= min_min` (default: 10 นาที)

**ถ้า:**
- สาย 15 นาที แต่มี grace 5 นาที → effective = 10 นาที ✓
- สาย 8 นาที แต่มี grace 5 นาที → effective = 3 นาที ❌ (ไม่ถึงเกณฑ์)

#### ปัญหา 3: ยังไม่ครบ N ครั้ง

**เงื่อนไข:**
- ต้องมี lateness logs ที่ ungrouped >= `every_n` (default: 5)

**ถ้ามี 4 logs:**
- ยังไม่ครบ 5 → ยังไม่สร้างเคส

**แก้ไข:** สร้าง attendance เพิ่มอีก 1 ครั้ง (ถ้าถึงเกณฑ์)

#### ปัญหา 4: `discipline_processed` เป็น True แล้ว

**ถ้า:**
- `discipline_processed = True` → ไม่จะถูกประมวลผลอีก

**แก้ไข:** Reset และประมวลผลใหม่:
```python
attendances = env['hr.attendance'].search([
    ('employee_id', '=', employee.id),
    ('check_in', '>=', '2025-10-27')  # วันที่ต้องการ
])
attendances.write({'discipline_processed': False, 'lateness_minutes': 0})
attendances._compute_lateness_and_discipline()
```

#### ปัญหา 5: `discipline_start_date` กรองออก

**ถ้า:**
- `discipline_start_date = 2025-11-01`
- Attendance วันที่ 10/27-10/30 → **ถูกกรองออก** ❌

**แก้ไข:** ลบหรือเปลี่ยน `discipline_start_date` ให้ก่อนวันที่ต้องการ

### 4. แก้ไขด้วย Script

**รันใน Python Code:**

```python
# หาพนักงาน
employee = env['hr.employee'].search([('name', 'ilike', 'ณัฐพล')], limit=1)

# Reset และประมวลผลใหม่
attendances = env['hr.attendance'].search([
    ('employee_id', '=', employee.id),
    ('check_in', '>=', '2025-10-27')
], order='check_in')

print(f"พบ {len(attendances)} attendance records")

# Reset
attendances.write({
    'discipline_processed': False,
    'lateness_minutes': 0
})

# ประมวลผลใหม่
attendances._compute_lateness_and_discipline()

# ตรวจสอบผลลัพธ์
logs = env['hr.lateness.log'].search([
    ('employee_id', '=', employee.id)
])
print(f"\nLateness Logs: {len(logs)} รายการ")

cases = env['hr.discipline.case'].search([
    ('employee_id', '=', employee.id),
    ('is_attendance_auto', '=', True)
])
print(f"Discipline Cases: {len(cases)} เคส")
```

## ✅ สรุป

**สาเหตุที่อาจเป็นได้:**
1. เวลาเช็คอินไม่สายจริง (เช็คอินก่อนเวลาเริ่มงาน)
2. Effective lateness ไม่ถึงเกณฑ์ (สาย < 10 นาที หลังจากหัก grace)
3. ยังไม่ครบ N ครั้ง (ต้องครบ 5 ครั้ง)
4. `discipline_processed = True` แล้ว → ต้อง reset
5. `discipline_start_date` กรองออก

**วิธีแก้:**
1. รันสคริปต์ตรวจสอบด้านบน
2. Reset `discipline_processed = False`
3. เรียก `_compute_lateness_and_discipline()` ใหม่
4. ตรวจสอบผลลัพธ์

