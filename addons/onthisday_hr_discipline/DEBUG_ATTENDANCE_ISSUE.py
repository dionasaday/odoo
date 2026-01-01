#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์ Debug ปัญหา: สร้าง attendance 5 วันแล้วแต่ไม่มีอะไรเกิดขึ้น

รันใน Odoo UI → Settings → Technical → Python Code
"""

# หาพนักงาน "ณัฐพล สุภา"
employee = env['hr.employee'].search([('name', 'ilike', 'ณัฐพล')], limit=1)
if not employee:
    print("❌ ไม่พบพนักงาน 'ณัฐพล สุภา'")
else:
    print(f"✅ พบพนักงาน: {employee.name} (ID: {employee.id})")
    print(f"   Company: {employee.company_id.name if employee.company_id else 'N/A'}")
    print(f"   Calendar: {employee.resource_calendar_id.name if employee.resource_calendar_id else 'N/A'}")
    
    # ตรวจสอบ company settings
    company = employee.company_id or env.company
    print(f"\n📋 Company Settings:")
    print(f"   hr_lateness_grace: {getattr(company, 'hr_lateness_grace', 'N/A')}")
    print(f"   lateness_alert_min_minutes: {getattr(company, 'lateness_alert_min_minutes', 'N/A')}")
    print(f"   lateness_alert_every_n: {getattr(company, 'lateness_alert_every_n', 'N/A')}")
    print(f"   discipline_start_date: {getattr(company, 'discipline_start_date', 'N/A')}")
    
    # หา attendance records ล่าสุด 5 รายการ
    attendances = env['hr.attendance'].search([
        ('employee_id', '=', employee.id)
    ], order='check_in desc', limit=5)
    
    print(f"\n📊 Attendance Records ({len(attendances)} รายการ):")
    for att in attendances:
        print(f"\n   Date: {att.check_in.date() if att.check_in else 'N/A'}")
        print(f"   Check In: {att.check_in}")
        print(f"   Check Out: {att.check_out or 'N/A'}")
        print(f"   Lateness Minutes: {att.lateness_minutes or 0}")
        print(f"   Discipline Processed: {att.discipline_processed}")
        
        # คำนวณ lateness แบบ manual
        if att.check_in:
            try:
                # หาเวลาเริ่มงาน
                start_utc = att._get_schedule_start(employee, att.check_in)
                late_min = max(0, int((att.check_in - start_utc).total_seconds() // 60))
                grace = getattr(company, 'hr_lateness_grace', 0) or 0
                effective_late = late_min if late_min > grace else 0
                print(f"   Manual Calc - Start: {start_utc}, Late: {late_min} min, Grace: {grace}, Effective: {effective_late} min")
            except Exception as e:
                print(f"   ⚠️  Error calculating: {e}")
    
    # ตรวจสอบ lateness logs
    logs = env['hr.lateness.log'].search([
        ('employee_id', '=', employee.id)
    ], order='date desc', limit=10)
    
    print(f"\n📝 Lateness Logs ({len(logs)} รายการ):")
    for log in logs:
        print(f"   Date: {log.date}, Minutes: {log.minutes}, Case: {log.case_id.name if log.case_id else 'None'}")
    
    # ตรวจสอบ discipline cases
    cases = env['hr.discipline.case'].search([
        ('employee_id', '=', employee.id)
    ], order='date desc', limit=5)
    
    print(f"\n⚖️  Discipline Cases ({len(cases)} เคส):")
    for case in cases:
        print(f"   Case: {case.name}, Date: {case.date}, Points: {case.points}, Offense: {case.offense_id.name if case.offense_id else 'N/A'}")
    
    # ตรวจสอบว่า attendance มีการประมวลผลหรือไม่
    unprocessed = env['hr.attendance'].search([
        ('employee_id', '=', employee.id),
        ('discipline_processed', '=', False),
        ('check_in', '!=', False)
    ])
    
    print(f"\n⚠️  Unprocessed Attendances: {len(unprocessed)} รายการ")
    if unprocessed:
        print("   กำลังประมวลผล attendance ที่ยังไม่ได้ประมวลผล...")
        try:
            unprocessed._compute_lateness_and_discipline()
            print("   ✅ ประมวลผลเสร็จแล้ว")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

