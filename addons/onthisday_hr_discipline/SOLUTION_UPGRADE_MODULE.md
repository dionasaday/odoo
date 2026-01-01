# 🔧 วิธีแก้ไข Error: ต้อง Upgrade Module ผ่าน UI

## ปัญหา

Error `TypeError: create() missing 1 required positional argument: 'vals_list'` ยังเกิดขึ้นอยู่ แม้ว่าโค้ดจะแก้ไขแล้ว

## สาเหตุ

**Odoo registry ยังไม่ได้ reload** จึงยังใช้โค้ดเก่าที่มี signature ผิด

## ✅ วิธีแก้ไข (ทำตามขั้นตอนนี้)

### วิธีที่ 1: Upgrade Module ผ่าน UI (แนะนำ)

1. **เปิด Odoo UI** (http://localhost:8069)
2. **Enable Developer Mode**
   - ไปที่ **Settings**
   - กด **"Activate the developer mode"** ที่มุมล่างซ้าย
   - หรือเพิ่ม `?debug=1` ใน URL

3. **ไปที่ Apps**
   - เมนู **Apps** → **Apps**

4. **ค้นหาและ Upgrade Module**
   - ค้นหา: **"OnThisDay HR Discipline"**
   - กด **Upgrade** (ถ้ามี)
   - หรือ **Install** (ถ้ายังไม่ได้ install)

5. **รอให้ Upgrade เสร็จ**
   - ควรเห็น "The following modules have been upgraded: onthisday_hr_discipline"

6. **Hard Reload Browser**
   - `Ctrl+Shift+R` (Windows/Linux)
   - `Cmd+Shift+R` (Mac)

7. **ทดสอบ**
   - สร้าง Discipline Case → ควรบันทึกได้ ✓
   - ลงเวลา (Attendance) → ควรบันทึกได้ ✓

### วิธีที่ 2: Force Reload Registry (ผ่าน Python Code)

1. **เปิด Odoo UI** → **Enable Developer Mode**

2. **ไปที่ Settings → Technical → Python Code**

3. **Copy โค้ดนี้ไป paste:**

```python
# Force reload registry
env.registry.clear_cache()
env.registry.setup_models(env.cr)

# ตรวจสอบ signature
import inspect
Case = env['hr.discipline.case']
sig = inspect.signature(Case.create)
print(f"Signature: {sig}")

# ตรวจสอบ default value
params = sig.parameters
for name, param in params.items():
    if name == 'vals_list':
        if param.default != inspect.Parameter.empty:
            print(f"✅ vals_list มี default: {param.default}")
        else:
            print(f"❌ vals_list ไม่มี default")
```

4. **Execute** (รันโค้ด)

5. **Hard Reload Browser**

6. **ทดสอบ**

### วิธีที่ 3: Restart Odoo Server (ถ้า Upgrade ไม่ได้)

1. **หยุด Odoo server** (Ctrl+C หรือ Cmd+C)

2. **Clear Python cache:**
   ```bash
   find custom_addons/onthisday_hr_discipline -name "*.pyc" -delete
   find custom_addons/onthisday_hr_discipline -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
   ```

3. **เริ่ม Odoo server ใหม่:**
   ```bash
   cd /Users/nattaphonsupa/odoo-16
   python3 odoo-bin -c odoo.conf -d nt_test
   ```

4. **Hard Reload Browser**

5. **ทดสอบ**

## ตรวจสอบว่าแก้ไขสำเร็จ

### ตรวจสอบใน UI:

1. **สร้าง Discipline Case:**
   - วินัยและบทลงโทษ > กรณีความผิด
   - Create → กรอกข้อมูล → Save
   - **ควรบันทึกได้โดยไม่มี error** ✓

2. **ลงเวลา (Attendance):**
   - Attendance → Check In/Check Out
   - **ควรบันทึกได้โดยไม่มี error** ✓

### ตรวจสอบ Signature (ใน Python Code):

รันโค้ดนี้ใน Settings → Technical → Python Code:

```python
import inspect
Case = env['hr.discipline.case']
sig = inspect.signature(Case.create)
print(f"Signature: {sig}")

# ควรเห็น: (self, vals_list=None)
```

## ถ้ายังไม่ได้

### ตรวจสอบว่าโค้ดถูกแก้ไขจริง:

```bash
grep "def create(" custom_addons/onthisday_hr_discipline/models/case.py
```

**ควรเห็น:**
```
    def create(self, vals_list=None):
```

### ถ้ายังเห็น: `def create(self, vals_list):` (ไม่มี =None)

แสดงว่าโค้ดยังไม่ได้แก้ไข → แจ้งให้ทราบ

## สรุป

**โค้ดแก้ไขแล้ว:** ✅ (`vals_list=None`)  
**ต้องทำ:** ⚠️ **Upgrade Module ผ่าน UI** หรือ **Restart Server**

**หลังจาก Upgrade/Restart:**
- Error ควรหายไป 100% ✓
- สามารถบันทึก Discipline Case ได้ ✓
- สามารถลงเวลาได้ ✓

---

**หมายเหตุ:** Upgrade Module จะ trigger reload registry และทำให้โค้ดใหม่ถูกโหลด

