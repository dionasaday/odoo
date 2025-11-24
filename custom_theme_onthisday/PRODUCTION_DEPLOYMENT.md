# คู่มือการ Deploy Custom Theme ใน Production

## ปัญหาที่พบ

โมดูล `custom_theme_onthisday` ติดตั้งใน production แล้ว แต่สี theme ไม่เปลี่ยน

## สาเหตุที่เป็นไปได้

1. **Asset Bundle Cache**: Odoo cache asset bundles ใน production เพื่อเพิ่มประสิทธิภาพ
2. **Module Not Upgraded**: โมดูลติดตั้งแล้วแต่ไม่ได้ upgrade ทำให้ asset ไม่ถูก compile ใหม่
3. **Browser Cache**: Browser cache ไฟล์ CSS เก่าไว้
4. **SCSS Not Compiled**: ไฟล์ SCSS ไม่ถูก compile เป็น CSS
5. **Asset Loading Order**: Assets ไม่ถูกโหลดในลำดับที่ถูกต้อง

## วิธีแก้ไข (Step by Step)

### ขั้นตอนที่ 1: ตรวจสอบว่าโมดูลถูกติดตั้งแล้ว

```bash
# เข้าสู่ระบบ Odoo
# ไปที่ Apps > ค้นหา "Custom Theme - On This Day"
# ตรวจสอบว่า state = "Installed"
```

### ขั้นตอนที่ 2: Upgrade โมดูล

**สำคัญ:** ใน Production ควรใช้ upgrade แทนการติดตั้งใหม่

```bash
# วิธีที่ 1: ผ่าน Command Line (แนะนำ)
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# ตัวอย่าง
odoo-bin -u custom_theme_onthisday -d odoo19_prod --stop-after-init

# วิธีที่ 2: ผ่าน Odoo Interface
# 1. ไปที่ Apps
# 2. ค้นหา "Custom Theme - On This Day"
# 3. คลิก "Upgrade" (ถ้ามี)
```

### ขั้นตอนที่ 3: Restart Odoo Service

```bash
# Docker
docker-compose restart odoo

# Systemd
sudo systemctl restart odoo

# Manual (ถ้า run เอง)
# หยุด process Odoo และรันใหม่
```

### ขั้นตอนที่ 4: Clear Asset Cache

#### 4.1 Clear Browser Cache

- **Windows/Linux**: กด `Ctrl+Shift+R` หรือ `Ctrl+F5`
- **Mac**: กด `Cmd+Shift+R`
- **Hard Refresh**: กด `Ctrl+Shift+Delete` (Windows) หรือ `Cmd+Shift+Delete` (Mac) แล้วเลือก "Clear cached images and files"

#### 4.2 Clear Asset Bundle ใน Odoo (ถ้ามี)

1. ไปที่ **Settings**
2. เปิด **Developer Mode** (ถ้ายังไม่เปิด)
3. ไปที่ **Technical > Assets > Clear Assets Cache**
4. หรือใช้คำสั่ง:
   ```bash
   # ใน Odoo shell
   odoo-bin shell -d <database_name>
   >>> env['ir.attachment'].search([('name', 'like', 'web.assets')]).unlink()
   ```

### ขั้นตอนที่ 5: ตรวจสอบว่าไฟล์ CSS ถูกโหลด

1. เปิด Browser DevTools (กด `F12`)
2. ไปที่ tab **Network**
3. Reload หน้าเว็บ (กด `Ctrl+R` หรือ `F5`)
4. ค้นหาไฟล์ CSS ที่มีคำว่า "custom_theme" หรือ "assets_backend"
5. ตรวจสอบว่า:
   - ไฟล์ถูกโหลด (Status = 200)
   - ไฟล์มีเนื้อหาที่ถูกต้อง (คลิกดู Response)
   - ไฟล์มี CSS rules ที่เราเขียนไว้

### ขั้นตอนที่ 6: ตรวจสอบ CSS Specificity

1. เปิด Browser DevTools (กด `F12`)
2. ไปที่ tab **Elements** หรือ **Inspector**
3. Inspect element ที่สีไม่เปลี่ยน (เช่น Navigation Bar)
4. ดูว่า CSS rule ไหนถูก apply
5. ตรวจสอบว่า CSS ของเรา override CSS ของ Odoo หรือไม่
6. ถ้าไม่ override:
   - เพิ่ม `!important` ใน SCSS file
   - เพิ่ม CSS specificity
   - ตรวจสอบว่า CSS rule ถูกเขียนถูกต้อง

## Checklist สำหรับ Production Deployment

- [ ] โมดูลถูกติดตั้งแล้ว (state = "Installed")
- [ ] Upgrade โมดูล: `odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init`
- [ ] Restart Odoo service
- [ ] Clear browser cache (Ctrl+Shift+R)
- [ ] ตรวจสอบว่าไฟล์ CSS ถูกโหลดใน Browser DevTools
- [ ] ตรวจสอบว่า CSS rules ถูก apply กับ elements
- [ ] ทดสอบในหลายๆ หน้า (Home, Apps, Settings, etc.)
- [ ] ทดสอบในหลายๆ browser (Chrome, Firefox, Safari)

## คำสั่งที่ใช้บ่อย

```bash
# 1. Upgrade โมดูล
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# 2. Restart Odoo (Docker)
docker-compose restart odoo

# 3. ดู Odoo logs
docker-compose logs -f odoo
# หรือ
tail -f /var/log/odoo/odoo.log

# 4. ตรวจสอบว่าโมดูลถูก load
odoo-bin shell -d <database_name>
>>> env['ir.module.module'].search([('name', '=', 'custom_theme_onthisday')]).state
```

## ถ้ายังแก้ไม่ได้

### ตรวจสอบ Log

```bash
# ดู Odoo log
tail -f /var/log/odoo/odoo.log | grep -i "custom_theme\|error\|scss"

# หรือ
docker-compose logs -f odoo | grep -i "custom_theme\|error\|scss"
```

### ตรวจสอบว่าไฟล์ SCSS ถูก compile

1. เปิด Browser DevTools
2. ไปที่ tab Network
3. Reload หน้าเว็บ
4. ค้นหาไฟล์ CSS
5. ตรวจสอบว่าไฟล์ CSS มีเนื้อหาจากไฟล์ SCSS ของเรา

### ตรวจสอบ Asset Bundle

```bash
# ใน Odoo shell
odoo-bin shell -d <database_name>
>>> env['ir.attachment'].search([('name', 'like', 'web.assets_backend')])
```

### เพิ่ม Version Number

ถ้ายังไม่ได้ผล ให้เพิ่ม version number ใน `__manifest__.py` เพื่อบังคับให้ asset bundle ถูกสร้างใหม่:

```python
'version': '19.0.1.0.2',  # เพิ่ม version
```

แล้ว upgrade โมดูลอีกครั้ง

## สรุป

ปัญหาสีไม่เปลี่ยนใน Production มักเกิดจาก:
1. Asset bundle cache
2. Module ไม่ได้ upgrade
3. Browser cache

วิธีแก้:
1. Upgrade โมดูล: `odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init`
2. Restart Odoo
3. Clear browser cache
4. ตรวจสอบว่าไฟล์ CSS ถูกโหลด

