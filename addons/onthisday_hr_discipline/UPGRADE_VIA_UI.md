# วิธี Upgrade Module ผ่าน UI

## ⚠️ หมายเหตุ
เนื่องจาก command line upgrade มีปัญหาเรื่อง dependencies ให้ upgrade ผ่าน UI แทน

## ขั้นตอนการ Upgrade ผ่าน UI

### 1. เปิด Browser และเข้า Odoo
- URL: `http://localhost:8069`
- Login เข้าสู่ระบบ

### 2. Enable Developer Mode (ถ้ายังไม่ได้ enable)
- ไปที่ **Settings** (⚙️)
- Scroll ลงไปหา **Activate the developer mode** 
- กดปุ่มเพื่อ activate

### 3. Upgrade Module
- ไปที่ **Apps** menu
- ค้นหา **"OnThisDay HR Discipline"** 
- จะเห็น module พร้อมปุ่ม **"Upgrade"** (ถ้าโมดูลอยู่ในสถานะ "to upgrade")
- กดปุ่ม **"Upgrade"**

### 4. รอให้ Upgrade เสร็จ
- Odoo จะแสดง progress bar
- รอจนกว่า upgrade จะเสร็จ (อาจใช้เวลาสักครู่)

### 5. Restart Odoo Server
- หยุด Odoo server (Ctrl+C หรือ kill process)
- เริ่ม Odoo server ใหม่

### 6. Hard Reload Browser
- กด **Ctrl+Shift+R** (Windows/Linux) หรือ **Cmd+Shift+R** (Mac)
- หรือปิดและเปิด browser ใหม่

## สิ่งที่จะเกิดขึ้นหลัง Upgrade

✅ Field definitions ใหม่ถูกโหลด:
- `license_report_user_ids`
- `module_knowsystem_website`
- `helpdesk_mgmt_portal_*` fields
- `fiscalyear_*` fields
- `anglo_saxon_accounting`

✅ Views ใหม่ถูกโหลด:
- `res_config_settings_patch_view.xml`

✅ `post_init_hook` ทำงาน:
- ลบ asset records จาก `om_account_asset`

✅ Cron jobs ใหม่ถูกสร้าง:
- `ir_cron_lateness_monthly_summary`

## ตรวจสอบผลลัพธ์

หลังจาก upgrade แล้ว ให้ตรวจสอบ:
1. Error "Missing field string information" ควรหายไป
2. Settings → Technical → Database Structure → Models
   - ตรวจสอบ `res.config.settings` 
   - ดูว่า field `license_report_user_ids` มี String attribute
3. Settings → Technical → Automation → Scheduled Actions
   - ตรวจสอบว่า cron "Lateness Monthly Summary" ถูกสร้างแล้ว

## Troubleshooting

### ถ้าไม่เห็นปุ่ม Upgrade
- ตรวจสอบว่าโมดูลอยู่ในสถานะ "to upgrade" หรือไม่
- ลอง **Update Apps List** ก่อน (Settings → Apps → Update Apps List)

### ถ้ายังมี Error
- ตรวจสอบ log ของ Odoo server
- ตรวจสอบว่าโมดูล dependencies ครบหรือไม่
- Restart Odoo server อีกครั้ง

## Alternative: Force Upgrade via SQL (ไม่แนะนำ)

ถ้า upgrade ผ่าน UI ไม่ได้ สามารถ force state ได้:
```sql
UPDATE ir_module_module 
SET state = 'installed', 
    latest_version = '16.0.1.0.5'
WHERE name = 'onthisday_hr_discipline';
```

⚠️ **หมายเหตุ:** วิธีนี้ไม่แนะนำเพราะจะไม่โหลด field definitions ใหม่ ควรใช้ UI upgrade ดีกว่า

