# ✅ Odoo Server ได้ Restart แล้ว

## สิ่งที่ทำแล้ว

1. ✅ **Clear port 8069** (ถ้ามี process เก่าค้างอยู่)
2. ✅ **เริ่ม Odoo server ใหม่** ใน background mode
   ```bash
   python3 odoo-bin -c odoo.conf -d nt_test
   ```

## ขั้นตอนต่อไป

### 1. รอให้ Server เริ่มทำงาน (ประมาณ 10-30 วินาที)

**ตรวจสอบว่า server เริ่มแล้ว:**
- เปิด browser ไปที่: http://localhost:8069
- ควรเห็นหน้า Odoo login page

**หรือตรวจสอบ logs:**
- ดูที่ terminal ที่รัน Odoo
- ควรเห็น: `INFO ... odoo.service.server: HTTP service (werkzeug) running on ...`

### 2. Hard Reload Browser

**สำคัญมาก:** ต้อง clear browser cache

- **Chrome/Edge:** `Ctrl+Shift+R` (Windows) หรือ `Cmd+Shift+R` (Mac)
- **Firefox:** `Ctrl+F5` หรือ `Ctrl+Shift+R`

**หรือ Clear cache แบบเต็ม:**
1. ไปที่ Browser Settings → Privacy → Clear browsing data
2. เลือก "Cached images and files"
3. Clear data

### 3. ทดสอบการแก้ไข

#### Test 1: สร้าง Discipline Case

1. **เปิด Odoo** → Login
2. ไปที่ **วินัยและบทลงโทษ > กรณีความผิด**
3. กด **Create** (สร้างใหม่)
4. กรอกข้อมูล:
   - Employee: เลือกพนักงาน
   - Date: ระบุวันที่
   - Offense: เลือกประเภทความผิด
5. กด **Save** (บันทึก)
6. **ควรบันทึกได้โดยไม่มี error** ✓

#### Test 2: ลงเวลา (Attendance)

1. ไปที่ **Attendance**
2. กด **Check In** หรือ **Check Out**
3. **ควรบันทึกได้โดยไม่มี error** ✓

## ตรวจสอบว่าแก้ไขสำเร็จ

### ตรวจสอบ Signature (ใน Odoo shell):

```bash
python3 odoo-bin shell -d nt_test
```

แล้วรัน:
```python
import inspect
Case = env['hr.discipline.case']
sig = inspect.signature(Case.create)
print(f"Signature: {sig}")

# ควรเห็น: (self, vals_list=None)
```

### ตรวจสอบใน Logs:

หลัง restart แล้วลอง save อีกครั้ง - **ไม่ควรเห็น error:**
```
TypeError: create() missing 1 required positional argument: 'vals_list'
```

## ถ้ายังมีปัญหา

### ตรวจสอบว่า Server Restart สำเร็จ:

```bash
# ตรวจสอบ process
ps aux | grep odoo-bin | grep -v grep

# ตรวจสอบ port
lsof -i:8069
```

### ถ้า Server ไม่ทำงาน:

1. **ตรวจสอบ logs** ใน terminal ที่รัน Odoo
2. **ตรวจสอบว่า database ชื่อถูกต้อง** (`nt_test`)
3. **ตรวจสอบ config file** (`odoo.conf`)

### ถ้า Error ยังเกิดขึ้น:

1. **ตรวจสอบว่าโค้ดถูกแก้ไขจริง:**
   ```bash
   grep "def create(" custom_addons/onthisday_hr_discipline/models/case.py
   ```
   ควรเห็น: `def create(self, vals_list=None):`

2. **Force reload registry** (ใน Odoo shell):
   ```python
   env.registry.clear_cache()
   env.registry.setup_models(env.cr)
   ```

3. **Upgrade module อีกครั้ง:**
   - Apps → "OnThisDay HR Discipline" → Upgrade

## สรุป

**Server ได้ restart แล้ว** ✅  
**Hard reload browser** - ต้องทำด้วยตัวเอง  
**ทดสอบ** - ควรทำงานได้แล้ว

---

**หมายเหตุ:** Server กำลังรันใน background mode ถ้าต้องการดู logs ให้ไปดูที่ terminal หรือรัน Odoo ใน foreground mode:
```bash
python3 odoo-bin -c odoo.conf -d nt_test
```

