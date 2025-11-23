# วิธีแก้ไข Track Inventory Checkbox ใน Odoo 19

## ปัญหา
แม้ว่าจะตั้งค่า `tracking='lot'` แล้ว แต่ "Track Inventory?" checkbox ยังไม่ถูกเลือกใน UI

## สาเหตุ
ใน Odoo 19, checkbox "Track Inventory?" อาจจะถูกควบคุมโดย:
1. Field `tracking` (none/lot/serial)
2. Product type (`type='consu'` สำหรับ Goods)
3. Computed field หรือ method อื่น

## วิธีแก้ไข

### วิธีที่ 1: ใช้ SQL เพื่อตรวจสอบและอัพเดทโดยตรง

```sql
-- ตรวจสอบ products ที่มี tracking='lot' แต่ checkbox ยังไม่ถูกเลือก
SELECT id, name, default_code, type, tracking 
FROM product_template 
WHERE type = 'consu' 
  AND default_code IS NOT NULL 
  AND tracking = 'lot'
LIMIT 10;

-- อัพเดท tracking เป็น 'lot' สำหรับ products ทั้งหมด
UPDATE product_template 
SET tracking = 'lot' 
WHERE type = 'consu' 
  AND default_code IS NOT NULL 
  AND (tracking IS NULL OR tracking = 'none');
```

### วิธีที่ 2: ใช้ Odoo Shell

```python
# ใน Odoo shell
env = self.env
products = env['product.template'].search([
    ('type', '=', 'consu'),
    ('default_code', '!=', False),
])

for product in products:
    if product.tracking != 'lot':
        product.write({'tracking': 'lot'})
        print(f"Updated: {product.default_code} - {product.name}")

env.cr.commit()
```

### วิธีที่ 3: ใช้ปุ่ม "แก้ไข Track Inventory ทั้งหมด" อีกครั้ง

1. ไปที่ Marketplace > Accounts > Zortout
2. กดปุ่ม "แก้ไข Track Inventory ทั้งหมด" อีกครั้ง
3. ระบบจะอัพเดท products ทั้งหมดด้วย `tracking='lot'`

## หมายเหตุ

- ใน Odoo 19, `tracking='lot'` จะทำให้ checkbox ถูกเลือกและแสดง "By Lots"
- แม้ว่าจะแสดง "By Lots" แต่ก็ยังสามารถ track โดย quantity ได้โดยไม่ต้องใช้ lot numbers
- หาก checkbox ยังไม่ถูกเลือกหลังจากอัพเดท อาจจะต้อง:
  1. Refresh หน้าเว็บ (F5)
  2. Logout/Login ใหม่
  3. Clear browser cache
  4. Restart Odoo

## ตรวจสอบผลลัพธ์

```python
# ตรวจสอบว่า product มี tracking='lot' แล้วหรือไม่
product = env['product.template'].search([('default_code', '=', 'FB6740')], limit=1)
print(f"Tracking: {product.tracking}")  # ควรเป็น 'lot'
print(f"Type: {product.type}")  # ควรเป็น 'consu'
```

