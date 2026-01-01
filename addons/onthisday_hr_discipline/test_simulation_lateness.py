#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์ทดสอบจำลอง: ทดสอบการแจ้งเตือนเมื่อพนักงานมาสายครบ 5 ครั้ง

วิธีใช้:
1. รันผ่าน Odoo shell:
   python3 odoo-bin shell -d <database_name> < test_simulation_lateness.py

2. หรือ copy code ไปรันใน Odoo shell:
   >>> exec(open('custom_addons/onthisday_hr_discipline/test_simulation_lateness.py').read())

ผลลัพธ์ที่คาดหวัง:
- สร้าง lateness logs 5 รายการ
- สร้าง discipline case 1 เคส (เมื่อครบ 5 ครั้ง)
- ส่งอีเมลแจ้งเตือน (ถ้ามี email template และ email configured)
"""

from datetime import datetime, timedelta, time
from odoo import api, fields
import pytz


def simulate_lateness_test(env, employee_name="ณัฐพล สุภา", lateness_count=5):
    """
    จำลองการมาสายของพนักงาน
    
    Args:
        env: Odoo environment
        employee_name: ชื่อพนักงานที่ต้องการทดสอบ
        lateness_count: จำนวนครั้งที่ต้องการให้มาสาย (default: 5)
    
    Returns:
        dict: ผลลัพธ์การทดสอบ
    """
    result = {
        'success': False,
        'employee': None,
        'attendances_created': [],
        'lateness_logs': [],
        'discipline_cases': [],
        'errors': []
    }
    
    try:
        # 1. หาพนักงาน
        Employee = env['hr.employee'].sudo()
        employee = Employee.search([('name', 'ilike', employee_name)], limit=1)
        
        if not employee:
            result['errors'].append(f"ไม่พบพนักงานชื่อ '{employee_name}'")
            print(f"❌ ไม่พบพนักงานชื่อ '{employee_name}'")
            print("   กำลังค้นหาในรายชื่อพนักงานทั้งหมด...")
            all_employees = Employee.search([])
            print(f"   พบพนักงานทั้งหมด {len(all_employees)} คน")
            for emp in all_employees[:10]:  # แสดงแค่ 10 คนแรก
                print(f"   - {emp.name} (ID: {emp.id})")
            return result
        
        result['employee'] = {
            'id': employee.id,
            'name': employee.name,
            'company_id': employee.company_id.id if employee.company_id else None,
            'company_name': employee.company_id.name if employee.company_id else None,
        }
        
        print(f"✅ พบพนักงาน: {employee.name} (ID: {employee.id})")
        print(f"   บริษัท: {employee.company_id.name if employee.company_id else 'N/A'}")
        
        # 2. ตรวจสอบการตั้งค่าบริษัท
        company = employee.company_id or env.company
        
        # ใช้ getattr เพื่อป้องกัน error ถ้า field ยังไม่มี
        discipline_start = getattr(company, 'discipline_start_date', None)
        grace_minutes = getattr(company, 'hr_lateness_grace', None) or 5
        min_minutes = getattr(company, 'lateness_alert_min_minutes', None) or 10
        every_n = getattr(company, 'lateness_alert_every_n', None) or 5
        
        # ตรวจสอบว่า module ถูกโหลดหรือยัง
        module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)
        if module and module.state != 'installed':
            result['errors'].append(f"โมดูล onthisday_hr_discipline ยังไม่ได้ install (state: {module.state})")
            print(f"⚠️  ข้อความเตือน: โมดูล onthisday_hr_discipline ยังไม่ได้ install/upgrade")
            print(f"   สถานะ: {module.state}")
            print(f"   แนะนำให้ upgrade module ก่อน")
        
        print(f"\n📋 การตั้งค่าบริษัท:")
        print(f"   - Discipline Start Date: {discipline_start or 'ไม่กำหนด'}")
        print(f"   - Grace Minutes: {grace_minutes} นาที")
        print(f"   - Min Minutes (Alert): {min_minutes} นาที")
        print(f"   - Alert Every N: {every_n} ครั้ง")
        
        # ตรวจสอบว่าไม่ย้อนหลังเกิน discipline_start_date
        if discipline_start:
            start_date = fields.Date.to_date(discipline_start)
        else:
            start_date = fields.Date.today() - timedelta(days=30)
        
        # 3. สร้าง attendance records ที่มาสาย
        Attendance = env['hr.attendance'].sudo()
        tz = pytz.timezone(env.user.tz or 'Asia/Bangkok')
        UTC = pytz.UTC
        
        # คำนวณเวลาเริ่มงาน (default 09:00)
        base_time = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        
        # สร้าง attendance 5 ครั้ง (แต่ละครั้งมาสาย 15 นาที)
        lateness_minutes = 15  # มาสาย 15 นาที (เกิน grace และ min_minutes)
        
        print(f"\n🕐 กำลังสร้าง Attendance Records...")
        print(f"   จำนวนครั้ง: {lateness_count} ครั้ง")
        print(f"   มาสาย: {lateness_minutes} นาทีต่อครั้ง")
        
        for i in range(lateness_count):
            # วันที่ (แต่ละวันเว้น 1 วัน)
            check_in_date = start_date + timedelta(days=i*2)
            
            # เวลาเช็คอิน = เวลาเริ่มงาน + lateness
            check_in_time = base_time.replace(
                year=check_in_date.year,
                month=check_in_date.month,
                day=check_in_date.day
            ) + timedelta(minutes=lateness_minutes)
            
            # แปลงเป็น UTC
            local_dt = tz.localize(check_in_time)
            check_in_utc = local_dt.astimezone(UTC).replace(tzinfo=None)
            
            # เวลาเช็คเอาท์ (8 ชั่วโมงหลังจากเช็คอิน)
            check_out_utc = check_in_utc + timedelta(hours=8)
            
            # สร้าง attendance
            attendance_vals = {
                'employee_id': employee.id,
                'check_in': check_in_utc,
                'check_out': check_out_utc,
            }
            
            try:
                attendance = Attendance.create(attendance_vals)
                result['attendances_created'].append({
                    'id': attendance.id,
                    'date': check_in_date.strftime('%Y-%m-%d'),
                    'check_in': check_in_utc.strftime('%Y-%m-%d %H:%M:%S'),
                    'check_out': check_out_utc.strftime('%Y-%m-%d %H:%M:%S'),
                })
                print(f"   ✅ {i+1}. สร้าง Attendance {attendance.id} - {check_in_date.strftime('%Y-%m-%d')} มาสาย {lateness_minutes} นาที")
            except Exception as e:
                error_msg = f"ไม่สามารถสร้าง attendance {i+1}: {str(e)}"
                result['errors'].append(error_msg)
                print(f"   ❌ {error_msg}")
        
        # 4. Trigger การคำนวณ lateness
        print(f"\n🔄 กำลังคำนวณ Lateness และ Discipline...")
        attendances = Attendance.browse([a['id'] for a in result['attendances_created']])
        
        # Reset discipline_processed เพื่อให้คำนวณใหม่
        attendances.write({'discipline_processed': False, 'lateness_minutes': 0})
        
        # เรียก method คำนวณ
        attendances._compute_lateness_and_discipline()
        
        # 5. ตรวจสอบผลลัพธ์
        print(f"\n📊 ตรวจสอบผลลัพธ์...")
        
        # ตรวจสอบ Lateness Logs
        LatenessLog = env['hr.lateness.log'].sudo()
        logs = LatenessLog.search([
            ('employee_id', '=', employee.id),
            ('attendance_id', 'in', attendances.ids)
        ])
        
        result['lateness_logs'] = [{
            'id': log.id,
            'date': log.date.strftime('%Y-%m-%d'),
            'minutes': log.minutes,
            'case_id': log.case_id.id if log.case_id else None,
        } for log in logs]
        
        print(f"   📝 Lateness Logs: {len(logs)} รายการ")
        for log in logs:
            case_info = f" → Case {log.case_id.name}" if log.case_id else ""
            print(f"      - {log.date.strftime('%Y-%m-%d')}: สาย {log.minutes} นาที{case_info}")
        
        # ตรวจสอบ Discipline Cases
        Case = env['hr.discipline.case'].sudo()
        cases = Case.search([
            ('employee_id', '=', employee.id),
            ('is_attendance_auto', '=', True),
            ('date', '>=', start_date)
        ])
        
        result['discipline_cases'] = [{
            'id': case.id,
            'name': case.name,
            'date': case.date.strftime('%Y-%m-%d'),
            'status': case.status,
            'points': case.points,
            'lateness_logs_count': len(case.lateness_log_ids),
        } for case in cases]
        
        print(f"\n   ⚠️  Discipline Cases: {len(cases)} เคส")
        for case in cases:
            print(f"      - {case.name} ({case.date.strftime('%Y-%m-%d')}): Status={case.status}, Points={case.points}")
            print(f"        รายการ Lateness: {len(case.lateness_log_ids)} รายการ")
        
        # 6. สรุปผลการทดสอบ
        print(f"\n{'='*60}")
        print(f"📋 สรุปผลการทดสอบ")
        print(f"{'='*60}")
        
        expected_logs = lateness_count if lateness_minutes >= min_minutes else 0
        expected_cases = 1 if len(logs) >= every_n else 0
        
        success = True
        if len(logs) != expected_logs:
            print(f"⚠️  Lateness Logs: ได้ {len(logs)} รายการ (คาดหวัง: {expected_logs})")
            success = False
        else:
            print(f"✅ Lateness Logs: {len(logs)} รายการ")
        
        if len(cases) != expected_cases:
            print(f"⚠️  Discipline Cases: ได้ {len(cases)} เคส (คาดหวัง: {expected_cases})")
            if len(cases) == 0:
                print(f"   💡 สาเหตุที่เป็นไปได้:")
                print(f"      - ยังไม่ครบ {every_n} ครั้ง (มี {len(logs)} logs)")
                print(f"      - มี logs ที่ถูกผูกกับ case เก่าแล้ว")
            success = False
        else:
            print(f"✅ Discipline Cases: {len(cases)} เคส")
        
        if cases:
            case = cases[0]
            if case.status == 'confirmed':
                print(f"✅ Case ถูกยืนยันแล้ว (Status: {case.status})")
            else:
                print(f"⚠️  Case ยังไม่ถูกยืนยัน (Status: {case.status})")
        
        result['success'] = success
        
        print(f"\n{'='*60}")
        if success:
            print(f"✅ การทดสอบสำเร็จ!")
        else:
            print(f"⚠️  การทดสอบมีปัญหา (ดูรายละเอียดด้านบน)")
        print(f"{'='*60}")
        
        return result
        
    except Exception as e:
        error_msg = f"เกิดข้อผิดพลาด: {str(e)}"
        result['errors'].append(error_msg)
        print(f"❌ {error_msg}")
        import traceback
        traceback.print_exc()
        return result


# ถ้ารันสคริปต์นี้โดยตรง
if __name__ == "__main__":
    # สำหรับรันใน Odoo shell
    print("\n" + "="*60)
    print("🧪 สคริปต์ทดสอบจำลอง: การแจ้งเตือนเมื่อมาสายครบ 5 ครั้ง")
    print("="*60 + "\n")
    
    # เรียกใช้ function
    result = simulate_lateness_test(env, employee_name="ณัฐพล สุภา", lateness_count=5)
    
    print("\n📝 ผลลัพธ์แบบละเอียด:")
    print(f"   Employee: {result['employee']}")
    print(f"   Attendances: {len(result['attendances_created'])} รายการ")
    print(f"   Lateness Logs: {len(result['lateness_logs'])} รายการ")
    print(f"   Discipline Cases: {len(result['discipline_cases'])} เคส")
    if result['errors']:
        print(f"   Errors: {len(result['errors'])} รายการ")
        for err in result['errors']:
            print(f"      - {err}")

