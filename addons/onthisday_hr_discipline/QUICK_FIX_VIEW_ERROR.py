#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick Fix Script: ตรวจสอบและแก้ปัญหา View Error

Error: can't access property "relation", models[resModel][fieldName] is undefined

รันสคริปต์นี้ใน Odoo shell เพื่อตรวจสอบและแนะนำวิธีแก้ไข
"""

print("\n" + "="*60)
print("🔍 ตรวจสอบปัญหา View Error")
print("="*60 + "\n")

# 1. ตรวจสอบ Module State
module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)

if not module:
    print("❌ ไม่พบโมดูล onthisday_hr_discipline")
    print("   แนะนำให้ install module ก่อน")
    print("   python3 odoo-bin -i onthisday_hr_discipline -d", env.cr.dbname, "--stop-after-init")
else:
    print(f"✅ พบโมดูล: {module.name}")
    print(f"   State: {module.state}")
    print(f"   Installed: {module.state == 'installed'}")
    
    if module.state != 'installed':
        print(f"\n⚠️  ปัญหา: Module ยังไม่ได้ install/upgrade")
        print(f"   แนะนำให้ upgrade module:")
        print(f"   python3 odoo-bin -u onthisday_hr_discipline -d {env.cr.dbname} --stop-after-init")
    else:
        print(f"\n✅ Module ถูก install แล้ว")
        
        # 2. ตรวจสอบ Fields ใน Model
        print(f"\n🔍 ตรวจสอบ Fields ใน Model...")
        
        try:
            Case = env['hr.discipline.case']
            fields_to_check = [
                'calendar_year',
                'preview_points_before',
                'preview_points_after',
                'total_points_before',
                'total_points_after',
                'action_suggested_id',
                'action_taken_id',
                'reset_points',
            ]
            
            missing_fields = []
            for field_name in fields_to_check:
                if hasattr(Case, '_fields') and field_name in Case._fields:
                    print(f"   ✅ {field_name}")
                else:
                    print(f"   ❌ {field_name} - ไม่พบใน model")
                    missing_fields.append(field_name)
            
            if missing_fields:
                print(f"\n⚠️  Fields ที่ไม่พบ: {missing_fields}")
                print(f"   แนะนำให้ upgrade module อีกครั้ง:")
                print(f"   python3 odoo-bin -u onthisday_hr_discipline -d {env.cr.dbname} --stop-after-init")
            else:
                print(f"\n✅ Fields ทั้งหมดมีใน model แล้ว")
                print(f"   ถ้ายังมี error ให้ลอง:")
                print(f"   1. Restart Odoo server")
                print(f"   2. Hard reload browser (Ctrl+Shift+R หรือ Cmd+Shift+R)")
                print(f"   3. Clear browser cache")
                
        except Exception as e:
            print(f"\n❌ Error ในการตรวจสอบ: {str(e)}")
            print(f"   แนะนำให้ upgrade module:")
            print(f"   python3 odoo-bin -u onthisday_hr_discipline -d {env.cr.dbname} --stop-after-init")

print("\n" + "="*60)

