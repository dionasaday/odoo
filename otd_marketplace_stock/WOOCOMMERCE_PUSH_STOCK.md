# คู่มือการ Push Stock จาก Odoo ไปยัง WooCommerce

## ภาพรวม

ระบบสามารถ push จำนวนสต็อกจาก Odoo ไปยัง WooCommerce ได้อัตโนมัติ โดยใช้ Product Bindings เพื่อ map สินค้าระหว่าง Odoo กับ WooCommerce

## ขั้นตอนการตั้งค่า

### 1. สร้าง Product Bindings

ก่อนที่จะ push stock ได้ ต้องสร้าง Product Bindings เพื่อ map สินค้าใน Odoo กับสินค้าใน WooCommerce:

1. ไปที่ **Marketplace > Product Bindings**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Product**: เลือกสินค้าใน Odoo
   - **Shop**: เลือก WooCommerce shop
   - **External SKU**: ใส่ SKU ที่ใช้ใน WooCommerce (ต้องตรงกับ SKU ใน WooCommerce)
   - **External Product ID**: Product ID จาก WooCommerce (optional)
4. **Save**

**หมายเหตุ**: External SKU ต้องตรงกับ SKU ใน WooCommerce เป๊ะๆ (case-sensitive)

### 2. ตั้งค่า Stock Location

1. ไปที่ **Marketplace > Accounts > WooCommerce Account**
2. ไปที่แท็บ **Stock Configuration**
3. ตั้งค่า **Stock Location**: เลือก location ที่ต้องการใช้คำนวณ stock
4. ตั้งค่า **Push Buffer Quantity**: จำนวนที่ต้องการหักออกจาก stock (default: 5)
5. ตั้งค่า **Minimum Online Quantity**: จำนวนขั้นต่ำที่จะแสดง online (default: 0)

## วิธีการ Push Stock

### วิธีที่ 1: Push Stock ทั้งหมด (จาก Account)

1. ไปที่ **Marketplace > Accounts > WooCommerce Account**
2. คลิกปุ่ม **"Push Stock to WooCommerce"**
3. ระบบจะสร้าง Job และ push stock สำหรับ product bindings ทั้งหมด

### วิธีที่ 2: Push Stock สำหรับ Product เดียว (จาก Product Binding)

1. ไปที่ **Marketplace > Product Bindings**
2. เปิด product binding ที่ต้องการ
3. คลิกปุ่ม **"Push Stock"**
4. ระบบจะสร้าง Job และ push stock สำหรับ product นั้น

### วิธีที่ 3: Auto Push (อัตโนมัติ)

ระบบจะ push stock อัตโนมัติเมื่อ:
- มีการเปลี่ยนแปลง stock quantity ใน Odoo (Stock Move หรือ Stock Quant)
- ระบบจะสร้าง Job อัตโนมัติและ push stock ภายใน 2 นาที

## การคำนวณ Stock Quantity

ระบบจะคำนวณ stock quantity ดังนี้:

```
Available Qty = Qty Available - Buffer Qty
Final Qty = max(Min Online Qty, Available Qty)
```

**ตัวอย่าง**:
- Qty Available: 100
- Push Buffer Qty: 5
- Min Online Qty: 0
- **Final Qty = max(0, 100 - 5) = 95**

## ตรวจสอบผลลัพธ์

### 1. ตรวจสอบ Job Status

1. ไปที่ **Marketplace > Jobs**
2. ค้นหา Job ที่มีชื่อ "Push Stock to WooCommerce"
3. ตรวจสอบ:
   - **State**: ควรเป็น `Done` (ถ้าสำเร็จ)
   - **Result**: ดูจำนวน products_pushed และ errors

### 2. ตรวจสอบใน WooCommerce

1. เข้าสู่ระบบ WooCommerce Admin
2. ไปที่ **Products**
3. เปิด product ที่ต้องการตรวจสอบ
4. ตรวจสอบ **Stock quantity** ว่าถูกอัพเดทแล้วหรือไม่

### 3. ตรวจสอบใน Product Binding

1. ไปที่ **Marketplace > Product Bindings**
2. เปิด product binding
3. ตรวจสอบ:
   - **Last Stock Push**: เวลาที่ push ล่าสุด
   - **Current Online Qty**: จำนวนที่ push ไปล่าสุด

## Troubleshooting

### Error: "Product with SKU not found"

**สาเหตุ**: SKU ใน WooCommerce ไม่ตรงกับ External SKU ใน Product Binding

**แก้ไข**:
1. ตรวจสอบ SKU ใน WooCommerce (Product > Edit > SKU)
2. ตรวจสอบ External SKU ใน Product Binding
3. ตรวจสอบว่า SKU ตรงกัน (case-sensitive)

### Error: "No active product bindings found"

**สาเหตุ**: ยังไม่ได้สร้าง Product Bindings หรือ Product Bindings ไม่ active

**แก้ไข**:
1. ตรวจสอบว่ามี Product Bindings หรือไม่
2. ตรวจสอบว่า Product Bindings active และไม่ exclude_push

### Stock ไม่ถูกอัพเดทใน WooCommerce

**สาเหตุ**: อาจเป็นเพราะ:
- API key ไม่มีสิทธิ์ Write
- Product ไม่มี SKU ใน WooCommerce
- Network error

**แก้ไข**:
1. ตรวจสอบ API key permissions (ต้องเป็น Read/Write)
2. ตรวจสอบว่า product มี SKU ใน WooCommerce
3. ตรวจสอบ logs:
   ```bash
   docker compose logs odoo | grep -i "woocommerce.*push\|update.*inventory"
   ```

### Stock ถูก push แต่จำนวนไม่ถูกต้อง

**สาเหตุ**: อาจเป็นเพราะการตั้งค่า Buffer หรือ Min Qty

**แก้ไข**:
1. ตรวจสอบ Push Buffer Quantity ใน Account settings
2. ตรวจสอบ Minimum Online Quantity ใน Account settings
3. ตรวจสอบ Buffer Override ใน Product Binding (ถ้ามี)

## หมายเหตุ

- Stock จะถูก push ไปยัง WooCommerce ทันทีเมื่อ Job ทำงาน
- ระบบจะ push stock อัตโนมัติเมื่อมีการเปลี่ยนแปลง stock ใน Odoo
- External SKU ต้องตรงกับ SKU ใน WooCommerce เป๊ะๆ
- API key ต้องมีสิทธิ์ **Read/Write** เพื่อ push stock

