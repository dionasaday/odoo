# 🔧 วิธีเปิดใช้งาน "Track Inventory?" สำหรับ Products จาก Zortout

## ปัญหา

เมื่อ sync products จาก Zortout, "Track Inventory?" checkbox ไม่ถูกเลือกอัตโนมัติ

## สาเหตุ

ใน Odoo 19:
- "Track Inventory?" checkbox ต้องการ Product Type = "Storable Product" (`type='product'`)
- แต่ `type='product'` ไม่ valid ใน Odoo 19 → เกิด error "Wrong value"
- เราใช้ `type='consu'` (consumable) แทน ซึ่งไม่สามารถ track inventory ได้

## วิธีแก้ไข

### วิธีที่ 1: เปิดใช้งานด้วยตนเอง (แนะนำสำหรับตอนนี้)

1. **ไปที่ Inventory > Products**
2. **เลือกสินค้าที่ต้องการ**
3. **ไปที่ Tab "General Information"**
4. **เลือก "Track Inventory?" checkbox**
5. **Save**

### วิธีที่ 2: ใช้ Mass Update (ถ้ามีหลาย products)

1. **ไปที่ Inventory > Products**
2. **เลือก products ที่ต้องการ (ใช้ filter หรือ search)**
3. **ใช้ Action > Edit** (ถ้ามี)
4. **เลือก "Track Inventory?" checkbox**
5. **Save**

### วิธีที่ 3: ใช้ SQL Update (สำหรับ Technical Users)

```sql
-- เปิดใช้งาน tracking สำหรับ products ที่เป็น storable (producttype = 0)
-- หมายเหตุ: ต้องระวัง - อาจส่งผลต่อ products อื่น
UPDATE product_template
SET tracking = 'lot'
WHERE type = 'consu'
  AND default_code IN (
    SELECT default_code 
    FROM product_template 
    WHERE default_code IS NOT NULL
  );
```

### วิธีที่ 4: สร้าง Script สำหรับ Bulk Update

สร้าง Python script เพื่อ update products:

```python
# ใน Odoo shell หรือ custom script
products = env['product.template'].search([
    ('type', '=', 'consu'),
    ('default_code', '!=', False),
])
products.write({'tracking': 'lot'})
```

## หมายเหตุสำคัญ

⚠️ **ข้อจำกัดใน Odoo 19:**
- ไม่สามารถใช้ `type='product'` ได้ (ไม่ valid)
- "Track Inventory?" checkbox อาจไม่ทำงานกับ `type='consu'`
- ต้องเปิดใช้งานด้วยตนเองหรือใช้ workaround

## Workaround ที่ใช้ได้

1. **ใช้ `tracking='lot'`:**
   - เปิดใช้งาน lot tracking
   - อาจไม่เปิด "Track Inventory?" checkbox แต่สามารถ track stock ได้

2. **ใช้ Stock Quant โดยตรง:**
   - ระบบ sync stock ใช้ `stock.quant` โดยตรง
   - ไม่ต้องเปิด "Track Inventory?" checkbox ก็สามารถ update stock ได้

## สรุป

- **"Track Inventory?" checkbox**: ต้องเปิดใช้งานด้วยตนเอง (ข้อจำกัดของ Odoo 19)
- **Stock Sync**: ยังทำงานได้ปกติแม้ไม่เปิด checkbox (ใช้ `stock.quant` โดยตรง)
- **Recommendation**: เปิดใช้งานด้วยตนเองสำหรับ products ที่ต้องการ track inventory

