# 🔧 แก้ไขปัญหาโมดูลที่ติดค้างในสถานะ "Upgrading"

## 🔴 ปัญหา

โมดูลแสดงสถานะ "Upgrading" ใน Odoo UI ทำให้ไม่สามารถ upgrade โมดูลอื่นๆ ได้

## 🔍 สาเหตุที่เป็นไปได้

1. **UI Cache** - Browser cache หรือ Odoo UI cache ที่ยังแสดงสถานะเก่า
2. **Database State** - โมดูลติดค้างในสถานะ `to upgrade`, `to install`, หรือ `to remove`
3. **Process Lock** - มี upgrade process ที่ติดค้าง
4. **Scheduled Upgrades** - มี scheduled upgrades ที่กำลังรอ

## ✅ วิธีแก้ไข

### ขั้นตอนที่ 1: ตรวจสอบสถานะในฐานข้อมูล

```bash
docker compose exec odoo odoo shell -d your_database_name --no-http
```

```python
Module = env['ir.module.module']

# ตรวจสอบโมดูลที่ติดค้าง
stuck_modules = Module.search([
    ('state', 'in', ['to upgrade', 'to install', 'to remove'])
])

if stuck_modules:
    print(f"พบโมดูลที่ติดค้าง: {len(stuck_modules)}")
    for module in stuck_modules:
        print(f"- {module.name}: {module.state}")
```

### ขั้นตอนที่ 2: Reset สถานะโมดูล (ถ้าพบ)

```python
for module in stuck_modules:
    if module.state == 'to upgrade' and module.installed_version:
        module.state = 'installed'
    elif module.state == 'to install':
        module.state = 'uninstalled'
    elif module.state == 'to remove' and module.installed_version:
        module.state = 'installed'
    else:
        module.state = 'uninstalled'

env.cr.commit()
print("✅ Reset สถานะโมดูลเรียบร้อยแล้ว")
```

### ขั้นตอนที่ 3: ใช้สคริปต์แก้ไขอัตโนมัติ

```bash
cd /Users/nattaphonsupa/odoo19
./scripts/fix_stuck_modules_complete.sh odoo19
```

### ขั้นตอนที่ 4: Restart Odoo

```bash
docker compose restart odoo
```

### ขั้นตอนที่ 5: Clear Browser Cache

1. **Clear browser cache:**
   - กด `Ctrl+Shift+Delete` (Windows/Linux) หรือ `Cmd+Shift+Delete` (Mac)
   - เลือก "Cached images and files"
   - คลิก "Clear data"

2. **Hard refresh หน้า Odoo:**
   - กด `Ctrl+Shift+R` (Windows/Linux) หรือ `Cmd+Shift+R` (Mac)

### ขั้นตอนที่ 6: Update Apps List

1. ไปที่หน้า **Apps** ใน Odoo
2. คลิก **"Update Apps List"**
3. รอให้เสร็จ

### ขั้นตอนที่ 7: ตรวจสอบสถานะอีกครั้ง

หลังจากทำตามขั้นตอนข้างต้นแล้ว:
- สถานะ "Upgrading" ควรหายไป
- สามารถ upgrade โมดูลอื่นๆ ได้แล้ว

## 🛠️ สคริปต์ที่เกี่ยวข้อง

- `scripts/fix_stuck_modules_complete.sh` - สคริปต์สำหรับแก้ไขปัญหาโมดูลที่ติดค้าง

## 📝 หมายเหตุ

- ถ้ายังมีปัญหา ให้ตรวจสอบ Odoo logs:
  ```bash
  docker compose logs odoo --tail 100 | grep -i error
  ```

- ถ้าปัญหายังคงอยู่ ให้ตรวจสอบว่ามี module dependencies ที่ขาดหายไปหรือไม่

## ✅ Checklist

- [ ] ตรวจสอบสถานะโมดูลในฐานข้อมูล
- [ ] Reset สถานะโมดูลที่ติดค้าง (ถ้ามี)
- [ ] Restart Odoo
- [ ] Clear browser cache
- [ ] Hard refresh หน้า Odoo
- [ ] Update Apps List
- [ ] ตรวจสอบว่าสถานะ "Upgrading" หายไปแล้ว
- [ ] ทดสอบ upgrade โมดูลอื่นๆ

