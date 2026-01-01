# แก้ไขปัญหาสคริปต์ทดสอบ

## ปัญหาที่พบ

เมื่อรันสคริปต์ทดสอบพบ error:
```
AttributeError: 'res.company' object has no attribute 'hr_lateness_grace'
```

## สาเหตุ

1. **โมดูลยังไม่ได้ถูกโหลด:** จาก log เห็นว่า `onthisday_hr_discipline` ยังไม่ได้ถูกโหลด:
   ```
   Some modules are not loaded: ['onthisday_hr_discipline']
   ```

2. **Fields ยังไม่มีใน database:** เพราะโมดูลยังไม่ได้ upgrade ทำให้ fields จาก `res_company.py` และ `lateness_rule.py` ยังไม่ได้ถูกเพิ่มเข้า database

## วิธีแก้ไข

### 1. Upgrade Module (จำเป็น)

รันคำสั่งนี้เพื่อ upgrade module และเพิ่ม fields เข้า database:

```bash
cd /Users/nattaphonsupa/odoo-16
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

หรือ upgrade ผ่าน UI:
1. เปิด Odoo → Settings
2. Enable Developer Mode
3. ไปที่ Apps → ค้นหา "OnThisDay HR Discipline"
4. กด Upgrade

### 2. แก้ไขสคริปต์ (ทำแล้ว)

สคริปต์ได้ถูกแก้ไขให้ใช้ `getattr()` เพื่อรองรับกรณีที่ fields ยังไม่มี:

```python
# เดิม (จะ error ถ้า field ยังไม่มี)
grace_minutes = company.hr_lateness_grace or 5

# แก้ไขแล้ว (ปลอดภัย)
grace_minutes = getattr(company, 'hr_lateness_grace', None) or 5
```

## ขั้นตอนการทดสอบใหม่

### Step 1: Upgrade Module
```bash
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

### Step 2: รันสคริปต์ทดสอบ
```bash
python3 odoo-bin shell -d nt < custom_addons/onthisday_hr_discipline/quick_test_lateness.py
```

### Step 3: ตรวจสอบผลลัพธ์

ตรวจสอบใน Odoo UI:
- วินัยและบทลงโทษ > Lateness Logs
- วินัยและบทลงโทษ > กรณีความผิด

## การตรวจสอบว่า Module ถูกโหลดแล้วหรือยัง

รันใน Odoo shell:
```python
module = env['ir.module.module'].sudo().search([('name', '=', 'onthisday_hr_discipline')], limit=1)
print(f"State: {module.state}")
print(f"Installed: {module.state == 'installed'}")

# ตรวจสอบ fields
company = env.company
print(f"Has hr_lateness_grace: {hasattr(company, 'hr_lateness_grace')}")
if hasattr(company, 'hr_lateness_grace'):
    print(f"Value: {company.hr_lateness_grace}")
```

ถ้า `state != 'installed'` แสดงว่าต้อง upgrade module ก่อน

## หมายเหตุ

- สคริปต์ที่แก้ไขแล้วจะทำงานได้แม้ module ยังไม่ได้ upgrade แต่จะใช้ค่า default แทน
- แนะนำให้ upgrade module ก่อนเพื่อให้ได้ผลการทดสอบที่ถูกต้อง
- หลัง upgrade แล้ว fields จะถูกเพิ่มเข้า database และสคริปต์จะทำงานได้ปกติ

