# คำแนะนำการติดตั้ง Module

## ปัญหา: ไม่พบ Theme Colors ใน Settings

Module ยังไม่ได้ติดตั้ง! ต้องติดตั้ง module ก่อน

## วิธีติดตั้ง

### วิธีที่ 1: ผ่าน Odoo UI (แนะนำ)

1. **เข้าสู่ระบบ Odoo**
   - ไปที่ `http://localhost:8069`
   - Login เข้าระบบ

2. **Update Apps List**
   - ไปที่ **Apps**
   - คลิก **"Update Apps List"** (รอให้เสร็จ)

3. **ติดตั้ง Module**
   - ในหน้า Apps
   - ค้นหา **"Custom Theme - On This Day"** หรือ **"custom_theme_onthisday"**
   - คลิก **Install**

4. **ตรวจสอบ**
   - ไปที่ **Settings > General Settings**
   - ควรเห็น section **"Theme Colors"** แล้ว

### วิธีที่ 2: ผ่าน Command Line

```bash
# 1. หยุด Odoo
docker-compose stop odoo

# 2. ติดตั้ง module
docker-compose run --rm odoo odoo -i custom_theme_onthisday -d odoo19 --stop-after-init

# 3. เริ่ม Odoo
docker-compose start odoo
```

### วิธีที่ 3: ผ่าน Odoo Shell

```bash
docker-compose exec odoo odoo shell -d odoo19

# ใน Odoo shell
>>> module = env['ir.module.module'].search([('name', '=', 'custom_theme_onthisday')])
>>> module.button_immediate_install()
```

## ตรวจสอบว่า Module ถูกติดตั้งแล้ว

```sql
SELECT name, state FROM ir_module_module WHERE name = 'custom_theme_onthisday';
```

ควรเห็น:
- `state = 'installed'` ✅

## หลังจากติดตั้ง

1. **Restart Odoo** (ถ้าติดตั้งผ่าน command line):
   ```bash
   docker-compose restart odoo
   ```

2. **Clear Browser Cache**:
   - กด `Ctrl+Shift+R` หรือ `Cmd+Shift+R`

3. **ไปที่ Settings > General Settings**
   - ควรเห็น section **"Theme Colors"** แล้ว

## ถ้ายังไม่เห็น Theme Colors

1. **ตรวจสอบว่า Module ถูกติดตั้งแล้ว**:
   - ไปที่ Apps
   - ค้นหา "Custom Theme - On This Day"
   - ตรวจสอบว่า state = "Installed"

2. **ตรวจสอบ View**:
   ```bash
   docker-compose exec -T db psql -U odoo -d odoo19 -c "SELECT id, name, active FROM ir_ui_view WHERE name LIKE '%theme%color%';"
   ```

3. **Restart Odoo**:
   ```bash
   docker-compose restart odoo
   ```

4. **Clear Browser Cache**:
   - Hard refresh: `Ctrl+Shift+Delete`

## สรุป

**Module ต้องถูกติดตั้งก่อน** ถึงจะเห็น Theme Colors ใน Settings!

