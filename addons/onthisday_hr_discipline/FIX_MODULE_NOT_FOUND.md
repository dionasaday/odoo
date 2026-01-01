# แก้ไขปัญหา ModuleNotFoundError

## ปัญหา

```
ModuleNotFoundError: No module named 'odoo.addons.onthisday_hr_discipline'
```

## สาเหตุที่เป็นไปได้

1. **Odoo Server ยังไม่ได้ Restart** - หลังจากแก้ไขไฟล์ Python/XML
2. **Python Cache** - มีไฟล์ `.pyc` เก่าที่ไม่ตรงกับโค้ดใหม่
3. **Addons Path** - โมดูลไม่อยู่ใน addons path ที่ Odoo รู้จัก

## วิธีแก้ไข

### ขั้นตอนที่ 1: Restart Odoo Server

```bash
# ใช้ Docker Compose
docker compose restart odoo

# หรือ
make restart
```

### ขั้นตอนที่ 2: ลบ Python Cache

```bash
# ลบ __pycache__ ทั้งหมดในโมดูล
find addons/onthisday_hr_discipline -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
find addons/onthisday_hr_discipline -name "*.pyc" -delete
```

### ขั้นตอนที่ 3: Update Apps List ใน Odoo

1. เปิด Odoo: http://localhost:8069
2. ไปที่ **Apps**
3. คลิก **"Update Apps List"** (รอให้เสร็จ)
4. ค้นหา "OnThisDay HR Discipline"

### ขั้นตอนที่ 4: ตรวจสอบ Addons Path

ตรวจสอบว่าโมดูลอยู่ในตำแหน่งที่ถูกต้อง:

**ใน Docker:**
- โมดูลควรอยู่ที่: `/mnt/extra-addons/onthisday_hr_discipline`
- ตรวจสอบ volume mapping ใน `docker-compose.yml`:
  ```yaml
  volumes:
    - ./addons:/mnt/extra-addons
  ```

**ตรวจสอบ config:**
- ดู `config/odoo.conf`:
  ```ini
  addons_path = /mnt/extra-addons,/mnt/enterprise-addons,/usr/lib/python3/dist-packages/odoo/addons
  ```

### ขั้นตอนที่ 5: ตรวจสอบ Syntax Errors

```bash
# ตรวจสอบ Python syntax
python3 -m py_compile addons/onthisday_hr_discipline/__init__.py
python3 -m py_compile addons/onthisday_hr_discipline/models/__init__.py

# ตรวจสอบ XML syntax
xmllint --noout addons/onthisday_hr_discipline/__manifest__.py
```

### ขั้นตอนที่ 6: ตรวจสอบ Logs

```bash
# ดู Odoo logs
docker compose logs odoo | tail -50

# หรือ
tail -50 /var/log/odoo/odoo.log
```

## Checklist

- [ ] Odoo server restart แล้ว
- [ ] Python cache ถูกลบแล้ว
- [ ] Update Apps List แล้ว
- [ ] โมดูลอยู่ใน addons path ที่ถูกต้อง
- [ ] ไม่มี syntax errors
- [ ] ตรวจสอบ logs แล้ว

## สรุป

ปัญหานี้มักเกิดจาก:
1. **Odoo server ยังไม่ได้ restart** → แก้โดย restart
2. **Python cache** → แก้โดยลบ cache
3. **Apps list ไม่ได้ update** → แก้โดย Update Apps List

ลองทำตามขั้นตอนข้างต้นตามลำดับ

