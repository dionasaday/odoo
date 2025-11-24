# คำแนะนำการ Upgrade Module

## ปัญหาที่พบ

เมื่อพยายามบันทึก Settings จะเกิด error:
```
column "theme_primary_color" of relation "res_config_settings" does not exist
```

## สาเหตุ

Module ยังไม่ได้ upgrade เพื่อสร้าง columns ใน database

## วิธีแก้ไข

### วิธีที่ 1: Upgrade ผ่าน Odoo UI (แนะนำ)

1. เข้าสู่ระบบ Odoo
2. ไปที่ **Apps**
3. ค้นหา "Custom Theme - On This Day"
4. คลิก **Upgrade**

### วิธีที่ 2: Upgrade ผ่าน Command Line

```bash
# หยุด Odoo
docker-compose stop odoo

# Upgrade module
docker-compose run --rm odoo odoo -u custom_theme_onthisday -d odoo19 --stop-after-init

# เริ่ม Odoo อีกครั้ง
docker-compose start odoo
```

### วิธีที่ 3: Upgrade ผ่าน Odoo Shell (ถ้าเข้าถึงได้)

```bash
docker-compose exec odoo odoo shell -d odoo19

# ใน Odoo shell
>>> module = env['ir.module.module'].search([('name', '=', 'custom_theme_onthisday')])
>>> module.button_immediate_upgrade()
```

## ตรวจสอบว่า Upgrade สำเร็จ

หลังจาก upgrade แล้ว ให้ตรวจสอบว่า columns ถูกสร้างแล้ว:

```sql
-- ตรวจสอบ res_config_settings
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'res_config_settings' 
AND column_name LIKE 'theme%';

-- ตรวจสอบ res_company
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'res_company' 
AND column_name LIKE 'theme%';
```

ควรเห็น columns:
- `theme_primary_color`
- `theme_secondary_color`
- `theme_text_color`

## หลังจาก Upgrade

1. Restart Odoo:
   ```bash
   docker-compose restart odoo
   ```

2. ไปที่ Settings > General Settings > Theme Colors
3. ควรสามารถแก้ไขสีและบันทึกได้แล้ว

## ถ้ายังมีปัญหา

1. ตรวจสอบ log:
   ```bash
   docker-compose logs -f odoo | grep -i error
   ```

2. ตรวจสอบว่า module ถูกติดตั้งแล้ว:
   - ไปที่ Apps
   - ค้นหา "Custom Theme - On This Day"
   - ตรวจสอบว่า state = "Installed"

3. Clear browser cache:
   - กด Ctrl+Shift+Delete
   - เลือก Clear cached images and files

