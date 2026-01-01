# ต้อง Restart Odoo Server

## ปัญหา

```
ModuleNotFoundError: No module named 'odoo.addons.onthisday_hr_discipline'
```

## สาเหตุ

Error นี้มักเกิดจาก:
1. **Odoo server ยังไม่ได้ restart** หลังจากแก้ไขไฟล์ Python/XML
2. **Python cache** ยังมีไฟล์เก่า
3. **Apps list ไม่ได้ update** ใน Odoo UI

## วิธีแก้ไข (ทำตามลำดับ)

### ขั้นตอนที่ 1: Restart Odoo Server (สำคัญที่สุด!)

```bash
# ใช้ Docker Compose
docker compose restart odoo

# หรือ
make restart

# หรือถ้าใช้ docker compose โดยตรง
docker compose down
docker compose up -d
```

**รอให้ Odoo server เริ่มทำงานเสร็จ** (ตรวจสอบ logs)

### ขั้นตอนที่ 2: ลบ Python Cache (ถ้ายังมีปัญหา)

```bash
# ลบ __pycache__ ทั้งหมด
find addons/onthisday_hr_discipline -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true
find addons/onthisday_hr_discipline -name "*.pyc" -delete
find addons/onthisday_hr_discipline -name "*.pyo" -delete
```

### ขั้นตอนที่ 3: Update Apps List ใน Odoo UI

1. เปิด Odoo: http://localhost:8069
2. ไปที่ **Apps** (เมนูด้านบน)
3. คลิก **"Update Apps List"** (ปุ่มด้านบนขวา)
4. **รอให้เสร็จ** (อาจใช้เวลาสักครู่)
5. ค้นหา "OnThisDay HR Discipline"

### ขั้นตอนที่ 4: ตรวจสอบ Logs

```bash
# ดู Odoo logs
docker compose logs odoo | tail -50

# หรือ
tail -50 /var/log/odoo/odoo.log
```

ตรวจสอบว่ามี error อื่นหรือไม่

### ขั้นตอนที่ 5: ลองติดตั้งโมดูลอีกครั้ง

หลังจาก restart และ update apps list แล้ว:
1. ไปที่ **Apps**
2. ค้นหา "OnThisDay HR Discipline"
3. คลิก **Install**

## Checklist

- [ ] Odoo server restart แล้ว
- [ ] รอให้ server เริ่มทำงานเสร็จ
- [ ] Python cache ถูกลบแล้ว (ถ้ายังมีปัญหา)
- [ ] Update Apps List แล้ว
- [ ] ตรวจสอบ logs แล้ว
- [ ] ลองติดตั้งโมดูลอีกครั้ง

## หมายเหตุ

- **สำคัญ**: ต้อง restart Odoo server หลังจากแก้ไขไฟล์ Python/XML
- Odoo จะ load โมดูลใหม่เมื่อ server restart
- Update Apps List จะทำให้ Odoo scan โมดูลใหม่

## สรุป

ปัญหานี้มักเกิดจาก **Odoo server ยังไม่ได้ restart**

**วิธีแก้**: Restart Odoo server → Update Apps List → Install Module
