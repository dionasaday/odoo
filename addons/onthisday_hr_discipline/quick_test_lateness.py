#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Test Script - ทดสอบการแจ้งเตือนเมื่อมาสายครบ 5 ครั้ง
Copy และ paste code นี้ไปรันใน Odoo shell ได้เลย
"""

from datetime import datetime, timedelta
import pytz

# ========== ตั้งค่า ==========
EMPLOYEE_NAME = "ณัฐพล สุภา"  # เปลี่ยนชื่อได้ตามต้องการ
LATENESS_COUNT = 5  # จำนวนครั้งที่ต้องการให้มาสาย
LATENESS_MINUTES = 15  # มาสายกี่นาทีต่อครั้ง (ควร >= 10)

# ========== Code เริ่มต้น ==========
print("\n" + "="*60)
print("🧪 Quick Test: การแจ้งเตือนเมื่อมาสายครบ 5 ครั้ง")
print("="*60 + "\n")

# 1. หาพนักงาน
employee = env['hr.employee'].sudo().search([('name', 'ilike', EMPLOYEE_NAME)], limit=1)

if not employee:
    print(f"❌ ไม่พบพนักงานชื่อ '{EMPLOYEE_NAME}'")
    print("\nรายชื่อพนักงานที่มี:")
    all_emps = env['hr.employee'].sudo().search([], limit=10)
    for emp in all_emps:
        print(f"   - {emp.name} (ID: {emp.id})")
else:
    print(f"✅ พบพนักงาน: {employee.name} (ID: {employee.id})")
    company = employee.company_id or env.company
    print(f"   บริษัท: {company.name}")
    
    # ใช้ getattr เพื่อป้องกัน error ถ้า field ยังไม่มี (module ยังไม่ได้ upgrade)
    grace_minutes = getattr(company, 'hr_lateness_grace', None) or 5
    min_minutes = getattr(company, 'lateness_alert_min_minutes', None) or 10
    every_n = getattr(company, 'lateness_alert_every_n', None) or 5
    
    print(f"   Grace Minutes: {grace_minutes}")
    print(f"   Min Minutes: {min_minutes}")
    print(f"   Every N: {every_n}")
    
    # ตรวจสอบว่า module ถูกโหลดหรือยัง
    module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)
    if module and module.state != 'installed':
        print(f"\n⚠️  ข้อความเตือน: โมดูล onthisday_hr_discipline ยังไม่ได้ install/upgrade")
        print(f"   สถานะ: {module.state}")
        print(f"   แนะนำให้ upgrade module ก่อน:")
        print(f"   python3 odoo-bin -u onthisday_hr_discipline -d {env.cr.dbname} --stop-after-init")
    
    # 2. สร้าง attendance records
    Attendance = env['hr.attendance'].sudo()
    tz = pytz.timezone('Asia/Bangkok')
    UTC = pytz.UTC
    
    # วันที่เริ่มต้น (วันนี้ - 10 วัน)
    start_date = fields.Date.today() - timedelta(days=10)
    base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    
    print(f"\n🕐 กำลังสร้าง Attendance {LATENESS_COUNT} ครั้ง...")
    attendances = []
    
    for i in range(LATENESS_COUNT):
        check_in_date = start_date + timedelta(days=i*2)  # เว้นวันละ 2 วัน
        
        # เวลาเช็คอิน = 09:00 + lateness
        check_in_time = base_time.replace(
            year=check_in_date.year,
            month=check_in_date.month,
            day=check_in_date.day
        ) + timedelta(minutes=LATENESS_MINUTES)
        
        # แปลงเป็น UTC
        local_dt = tz.localize(check_in_time)
        check_in_utc = local_dt.astimezone(UTC).replace(tzinfo=None)
        check_out_utc = check_in_utc + timedelta(hours=8)
        
        att = Attendance.create({
            'employee_id': employee.id,
            'check_in': check_in_utc,
            'check_out': check_out_utc,
        })
        attendances.append(att)
        print(f"   ✅ {i+1}. {check_in_date.strftime('%Y-%m-%d')} - มาสาย {LATENESS_MINUTES} นาที")
    
    # 3. Trigger การคำนวณ
    print(f"\n🔄 กำลังคำนวณ Lateness และ Discipline...")
    for att in attendances:
        att.write({'discipline_processed': False, 'lateness_minutes': 0})
    
    attendances._compute_lateness_and_discipline()
    
    # 4. ตรวจสอบผลลัพธ์
    print(f"\n📊 ผลลัพธ์:")
    
    # Lateness Logs
    logs = env['hr.lateness.log'].sudo().search([
        ('employee_id', '=', employee.id),
        ('attendance_id', 'in', [a.id for a in attendances])
    ])
    
    print(f"   📝 Lateness Logs: {len(logs)} รายการ")
    for log in logs[:5]:  # แสดงแค่ 5 รายการแรก
        case_info = f" → Case {log.case_id.name}" if log.case_id else ""
        print(f"      - {log.date.strftime('%Y-%m-%d')}: สาย {log.minutes} นาที{case_info}")
    
    # Discipline Cases
    cases = env['hr.discipline.case'].sudo().search([
        ('employee_id', '=', employee.id),
        ('is_attendance_auto', '=', True),
        ('date', '>=', start_date)
    ])
    
    print(f"\n   ⚠️  Discipline Cases: {len(cases)} เคส")
    for case in cases:
        print(f"      - {case.name} ({case.date.strftime('%Y-%m-%d')}):")
        print(f"        Status: {case.status}, Points: {case.points}")
        print(f"        Lateness Logs: {len(case.lateness_log_ids)} รายการ")
    
    # 5. สรุป
    print(f"\n{'='*60}")
    if len(logs) == LATENESS_COUNT and len(cases) >= 1:
        print("✅ การทดสอบสำเร็จ!")
        print(f"   - สร้าง Lateness Logs: {len(logs)}/{LATENESS_COUNT} รายการ ✓")
        print(f"   - สร้าง Discipline Case: {len(cases)} เคส ✓")
        if cases[0].status == 'confirmed':
            print(f"   - Case Status: Confirmed ✓")
    else:
        print("⚠️  การทดสอบมีปัญหา:")
        if len(logs) != LATENESS_COUNT:
            print(f"   - Lateness Logs: ได้ {len(logs)}/{LATENESS_COUNT}")
        if len(cases) == 0:
            print(f"   - Discipline Case: ยังไม่ถูกสร้าง (มี logs {len(logs)} รายการ)")
            required_n = getattr(company, 'lateness_alert_every_n', None) or 5
            if len(logs) < required_n:
                print(f"      💡 ต้องมี logs อย่างน้อย {required_n} รายการ")
    print(f"{'='*60}\n")

