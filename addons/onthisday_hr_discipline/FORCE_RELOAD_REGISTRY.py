#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สคริปต์ Force Reload Registry (รันผ่าน Odoo UI หรือ shell)

วิธีใช้:
1. เปิด Odoo UI
2. Enable Developer Mode
3. ไปที่ Settings → Technical → Python Code
4. Copy และ paste โค้ดด้านล่าง
5. Execute
"""

# Force reload registry
env.registry.clear_cache()
env.registry.setup_models(env.cr)

# ตรวจสอบ signature
import inspect
Case = env['hr.discipline.case']
sig = inspect.signature(Case.create)
print(f"Signature after reload: {sig}")

# ตรวจสอบ default value
params = sig.parameters
for name, param in params.items():
    if name == 'vals_list':
        if param.default != inspect.Parameter.empty:
            print(f"✅ vals_list มี default: {param.default}")
        else:
            print(f"❌ vals_list ไม่มี default - ต้อง restart server")

# ลองเรียก create() โดยไม่ส่ง argument
try:
    result = Case.create([])
    print(f"✅ create([]) ทำงานได้")
except TypeError as e:
    print(f"❌ create([]) error: {e}")

