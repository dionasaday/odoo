# แก้ไขปัญหา Internal Server Error

## สาเหตุที่พบบ่อย

หลังจากเพิ่มฟีเจอร์การปรับแต่งสีผ่าน Settings แล้ว อาจพบ Internal Server Error เมื่อเข้าถึงหน้า Settings

### สาเหตุหลัก

1. **Module ยังไม่ได้ Upgrade**: Field ใหม่ยังไม่มีใน database
2. **JavaScript Error**: JavaScript execute ก่อนที่ Odoo จะ ready
3. **Controller Error**: Controller route อาจมีปัญหา
4. **View Error**: View structure อาจไม่ถูกต้อง

## วิธีแก้ไข

### ขั้นตอนที่ 1: Upgrade Module

```bash
# Upgrade module
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# Restart Odoo
docker-compose restart odoo
# หรือ
sudo systemctl restart odoo
```

### ขั้นตอนที่ 2: ตรวจสอบว่า Field ถูกสร้างใน Database

```bash
# เข้าสู่ Odoo shell
odoo-bin shell -d <database_name>

# ตรวจสอบ field
>>> env['res.company']._fields.get('theme_primary_color')
>>> env['res.config.settings']._fields.get('theme_primary_color')
```

### ขั้นตอนที่ 3: ตรวจสอบ Log

```bash
# ดู Odoo log
tail -f /var/log/odoo/odoo.log

# หรือ Docker
docker-compose logs -f odoo
```

ค้นหาคำว่า:
- `custom_theme_onthisday`
- `theme_primary_color`
- `Internal Server Error`
- `Traceback`

### ขั้นตอนที่ 4: Clear Cache

```bash
# Restart Odoo
docker-compose restart odoo

# Clear browser cache
# กด Ctrl+Shift+Delete แล้วเลือก Clear cached images and files
```

### ขั้นตอนที่ 5: ตรวจสอบ JavaScript

1. เปิด Browser DevTools (F12)
2. ไปที่ tab Console
3. ตรวจสอบว่ามี error เกี่ยวกับ `theme_color.js`
4. ตรวจสอบว่าไฟล์ถูกโหลดแล้ว

## ถ้ายังแก้ไม่ได้

### วิธีที่ 1: Uninstall และ Install ใหม่

```bash
# Uninstall module
odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init

# Install module ใหม่
odoo-bin -i custom_theme_onthisday -d <database_name> --stop-after-init

# Restart Odoo
docker-compose restart odoo
```

### วิธีที่ 2: ตรวจสอบ Python Code

ตรวจสอบว่า:
1. `models/res_company.py` มี field ครบ
2. `models/res_config_settings.py` มี field ครบ
3. `controllers/theme_controller.py` ไม่มี syntax error
4. `views/res_config_settings_views.xml` ไม่มี XML error

### วิธีที่ 3: ลบ JavaScript ชั่วคราว

ถ้า JavaScript เป็นปัญหา ให้ comment JavaScript ใน `__manifest__.py`:

```python
'assets': {
    'web.assets_backend': [
        'custom_theme_onthisday/static/src/scss/custom_theme.scss',
        # 'custom_theme_onthisday/static/src/js/theme_color.js',  # Comment ชั่วคราว
    ],
},
```

แล้ว upgrade module และทดสอบอีกครั้ง

### วิธีที่ 4: ตรวจสอบ View

ตรวจสอบว่า view ไม่มีปัญหา:

```bash
# เข้าสู่ Odoo shell
odoo-bin shell -d <database_name>

# ตรวจสอบ view
>>> view = env.ref('custom_theme_onthisday.res_config_settings_view_form_theme_colors')
>>> view.arch
```

## ตรวจสอบว่า Module ทำงานถูกต้อง

1. **ตรวจสอบว่า Field ถูกสร้างใน Database**:
   ```sql
   SELECT column_name FROM information_schema.columns 
   WHERE table_name = 'res_company' AND column_name LIKE 'theme%';
   ```

2. **ตรวจสอบว่า View ถูกสร้าง**:
   - ไปที่ Settings > Technical > User Interface > Views
   - ค้นหา "res.config.settings.view.form.theme.colors"

3. **ตรวจสอบว่า Controller ทำงาน**:
   - เปิด Browser DevTools (F12)
   - ไปที่ tab Network
   - Reload หน้าเว็บ
   - ค้นหา `/custom_theme/get_colors`
   - ตรวจสอบว่า response เป็น 200 OK

## สรุป

ปัญหาส่วนใหญ่เกิดจาก:
1. Module ยังไม่ได้ upgrade
2. Field ยังไม่มีใน database
3. JavaScript error

วิธีแก้ไข:
1. Upgrade module
2. Restart Odoo
3. Clear browser cache
4. ตรวจสอบ log สำหรับ error messages

