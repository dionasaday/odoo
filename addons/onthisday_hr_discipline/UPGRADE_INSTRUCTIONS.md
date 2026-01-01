# คำแนะนำการ Upgrade Module onthisday_hr_discipline

## ปัญหา
```
ERROR: Some modules have inconsistent states, some dependencies may be missing: ['onthisday_hr_discipline']
```

## สาเหตุ
โมดูลอยู่ในสถานะ "to upgrade" เพราะมีการเปลี่ยนแปลงใน:
- Models (เช่น `res_config_settings_patch.py`)
- Views (เช่น `res_config_settings_patch_view.xml`)
- Data files (เช่น `cron_lateness_monthly_summary.xml`)

## วิธีแก้ไข

### วิธีที่ 1: ใช้ Script (แนะนำ)
```bash
cd /Users/nattaphonsupa/odoo-16
./custom_addons/onthisday_hr_discipline/upgrade_module.sh
```

### วิธีที่ 2: ใช้ Command Line โดยตรง
```bash
cd /Users/nattaphonsupa/odoo-16
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

### วิธีที่ 3: ผ่าน Odoo UI
1. เปิด browser → เข้า Odoo
2. Enable Developer Mode (ถ้ายังไม่ได้ enable)
   - Settings → Activate Developer Mode
3. ไปที่ Apps
4. ค้นหา "OnThisDay HR Discipline"
5. กดปุ่ม "Upgrade"

## หลังจาก Upgrade

1. **Restart Odoo Server** (ถ้ายังไม่ได้ restart)
2. **Hard Reload Browser:**
   - Windows/Linux: `Ctrl + Shift + R`
   - Mac: `Cmd + Shift + R`
3. **ตรวจสอบ Log** ว่าไม่มี error
4. **ตรวจสอบว่า Field Definitions ถูกโหลด:**
   - Settings → Technical → Database Structure → Models
   - ค้นหา `res.config.settings`
   - ตรวจสอบว่า field `license_report_user_ids` มี String attribute

## สิ่งที่ Upgrade จะทำ

1. ✅ โหลด model definitions ใหม่ (เช่น `res_config_settings_patch.py`)
2. ✅ โหลด views ใหม่ (เช่น `res_config_settings_patch_view.xml`)
3. ✅ สร้าง/อัปเดต cron jobs
4. ✅ รัน `post_init_hook` เพื่อลบ asset records ที่ไม่ต้องการ
5. ✅ อัปเดต field descriptions ใน database

## Troubleshooting

### ถ้า Upgrade ไม่ได้
```sql
-- ตรวจสอบ state ของโมดูล
SELECT name, state, latest_version FROM ir_module_module 
WHERE name = 'onthisday_hr_discipline';

-- Force state เป็น installed (ใช้เมื่อ upgrade ไม่ได้ - ไม่แนะนำ)
UPDATE ir_module_module 
SET state = 'installed' 
WHERE name = 'onthisday_hr_discipline';
```

### ถ้ายังมี Error
- ตรวจสอบ dependencies ครบหรือไม่
- ตรวจสอบ log ว่าไม่มี syntax errors ใน Python files
- Restart Odoo server ใหม่

## หมายเหตุ

⚠️ **Important:** ต้อง upgrade module เพื่อให้ field definitions ใหม่ถูกโหลดและแก้ error "Missing field string information" ได้อย่างสมบูรณ์

