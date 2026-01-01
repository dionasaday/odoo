#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์แก้ไข: สร้าง Attendance แล้วแต่ไม่มีเคสเกิดขึ้น

รันใน Odoo UI → Settings → Technical → Python Code
"""

# หาพนักงาน "ณัฐพล สุภา"
employee = env['hr.employee'].search([('name', 'ilike', 'ณัฐพล')], limit=1)

if not employee:
    print("❌ ไม่พบพนักงาน 'ณัฐพล สุภา'")
    print("\nรายชื่อพนักงาน:")
    for emp in env['hr.employee'].search([], limit=10):
        print(f"   - {emp.name} (ID: {emp.id})")
else:
    print(f"✅ พบพนักงาน: {employee.name} (ID: {employee.id})")
    
    # ตรวจสอบ company settings
    company = employee.company_id or env.company
    grace = getattr(company, 'hr_lateness_grace', None) or 5
    min_min = getattr(company, 'lateness_alert_min_minutes', None) or 10
    every_n = getattr(company, 'lateness_alert_every_n', None) or 5
    start_date = getattr(company, 'discipline_start_date', None)
    
    print(f"\n📋 Company Settings:")
    print(f"   Grace Minutes: {grace}")
    print(f"   Min Minutes (threshold): {min_min}")
    print(f"   Every N occurrences: {every_n}")
    print(f"   Discipline Start Date: {start_date or 'Not set'}")
    
    # หา attendance ล่าสุด 5 รายการ
    attendances = env['hr.attendance'].search([
        ('employee_id', '=', employee.id)
    ], order='check_in desc', limit=10)
    
    print(f"\n📊 Attendance Records ({len(attendances)} รายการ):")
    
    # Reset และประมวลผลใหม่
    print(f"\n🔄 กำลัง Reset และประมวลผลใหม่...")
    
    # หา attendance ที่ควรประมวลผล (ตั้งแต่ 10/27 ขึ้นไป)
    target_attendances = env['hr.attendance'].search([
        ('employee_id', '=', employee.id),
        ('check_in', '>=', '2025-10-27')
    ], order='check_in')
    
    print(f"   พบ {len(target_attendances)} attendance ที่ต้องประมวลผล")
    
    # Reset
    target_attendances.write({
        'discipline_processed': False,
        'lateness_minutes': 0
    })
    print(f"   ✅ Reset discipline_processed และ lateness_minutes แล้ว")
    
    # ประมวลผลใหม่
    try:
        target_attendances._compute_lateness_and_discipline()
        print(f"   ✅ ประมวลผลเสร็จแล้ว")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # ตรวจสอบผลลัพธ์
    print(f"\n📊 ผลลัพธ์หลังประมวลผล:")
    
    for att in target_attendances[:5]:
        print(f"\n   Date: {att.check_in.date() if att.check_in else 'N/A'}")
        print(f"   Check In: {att.check_in.strftime('%Y-%m-%d %H:%M:%S') if att.check_in else 'N/A'}")
        
        # คำนวณ manual
        if att.check_in and att.employee_id:
            try:
                start_utc = att._get_schedule_start(employee, att.check_in)
                late_min = max(0, int((att.check_in - start_utc).total_seconds() // 60))
                effective_late = late_min if late_min > grace else 0
                
                print(f"   Scheduled Start: {start_utc.strftime('%H:%M:%S')}")
                print(f"   Late (raw): {late_min} min")
                print(f"   Late (effective): {att.lateness_minutes or 0} min")
                print(f"   Processed: {att.discipline_processed}")
                
                if effective_late >= min_min:
                    print(f"   ✅ ถึงเกณฑ์ ({effective_late} >= {min_min})")
                else:
                    print(f"   ⚠️  ไม่ถึงเกณฑ์ ({effective_late} < {min_min})")
            except Exception as e:
                print(f"   ❌ Error calculating: {e}")
    
    # ตรวจสอบ lateness logs
    logs = env['hr.lateness.log'].search([
        ('employee_id', '=', employee.id),
        ('date', '>=', '2025-10-27')
    ], order='date asc')
    
    print(f"\n📝 Lateness Logs: {len(logs)} รายการ")
    for log in logs:
        case_info = f" → Case {log.case_id.name}" if log.case_id else " (ยังไม่มีเคส)"
        print(f"   {log.date}: สาย {log.minutes} นาที{case_info}")
    
    # ตรวจสอบ ungrouped logs (ที่ยังไม่มีเคส)
    ungrouped = env['hr.lateness.log'].search([
        ('employee_id', '=', employee.id),
        ('case_id', '=', False),
        ('minutes', '>=', min_min),
        ('date', '>=', start_date) if start_date else ('date', '>=', '2025-10-27')
    ], order='date asc')
    
    print(f"\n📋 Ungrouped Logs (ยังไม่มีเคส): {len(ungrouped)} รายการ")
    print(f"   ต้องมี {every_n} รายการเพื่อสร้างเคส")
    if len(ungrouped) >= every_n:
        print(f"   ✅ ครบ {len(ungrouped)} >= {every_n} - ควรมีเคสแล้ว")
    else:
        print(f"   ⚠️  ยังไม่ครบ ({len(ungrouped)} < {every_n})")
    
    # ตรวจสอบ discipline cases
    cases = env['hr.discipline.case'].search([
        ('employee_id', '=', employee.id),
        ('is_attendance_auto', '=', True),
        ('date', '>=', '2025-10-27')
    ], order='date desc')
    
    print(f"\n⚖️  Discipline Cases: {len(cases)} เคส")
    for case in cases:
        print(f"   {case.name}: {case.date}, {case.points} points, {case.offense_id.name if case.offense_id else 'N/A'}")
    
    if len(cases) == 0 and len(ungrouped) >= every_n:
        print(f"\n⚠️  มี logs ครบแต่ยังไม่มีเคส - กำลังสร้างเคสใหม่...")
        try:
            # Force create case
            group_logs = ungrouped[:every_n]
            
            # หา offense
            offense = env.ref('onthisday_hr_discipline.offense_late_bundle', raise_if_not_found=False)
            if not offense:
                cat = env['hr.discipline.offense.category'].search([('name', '=', 'Lateness')], limit=1)
                offense = env['hr.discipline.offense'].create({
                    'name': f'Lateness (every {every_n} times)',
                    'points': 1,
                    'category_id': cat.id if cat else False,
                })
            
            # สร้าง description พร้อมรายละเอียดเวลาเข้า-ออก
            details_lines = []
            for log in group_logs:
                date_str = log.date.strftime('%Y-%m-%d')
                check_in = "-"
                check_out = "-"
                
                if log.attendance_id:
                    if log.attendance_id.check_in:
                        # check_in เป็น datetime object อยู่แล้ว
                        check_in = log.attendance_id.check_in.strftime('%H:%M') if hasattr(log.attendance_id.check_in, 'strftime') else "-"
                    if log.attendance_id.check_out:
                        # check_out เป็น datetime object อยู่แล้ว
                        check_out = log.attendance_id.check_out.strftime('%H:%M') if hasattr(log.attendance_id.check_out, 'strftime') else "-"
                
                details_lines.append(
                    f"  • {date_str} - เข้างาน: {check_in}, ออกงาน: {check_out}, สาย: {log.minutes} นาที"
                )
            
            description_base = f'Auto from Attendance: Lateness reached {every_n} times (>= {min_min} min).\n\nรายละเอียดการมาสาย:'
            description_full = description_base + '\n' + '\n'.join(details_lines)
            
            case_vals = {
                'employee_id': employee.id,
                'date': group_logs[-1].date,
                'offense_id': offense.id,
                'description': description_full,
                'is_attendance_auto': True,
                'lateness_minutes': sum(group_logs.mapped('minutes')),
            }
            
            new_case = env['hr.discipline.case'].create(case_vals)
            group_logs.write({'case_id': new_case.id})
            
            print(f"   ✅ สร้างเคส {new_case.name} สำเร็จ")
            new_case.action_confirm()
            print(f"   ✅ ยืนยันเคสสำเร็จ")
        except Exception as e:
            print(f"   ❌ Error creating case: {e}")
            import traceback
            traceback.print_exc()

