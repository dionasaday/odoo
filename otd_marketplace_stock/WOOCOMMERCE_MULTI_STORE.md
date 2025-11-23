# คู่มือการเชื่อมต่อ WooCommerce หลายเว็บไซต์

## ภาพรวม

ระบบรองรับการเชื่อมต่อ WooCommerce หลายเว็บไซต์พร้อมกัน โดยแต่ละเว็บไซต์จะใช้:
- Account แยกกัน
- Shop แยกกัน
- Product Bindings แยกกัน
- Auto Push Stock แยกกัน (ตาม interval ที่ตั้งค่า)

## ขั้นตอนการเชื่อมต่อ WooCommerce เว็บที่ 2

### 1. สร้าง API Keys ใน WooCommerce เว็บที่ 2

1. เข้าสู่ระบบ WooCommerce Admin ของเว็บที่ 2
2. ไปที่ **WooCommerce > Settings > Advanced > REST API**
3. คลิก **Add Key**
4. กรอกข้อมูล:
   - **Description**: เช่น "Odoo Integration - Store 2"
   - **User**: เลือก user ที่มีสิทธิ์ (แนะนำ: Administrator)
   - **Permissions**: เลือก **Read/Write**
5. คลิก **Generate API Key**
6. **บันทึกข้อมูล**:
   - **Consumer Key**: `ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **Consumer Secret**: `cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 2. สร้าง Marketplace Account ใหม่ใน Odoo

1. ไปที่ **Marketplace > Accounts**
2. คลิก **Create** (หรือปุ่ม "New")
3. กรอกข้อมูล:
   - **Account Name**: ชื่อ account (เช่น "WooCommerce Store 2" หรือชื่อเว็บไซต์)
   - **Channel**: เลือก **WooCommerce**
   - **Company**: เลือกบริษัท (สามารถใช้บริษัทเดียวกันหรือต่างกันได้)
   - **Store URL**: ใส่ Store URL ของเว็บที่ 2 (เช่น `https://store2.com`)
   - **Consumer Key**: ใส่ Consumer Key จากเว็บที่ 2
   - **Consumer Secret**: ใส่ Consumer Secret จากเว็บที่ 2
   - **Push Stock Interval**: 30 นาที (หรือตามต้องการ)
4. **Save**

### 3. ทดสอบการเชื่อมต่อ

1. คลิกปุ่ม **"Test Connection"**
2. ตรวจสอบว่า:
   - ✅ System Status: สำเร็จ
   - ✅ Products API: เข้าถึงได้
   - ✅ Orders API: เข้าถึงได้
   - ✅ Shop created automatically: Shop ถูกสร้างอัตโนมัติ

### 4. เชื่อมต่อข้อมูลสินค้า

1. คลิกปุ่ม **"เชื่อมต่อข้อมูลสินค้า"**
2. ระบบจะ:
   - ดึง products ทั้งหมดจาก WooCommerce เว็บที่ 2
   - Map products โดยใช้ SKU
   - สร้าง Product Bindings อัตโนมัติ
3. ตรวจสอบผลลัพธ์:
   - Created: จำนวน bindings ที่ถูกสร้าง
   - Updated: จำนวน bindings ที่ถูกอัพเดท
   - Not Found: จำนวน products ที่ไม่พบใน Odoo

### 5. Push Stock

1. คลิกปุ่ม **"Push Stock to WooCommerce"**
2. ระบบจะ push stock สำหรับ product bindings ทั้งหมด
3. ตรวจสอบผลลัพธ์ใน Marketplace > Jobs

## การจัดการหลาย WooCommerce Accounts

### แยกตาม Account
- แต่ละ WooCommerce account จะมี:
  - Store URL แยกกัน
  - API Keys แยกกัน
  - Shops แยกกัน
  - Product Bindings แยกกัน

### Auto Push Stock
- แต่ละ account จะ push stock ตาม interval ที่ตั้งค่า
- สามารถตั้งค่า interval ต่างกันได้ (เช่น account 1 = 30 นาที, account 2 = 15 นาที)

### Product Bindings
- Product ใน Odoo เดียวกันสามารถ bind กับหลาย WooCommerce stores ได้
- แต่ละ binding จะมี Shop แยกกัน
- Stock จะถูก push แยกกันตาม shop

## ตัวอย่างการใช้งาน

### Scenario: มี 2 WooCommerce Stores

**Store 1: onthisdayco.com**
- Account: "WooCommerce - On This Day"
- Shop: "WooCommerce - onthisdayco.com"
- Push Interval: 30 นาที
- Product Bindings: 214

**Store 2: store2.com**
- Account: "WooCommerce - Store 2"
- Shop: "WooCommerce - store2.com"
- Push Interval: 30 นาที
- Product Bindings: (จะถูกสร้างเมื่อเชื่อมต่อข้อมูลสินค้า)

### การ Push Stock
- Store 1 จะ push stock ทุก 30 นาที
- Store 2 จะ push stock ทุก 30 นาที
- แต่ละ store จะ push stock แยกกัน ไม่รบกวนกัน

## หมายเหตุ

- แต่ละ WooCommerce account ต้องมี API Keys แยกกัน
- Product Bindings จะแยกตาม Shop
- Stock จะถูก push แยกกันตาม account/shop
- สามารถตั้งค่า Push Stock Interval ต่างกันได้สำหรับแต่ละ account

