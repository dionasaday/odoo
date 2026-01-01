# แก้ไข Error: can't access property "relation", models[resModel][fieldName] is undefined

## สาเหตุ

Error นี้เกิดจาก **View XML อ้างอิง field ที่ยังไม่มีใน Odoo model registry** ซึ่งมักเกิดเมื่อ:
1. Module ยังไม่ได้ upgrade/install ทำให้ fields ยังไม่ถูกโหลดเข้า registry
2. View XML อ้างอิง field ที่ไม่มีจริงใน model
3. Typo ในชื่อ field ใน view XML

## วิธีแก้ไข

### วิธีที่ 1: Upgrade Module (แนะนำ - แก้ปัญหาโดยตรง)

```bash
cd /Users/nattaphonsupa/odoo-16
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

### วิธีที่ 2: Restart Odoo และ Clear Browser Cache

1. **Restart Odoo server**
2. **Hard reload browser:**
   - Chrome/Edge: `Ctrl+Shift+R` (Windows/Linux) หรือ `Cmd+Shift+R` (Mac)
   - Firefox: `Ctrl+F5` หรือ `Ctrl+Shift+R`

### วิธีที่ 3: ตรวจสอบและแก้ไข View XML (ถ้ายังไม่ได้)

ถ้ายังมีปัญหา ให้ตรวจสอบว่า fields ที่ view อ้างอิงมีใน model จริง:

#### Fields ที่ view อ้างอิง:
- `calendar_year` - ✅ มีใน `case.py`
- `preview_points_before` - ✅ มีใน `case.py`
- `preview_points_after` - ✅ มีใน `case.py`
- `total_points_before` - ✅ มีใน `case.py`
- `total_points_after` - ✅ มีใน `case.py`
- `action_suggested_id` - ✅ มีใน `case.py`
- `action_taken_id` - ✅ มีใน `case.py`
- `reset_points` - ✅ มีใน `case.py`

**Fields ทั้งหมดมีใน model แล้ว** ดังนั้นปัญหาคือ module ยังไม่ได้ upgrade

## ขั้นตอนการแก้ไขที่แนะนำ

### Step 1: ตรวจสอบ Module State

รันใน Odoo shell:
```python
module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)
print(f"Module State: {module.state}")
print(f"Is Installed: {module.state == 'installed'}")
```

### Step 2: Upgrade Module

```bash
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

### Step 3: Restart Odoo

```bash
# หยุด Odoo server
# แล้วเริ่มใหม่
python3 odoo-bin -c odoo.conf
```

### Step 4: Clear Browser Cache

- Hard reload: `Ctrl+Shift+R` หรือ `Cmd+Shift+R`
- หรือ clear cache ใน browser settings

### Step 5: ตรวจสอบว่า Error หาย

ลองเข้า Odoo UI อีกครั้ง ตรวจสอบว่าไม่มี error

## ถ้ายังมีปัญหา

### ตรวจสอบ View XML ที่อาจมีปัญหา:

1. **case_views.xml** - อ้างอิง `total_points_after`
2. **hr_discipline_case_views.xml** - อ้างอิง `calendar_year`, `preview_points_before`, `preview_points_after`

ถ้ายังมี error หลังจาก upgrade แล้ว ให้ตรวจสอบว่า:

```bash
# ตรวจสอบว่า view XML มี syntax ถูกต้อง
grep -r "field name=" custom_addons/onthisday_hr_discipline/views/*.xml | grep -E "(calendar_year|preview_points|total_points)"

# ตรวจสอบว่า model มี fields เหล่านี้
grep -r "calendar_year\|preview_points\|total_points" custom_addons/onthisday_hr_discipline/models/*.py
```

## หมายเหตุ

- Error นี้จะหายไปหลังจาก upgrade module เพราะ fields จะถูกโหลดเข้า registry
- ไม่ต้องแก้ไข view XML เพราะ fields ทั้งหมดมีใน model อยู่แล้ว
- ปัญหาคือ module state ไม่สอดคล้องกับ code

