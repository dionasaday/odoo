# Custom Theme Module - On This Day

โมดูลสำหรับปรับแต่งสีธีมของ Odoo 19 ให้ตรงกับ Corporate Identity (CI) ของบริษัท On This Day

## การติดตั้ง

1. วางโมดูลในโฟลเดอร์ `addons/`
2. Update Apps List ใน Odoo
3. ติดตั้งโมดูล "Custom Theme - On This Day"

## การใช้งาน

### วิธีที่ 1: ปรับแต่งสีผ่าน Settings (แนะนำ - ง่ายที่สุด) ⭐

1. ไปที่ **Settings** > **General Settings**
2. เลื่อนลงไปหา section **"Theme Colors"**
3. แก้ไขสี:
   - **Primary Color**: สีหลักที่ใช้ใน Navigation Bar, Buttons (เช่น #232222)
   - **Secondary Color**: สีรองที่ใช้ใน hover states (เช่น #623412)
   - **Text Color**: สีข้อความบนพื้นหลังสีหลัก (เช่น #FFFFFF)
4. คลิก **Save**
5. **Refresh browser** (Ctrl+Shift+R หรือ Cmd+Shift+R) เพื่อดูการเปลี่ยนแปลงทันที

> **หมายเหตุ**: สีจะถูกบันทึกใน company settings และใช้กับผู้ใช้ทั้งหมดของบริษัทนั้น

### วิธีที่ 2: แก้ไขสีใน SCSS File

1. เปิดไฟล์ `static/src/scss/custom_theme.scss`
2. แก้ไขค่าสีในส่วน `:root` variables:
   ```scss
   :root {
       --o-brand-primary: #YOUR_COLOR_HERE; /* เปลี่ยนเป็นสีของบริษัท */
   }
   ```
3. Upgrade โมดูล:
   ```bash
   odoo-bin -u custom_theme_onthisday -d <database_name>
   ```
4. Restart Odoo และ Clear Browser Cache (Ctrl+Shift+R)

> **หมายเหตุ**: สีจาก SCSS จะเป็นค่า default แต่จะถูก override โดยค่าจาก Settings

### วิธีหา Hex Code ของสี

1. ใช้เครื่องมือ online color picker (เช่น https://imagecolorpicker.com/)
2. อัปโหลดโลโก้ของบริษัท
3. เลือกสีหลัก
4. คัดลอก Hex Code (เช่น #232222)
5. วางใน Settings > General Settings > Theme Colors

## ตัวอย่างสี

- **สีม่วง (Default)**: `#875A7B`
- **สีน้ำเงิน**: `#0077BE` หรือ `#0066CC`
- **สีเขียว**: `#00A859` หรือ `#28A745`
- **สีส้ม**: `#FF6B35` หรือ `#FF5733`
- **สีแดง**: `#DC3545` หรือ `#E74C3C`
- **สีเทา**: `#6C757D` หรือ `#495057`

## สิ่งที่ถูกเปลี่ยนสี

- Navigation Bar (แถบเมนูด้านบน)
- Buttons (ปุ่มต่างๆ)
- Links (ลิงก์)
- Active States (สถานะที่เลือก)
- Kanban Cards
- Form Views
- List Views
- Search View
- Badges & Labels
- Progress Bars
- Tabs
- และ UI Elements อื่นๆ

## การติดตั้งใน Production

### ขั้นตอนการติดตั้ง

1. **วางโมดูลในโฟลเดอร์ addons**
   ```bash
   # ตรวจสอบว่าโมดูลอยู่ในโฟลเดอร์ addons
   ls -la addons/custom_theme_onthisday
   ```

2. **Update Apps List**
   - เข้าสู่ระบบ Odoo
   - ไปที่ Apps > Update Apps List

3. **ติดตั้งหรือ Upgrade โมดูล**
   ```bash
   # วิธีที่ 1: ผ่าน Odoo Interface
   - ไปที่ Apps
   - ค้นหา "Custom Theme - On This Day"
   - คลิก Install หรือ Upgrade
   
   # วิธีที่ 2: ผ่าน Command Line (แนะนำสำหรับ Production)
   odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init
   ```

4. **Restart Odoo Service**
   ```bash
   # Docker
   docker-compose restart odoo
   
   # Systemd
   sudo systemctl restart odoo
   
   # Manual
   # หยุด Odoo และรันใหม่
   ```

5. **Clear Asset Cache**
   - Clear Browser Cache: `Ctrl+Shift+R` (Windows/Linux) หรือ `Cmd+Shift+R` (Mac)
   - หรือ Clear Asset Bundle ใน Odoo:
     - ไปที่ Settings > Technical > Assets
     - คลิก "Clear Assets Cache" (ถ้ามี)
   - หรือ Hard Refresh: `Ctrl+Shift+Delete` แล้วเลือก Clear cached files

### ปัญหาที่พบบ่อยใน Production

#### 1. สีไม่เปลี่ยนหลังติดตั้ง

**สาเหตุ:** Asset bundle ถูก cache หรือโมดูลยังไม่ได้ upgrade

**วิธีแก้:**
```bash
# 1. Upgrade โมดูล
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# 2. Restart Odoo
docker-compose restart odoo  # หรือ sudo systemctl restart odoo

# 3. Clear browser cache
# กด Ctrl+Shift+R หรือ Ctrl+F5

# 4. ถ้ายังไม่ได้ ให้ restart Odoo อีกครั้ง
```

#### 2. สีเปลี่ยนเฉพาะบางหน้า

**สาเหตุ:** CSS Specificity ไม่สูงพอ หรือมี inline styles

**วิธีแก้:**
- ตรวจสอบว่าใช้ `!important` ใน SCSS file แล้ว
- ตรวจสอบ browser DevTools (F12) เพื่อดูว่า CSS rule ไหนถูก override
- เพิ่ม CSS specificity ในไฟล์ `custom_theme.scss`

#### 3. Asset ไม่ถูก compile

**สาเหตุ:** SCSS compiler ไม่ทำงานหรือมี error

**วิธีแก้:**
```bash
# ตรวจสอบ log
tail -f /var/log/odoo/odoo.log

# ตรวจสอบว่าโมดูลถูก load
# ใน Odoo: Settings > Technical > Database Structure > Modules
# ค้นหา custom_theme_onthisday และตรวจสอบว่า state = 'installed'
```

#### 4. หลังจาก Upgrade โมดูลสียังไม่เปลี่ยน

**วิธีแก้:**
```bash
# 1. Upgrade โมดูลด้วย force
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# 2. Restart Odoo
docker-compose restart odoo

# 3. Clear asset cache ใน browser
# กด Ctrl+Shift+Delete แล้วเลือก Clear cached images and files

# 4. Hard refresh หน้าเว็บ
# กด Ctrl+Shift+R หรือ Ctrl+F5
```

## Troubleshooting

### สีไม่เปลี่ยน

1. **ตรวจสอบว่าโมดูลถูกติดตั้งแล้ว**
   - ไปที่ Apps > ค้นหา "Custom Theme - On This Day"
   - ตรวจสอบว่า state = "Installed"

2. **Upgrade โมดูล**
   ```bash
   odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init
   ```

3. **Restart Odoo**
   ```bash
   make restart
   # หรือ
   docker-compose restart odoo
   ```

4. **Clear Browser Cache**
   - Windows/Linux: `Ctrl+Shift+R` หรือ `Ctrl+F5`
   - Mac: `Cmd+Shift+R`
   - หรือ Hard Refresh: `Ctrl+Shift+Delete`

5. **ตรวจสอบว่าไฟล์ SCSS ถูก compile แล้ว**
   - เปิด Browser DevTools (F12)
   - ไปที่ tab Network
   - Reload หน้าเว็บ
   - ค้นหาไฟล์ CSS ที่มีชื่อ custom_theme
   - ตรวจสอบว่าไฟล์ถูกโหลดและมีเนื้อหาที่ถูกต้อง

6. **ตรวจสอบ Odoo Log**
   ```bash
   tail -f /var/log/odoo/odoo.log
   # หรือ
   docker-compose logs -f odoo
   ```
   - ค้นหาคำว่า "custom_theme" หรือ "error"
   - ตรวจสอบว่ามี error เกี่ยวกับ SCSS compilation หรือไม่

### ต้องการเปลี่ยนสีเพิ่มเติม

แก้ไขไฟล์ `static/src/scss/custom_theme.scss` และเพิ่ม CSS rules ตามต้องการ

หลังจากแก้ไข:
1. Upgrade โมดูล: `odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init`
2. Restart Odoo
3. Clear Browser Cache

## หมายเหตุ

- ไฟล์ SCSS จะถูก compile อัตโนมัติเมื่อ Odoo โหลด
- ใน Production ควร restart Odoo หลังแก้ไข SCSS file
- ควรทดสอบสีในหลายๆ หน้าจอเพื่อความเหมาะสม
- ใช้สีที่มี Contrast สูงเพื่อความอ่านง่าย
- ใน Production ควร upgrade โมดูลแทนการติดตั้งใหม่ เพื่อรักษา asset bundle cache

## License

LGPL-3

