# ⚠️ แก้ไขปัญหา: Module "not installable, skipped"

## ปัญหาหลัก

จาก log:
```
WARNING: module onthisday_hr_discipline: not installable, skipped
ERROR: Some modules have inconsistent states: ['onthisday_hr_discipline']
ERROR: Missing model hr.discipline.case, hr.discipline.point.ledger, etc.
```

**สาเหตุ:** Odoo ไม่พบโมดูลใน addons path เพราะใช้ config file ที่ผิด

## วิธีแก้ไข (ทำตามลำดับ)

### ✅ วิธีที่ 1: แก้ไข Config File (แนะนำ - แก้ถาวร)

**ปัญหาคือ Odoo ใช้ `~/.odoorc` แทน `odoo.conf` และใน `~/.odoorc` ไม่มี `addons_path` ที่ชี้ไปยัง `custom_addons`**

#### ขั้นตอน:

1. **แก้ไข `~/.odoorc`:**
```bash
nano ~/.odoorc
```

2. **เพิ่มบรรทัดนี้:**
```ini
[options]
addons_path = /Users/nattaphonsupa/odoo-16/odoo/addons,/Users/nattaphonsupa/odoo-16/addons,/Users/nattaphonsupa/odoo-16/custom_addons
```

3. **หรือใช้ `odoo.conf` แทน:**
   - ใช้ `-c odoo.conf` ทุกครั้งที่รัน Odoo
   - หรือ rename `~/.odoorc` เป็น backup แล้วใช้ `odoo.conf`

4. **Restart Odoo server**

5. **Upgrade module ผ่าน UI:**
   - ไปที่ Apps → ค้นหา "OnThisDay HR Discipline"
   - กด Upgrade

### ✅ วิธีที่ 2: ใช้ Config File ที่ถูกต้อง

เมื่อรัน Odoo server **ต้องใช้ `-c odoo.conf`:**

```bash
python3 odoo-bin -c odoo.conf -d nt_test
```

หรือแก้ไข startup script/alias ให้รวม `-c odoo.conf` เสมอ

### ✅ วิธีที่ 3: ตรวจสอบ Addons Path

รันใน Odoo shell (หลังจากแก้ config):

```python
# ตรวจสอบ addons path
print(env['ir.module.module'].sudo()._get_addons_path())
print(env['ir.module.module'].sudo()._get_modules())

# ตรวจสอบว่า module พบหรือไม่
module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)
if module:
    print(f"Found: {module.name}, State: {module.state}, Installable: {module.state in ['installed', 'to upgrade']}")
else:
    print("Module not found - check addons_path")
```

## หลังจากแก้ไข Config

1. **Restart Odoo Server:**
```bash
# หยุด Odoo server
# แล้วเริ่มใหม่
python3 odoo-bin -c odoo.conf -d nt_test
```

2. **ตรวจสอบ Module:**
   - ไปที่ Apps → ค้นหา "OnThisDay HR Discipline"
   - ควรเห็น module และสามารถ upgrade ได้

3. **Upgrade Module:**
   - Enable Developer Mode (ถ้ายังไม่ได้)
   - ไปที่ Apps → "OnThisDay HR Discipline" → Upgrade

4. **ตรวจสอบว่าสำเร็จ:**
   - Module state ควรเป็น "Installed"
   - Models ควรถูกโหลด (ไม่มี Missing model errors)
   - View errors ควรหาย

## ตรวจสอบว่าแก้ไขสำเร็จ

### 1. ตรวจสอบใน Logs:

หลังจาก restart Odoo ควรเห็น:
```
INFO: loading modules...
INFO: Module onthisday_hr_discipline loaded
```

และ **ไม่ควรเห็น:**
```
WARNING: module onthisday_hr_discipline: not installable, skipped
ERROR: Missing model hr.discipline.case
```

### 2. ตรวจสอบใน UI:

- ไปที่ Apps → "OnThisDay HR Discipline"
- ควรเห็นสถานะ "Installed" ✓
- ไม่มี error messages

### 3. ตรวจสอบ Models:

รันใน Odoo shell:
```python
# ตรวจสอบว่า models ถูกโหลด
models = [
    'hr.discipline.case',
    'hr.discipline.point.ledger',
    'hr.discipline.offense',
    'hr.discipline.action',
]

for model_name in models:
    if model_name in env:
        print(f"✅ {model_name} - Found")
    else:
        print(f"❌ {model_name} - Missing")
```

## สรุป

**ปัญหา:** Odoo ไม่พบ `custom_addons` path  
**แก้ไข:** เพิ่ม `addons_path` ใน config file  
**ผลลัพธ์:** Module จะถูกพบและสามารถ upgrade ได้

---

**หมายเหตุสำคัญ:** หลังจากแก้ config แล้ว **ต้อง restart Odoo server** ก่อน upgrade module

