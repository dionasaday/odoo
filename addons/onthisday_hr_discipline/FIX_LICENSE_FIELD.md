# แก้ปัญหา Missing field string information สำหรับ license_report_user_ids

## ปัญหา
Error: Missing field string information for the field 'license_report_user_ids' from the 'res.config.settings' model

## สาเหตุ
- Field `license_report_user_ids` มาจากโมดูล `onthisday_lot_license_v107` ที่ถูก disable แล้ว
- Field ยังอยู่ใน database แต่ไม่มี string attribute ที่ Odoo frontend สามารถอ่านได้
- โมดูล `onthisday_hr_discipline` ยังไม่ได้ upgrade เพื่อโหลด patch module

## วิธีแก้ไข

### 1. Upgrade Module (จำเป็น)
```bash
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

หรือผ่าน UI:
- ไปที่ Apps
- ค้นหา "OnThisDay HR Discipline"
- กด "Upgrade"

### 2. Restart Odoo Server
หลังจาก upgrade แล้ว ให้ restart Odoo server

### 3. Hard Reload Browser
- Windows/Linux: `Ctrl + Shift + R`
- Mac: `Cmd + Shift + R`

### 4. ถ้ายังไม่ได้ (Manual Fix)
ถ้ายังมี error อยู่ ให้รัน SQL นี้เพื่ออัปเดต field description:

```sql
UPDATE ir_model_fields 
SET field_description = '{"en_US": "License Report Recipients"}'::jsonb 
WHERE model = 'res.config.settings' 
AND name = 'license_report_user_ids';
```

## สิ่งที่ทำไปแล้ว
✅ สร้าง patch module (`res_config_settings_patch.py`) ที่เพิ่ม field พร้อม string
✅ Field มีอยู่ใน database แล้ว
✅ โมดูลอยู่ในสถานะ "to upgrade"

## สิ่งที่ต้องทำ
⚠️ **Upgrade module `onthisday_hr_discipline`** เพื่อให้ patch module ถูกโหลด

