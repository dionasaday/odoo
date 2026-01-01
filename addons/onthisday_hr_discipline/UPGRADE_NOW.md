# ⚠️ ต้อง Upgrade Module ทันที

## ปัญหาปัจจุบัน
Error: **"Missing field string information for the field 'module_l10n_fr_hr_payroll'"**

## สาเหตุ
- Field definitions ใน `res_config_settings_patch.py` ถูกเขียนแล้ว
- แต่ **module ยังไม่ได้ upgrade** → Odoo registry ยังไม่มี field definitions เหล่านี้
- View 3505 อ้างอิง field เหล่านี้แต่ registry ยังไม่มี → Error!

## ✅ สิ่งที่แก้ไขไปแล้ว

1. ✅ เพิ่ม field definitions ใน `res_config_settings_patch.py`
2. ✅ อัปเดต `field_description` ใน database สำหรับ payroll localization fields
3. ✅ แก้ไข view 3505 ให้มี XML ที่ถูกต้อง

## 🔧 วิธี Upgrade Module

### วิธีที่ 1: Upgrade ผ่าน UI (แนะนำ)

1. เปิด browser → เข้า Odoo
2. กด **F12** (เปิด Developer Tools) → ดู Console tab
3. Settings → Activate Developer Mode (ถ้ายังไม่ได้เปิด)
4. Apps → ค้นหา **"OnThisDay HR Discipline"**
5. กด **"Upgrade"** button
6. รอให้ upgrade เสร็จ
7. **Hard Reload** browser (Ctrl+Shift+R หรือ Cmd+Shift+R)

### วิธีที่ 2: Upgrade ผ่าน Command Line

```bash
cd /Users/nattaphonsupa/odoo-16
python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init
```

### วิธีที่ 3: Upgrade ผ่าน Odoo Shell (ถ้า Odoo กำลังรันอยู่)

1. เข้า Odoo
2. Settings → Activate Developer Mode
3. ไปที่ menu: **Settings → Technical → Database Structure → Modules**
4. ค้นหา **"onthisday_hr_discipline"**
5. กด **"Upgrade"**

## 📋 หลัง Upgrade

1. **Restart Odoo Server** (ถ้ายังไม่ได้ restart)
2. **Hard Reload Browser** (Ctrl+Shift+R หรือ Cmd+Shift+R)
3. ทดสอบเข้าหน้า Settings → ไม่ควรมี error แล้ว

## ⚠️ สำคัญ

**Module ต้อง upgrade ก่อน** field definitions จะถูกโหลดเข้า Odoo registry!

ดูเหมือนว่า:
- Field definitions ✅ พร้อมแล้ว
- Database records ✅ อัปเดตแล้ว  
- Views ✅ แก้ไขแล้ว
- **Module Upgrade** ❌ ยังไม่ได้ทำ ← **ต้องทำตอนนี้!**

