#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์ตรวจสอบและแก้ไขปัญหา create() method

รันใน Odoo shell:
python3 odoo-bin shell -d nt_test < custom_addons/onthisday_hr_discipline/CHECK_AND_FIX_CREATE.py
"""

import inspect

print("\n" + "="*60)
print("🔍 ตรวจสอบ create() method signature")
print("="*60 + "\n")

# 1. ตรวจสอบ DisciplineCase.create()
try:
    Case = env['hr.discipline.case']
    sig = inspect.signature(Case.create)
    print(f"✅ hr.discipline.case.create() signature: {sig}")
    
    params = list(sig.parameters.keys())
    if 'vals_list' in params:
        param = sig.parameters['vals_list']
        if param.default != inspect.Parameter.empty:
            print(f"   ✅ vals_list มี default value: {param.default}")
        else:
            print(f"   ⚠️  vals_list ไม่มี default value (required)")
    else:
        print(f"   ❌ ไม่พบ parameter 'vals_list'")
        
except Exception as e:
    print(f"❌ Error: {str(e)}")

# 2. ตรวจสอบ source code
print(f"\n📝 ตรวจสอบ source code:")
try:
    import os
    case_file = os.path.join(
        os.path.dirname(__file__) if '__file__' in globals() else '.',
        'custom_addons/onthisday_hr_discipline/models/case.py'
    )
    with open(case_file, 'r') as f:
        lines = f.readlines()
        for i, line in enumerate(lines[270:280], start=271):
            if 'def create' in line:
                print(f"   บรรทัด {i}: {line.strip()}")
                if i+1 < len(lines):
                    print(f"   บรรทัด {i+1}: {lines[i].strip()}")
                break
except Exception as e:
    print(f"   ⚠️  ไม่สามารถอ่านไฟล์: {str(e)}")

# 3. แนะนำวิธีแก้ไข
print(f"\n💡 คำแนะนำ:")
print(f"   1. Restart Odoo server (Ctrl+C แล้วเริ่มใหม่)")
print(f"   2. Hard reload browser (Ctrl+Shift+R)")
print(f"   3. ลองสร้าง record ใหม่อีกครั้ง")

print("\n" + "="*60)

