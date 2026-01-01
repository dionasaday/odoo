# แก้ปัญหา Employee และ Contract

## สถานะปัจจุบัน

✅ **Settings**: เข้าได้แล้ว  
❌ **Employee**: เข้าไม่ได้ (error `can't access property "relation"`)  
❌ **Contract**: เข้าไม่ได้ (error `can't access property "relation"`)

## สิ่งที่ตรวจสอบแล้ว

✅ **Fields ใน hr.employee**: มี metadata ครบแล้ว
- `category_ids`: OK
- `message_partner_ids`: OK  
- `related_contact_ids`: OK
- `kpi_missing_subordinate_ids`: OK

✅ **Fields ใน hr.contract**: มี metadata ครบแล้ว
- `message_partner_ids`: OK

## สาเหตุที่เป็นไปได้

1. **Browser cache** - ยังใช้ JavaScript bundle เก่า
2. **Odoo client cache** - client-side cache ยังมี field definitions เก่า
3. **View ใช้ field ที่ client ไม่ได้รับ** - view อาจอ้างอิง field ที่ fields_get ไม่ return มา

## 🔴 ขั้นตอนแก้ไข

### 1. Clear Browser Cache แบบเต็มรูปแบบ

#### วิธีที่ 1: Empty Cache and Hard Reload (แนะนำ)
1. กด **F12** เปิด Developer Tools
2. คลิกขวาที่ **Reload button** (⟳)
3. เลือก **"Empty Cache and Hard Reload"**

#### วิธีที่ 2: Clear Cache ผ่าน Settings
1. **Ctrl+Shift+Delete** (Windows/Linux) หรือ **Cmd+Shift+Delete** (Mac)
2. เลือก **"Cached images and files"**
3. เลือก **"All time"**
4. กด **"Clear data"**

#### วิธีที่ 3: Incognito Window
- เปิด **Incognito/Private window** (Ctrl+Shift+N หรือ Cmd+Shift+N)
- เข้า Odoo ใหม่

### 2. Hard Reload

- **Ctrl+Shift+R** (Windows/Linux) หรือ **Cmd+Shift+R** (Mac)
- หรือ **F5** หลายครั้ง

### 3. Restart Odoo Server (ถ้ายังไม่ได้ทำ)

```bash
# หยุด Odoo server (Ctrl+C)
# แล้วเริ่มใหม่:
cd /Users/nattaphonsupa/odoo-16
./venv/bin/python3 odoo-bin -d nt --addons-path=./odoo/addons,./addons,./custom_addons
```

### 4. ทดสอบ

- เข้าหน้า **Employee** → ตรวจสอบ error
- เข้าหน้า **Contract** → ตรวจสอบ error

## ถ้ายังมี Error

ถ้ายังมี error หลังจาก clear cache:

1. **ตรวจสอบ Browser Console** (F12 → Console):
   - ดู error message ที่ชัดเจนขึ้น
   - ดู field ไหนที่ทำให้เกิด error

2. **ตรวจสอบ Network tab**:
   - ดู fields_get request สำเร็จหรือไม่
   - ดู response มี field definitions หรือไม่

3. **ตรวจสอบ Odoo log**:
   - ดูว่ามี error เมื่อ load fields หรือไม่

## สรุป

✅ **Fields metadata ครบแล้ว**  
⚠️ **ต้อง Clear Browser Cache แบบเต็มรูปแบบ**  
⚠️ **อาจต้อง Restart Odoo Server**

**Clear browser cache แล้วทดสอบอีกครั้ง!**

