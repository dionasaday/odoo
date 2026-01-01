#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์ Force Upgrade Module (รันผ่าน Odoo UI)

วิธีใช้:
1. เปิด Odoo UI
2. Enable Developer Mode
3. ไปที่ Settings → Technical → Python Code
4. Copy และ paste โค้ดด้านล่าง
5. Execute
"""

# Upgrade module เพื่อ force reload
module = env['ir.module.module'].search([('name', '=', 'onthisday_hr_discipline')], limit=1)
if module:
    print(f"Found module: {module.name}, State: {module.state}")
    module.button_immediate_upgrade()
    print("✅ Module upgraded")
else:
    print("❌ Module not found")

# Clear registry cache
env.registry.clear_cache()
env.registry.setup_models(env.cr)

# ตรวจสอบ signature
import inspect
Case = env['hr.discipline.case']
sig = inspect.signature(Case.create)
print(f"\nSignature: {sig}")

# ตรวจสอบ default value
params = sig.parameters
for name, param in params.items():
    if name == 'vals_list':
        if param.default != inspect.Parameter.empty:
            print(f"✅ vals_list มี default: {param.default}")
            print(f"✅ โค้ดใหม่ถูกโหลดแล้ว!")
        else:
            print(f"❌ vals_list ไม่มี default")
            print(f"⚠️  ยังใช้โค้ดเก่าอยู่ - ต้อง restart server")

