# 🧪 คู่มือทดสอบระบบ Marketplace Integration

## ✅ สถานะปัจจุบัน
- ✅ OAuth Connection สำเร็จ
- ✅ Access Token และ Refresh Token ถูกบันทึก
- ✅ Shop Record สร้างอัตโนมัติแล้ว (Shop ID: 95152937)

## 📋 ขั้นตอนการทดสอบ

### 1. ทดสอบการดึง Orders จาก Shopee

#### วิธีที่ 1: สร้าง Job ผ่าน UI
1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Job Type**: `pull_orders`
   - **Account**: Shopee Thailand
   - **Shop**: Shopee Shop 95152937
   - **Payload**: 
     ```json
     {
       "since": "2024-11-01T00:00:00",
       "until": null
     }
     ```
   - **Priority**: 1 (ปกติ)
4. **Save** และรอให้ job ทำงาน

#### วิธีที่ 2: ใช้ Cron Job (อัตโนมัติ)
- Cron Job "Marketplace: Pull Orders" จะทำงานอัตโนมัติ
- ตรวจสอบที่ **Marketplace** > **Jobs** ว่ามี job ใหม่หรือไม่

#### ตรวจสอบผลลัพธ์:
- ไปที่ **Marketplace** > **Orders**
- ควรเห็น orders ที่ดึงมาจาก Shopee
- ตรวจสอบ Job Status: **Marketplace** > **Jobs** > ดูว่า job สำเร็จหรือไม่

### 2. ทดสอบ Product Bindings (เชื่อมโยงสินค้า)

#### สร้าง Product Binding:
1. ไปที่ **Marketplace** > **Product Bindings**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Shop**: Shopee Shop 95152937
   - **Product**: เลือกสินค้าจาก Odoo
   - **External Product ID**: ใส่ Shopee Product ID
   - **External SKU**: ใส่ Shopee SKU
   - **Active**: ✓
4. **Save**

#### Bulk Binding (เชื่อมโยงหลายสินค้าพร้อมกัน):
1. ไปที่ **Marketplace** > **Product Bindings**
2. คลิก **Bulk Binding** (ถ้ามี)
3. เลือก Shop และ Products
4. ระบบจะเชื่อมโยงสินค้าอัตโนมัติ

### 3. ทดสอบ Stock Sync (ส่ง Stock ไป Shopee)

#### ตั้งค่า Sync Rules:
1. ไปที่ **Marketplace** > **Sync Rules**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Shop**: Shopee Shop 95152937
   - **Buffer Quantity**: 10 (สำรอง)
   - **Min Online Quantity**: 5 (จำนวนขั้นต่ำ)
   - **Rounding**: 0 (ไม่ปัดเศษ)
   - **Active**: ✓
4. **Save**

#### ทดสอบ Push Stock:
1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Job Type**: `push_stock`
   - **Account**: Shopee Thailand
   - **Shop**: Shopee Shop 95152937
   - **Payload**: 
     ```json
     {
       "product_ids": [1, 2, 3]
     }
     ```
     หรือปล่อยว่างเพื่อ sync ทั้งหมด
4. **Save** และรอให้ job ทำงาน

#### ตรวจสอบผลลัพธ์:
- ตรวจสอบ Stock ใน Shopee Seller Center
- ตรวจสอบ Job Status
- ตรวจสอบ Logs: `docker compose logs odoo | grep "stock\|sync"`

### 4. ทดสอบ Order Processing

#### ตรวจสอบ Order Flow:
1. **Marketplace** > **Orders** - ดู orders ที่ดึงมา
2. ตรวจสอบว่า orders ถูกสร้างเป็น `sale.order` หรือไม่
3. ตรวจสอบ Stock Reservation
4. ตรวจสอบ Delivery Documents

#### สร้าง Sale Order จาก Marketplace Order:
1. ไปที่ **Marketplace** > **Orders**
2. เลือก order ที่ต้องการ
3. คลิก **Create Sale Order** (ถ้ามี action)
4. ตรวจสอบว่า sale.order ถูกสร้าง

### 5. ทดสอบ Webhooks (ถ้ามี)

#### ตั้งค่า Webhook:
1. ไปที่ **Settings** > **Technical** > **Parameters** > **System Parameters**
2. ตรวจสอบ webhook URL
3. ตั้งค่าใน Shopee Seller Center (ถ้ารองรับ)

#### ทดสอบ Webhook:
- สร้าง order ใหม่ใน Shopee
- ตรวจสอบว่า webhook ถูกส่งมาที่ Odoo
- ตรวจสอบ logs: `docker compose logs odoo | grep "webhook"`

### 6. ทดสอบ Error Handling

#### ทดสอบกรณี Error:
1. ลองดึง orders จากวันที่ไม่มี (ไม่มี orders)
2. ลอง sync stock ของสินค้าที่ไม่มี binding
3. ตรวจสอบว่า error ถูกบันทึกใน Job Queue
4. ตรวจสอบ Retry Mechanism

## 🔍 ตรวจสอบและ Debug

### ตรวจสอบ Logs:
```bash
# ดู logs ทั้งหมด
docker compose logs -f odoo

# ดู logs เฉพาะ Marketplace
docker compose logs odoo | grep -i "marketplace\|shopee\|order\|stock"

# ดู logs ของ Jobs
docker compose logs odoo | grep -i "job\|queue"
```

### ตรวจสอบ Job Queue:
- ไปที่ **Marketplace** > **Jobs**
- ดู Job Status: pending, processing, completed, failed
- ดู Error Messages (ถ้ามี)
- ตรวจสอบ Retry Count

### ตรวจสอบ API Calls:
- ดู logs สำหรับ API requests
- ตรวจสอบ response status codes
- ตรวจสอบ error messages จาก Shopee API

## 📊 Dashboard

ตรวจสอบ Dashboard:
- ไปที่ **Marketplace** > **Dashboard**
- ดูสรุป:
  - Sales per channel
  - Pending orders
  - Stock levels
  - Sync status

## ⚠️ Troubleshooting

### Orders ไม่ถูกดึงมา:
1. ตรวจสอบว่า Shop ID ถูกต้อง
2. ตรวจสอบ Access Token ยังไม่หมดอายุ
3. ตรวจสอบ Job Status และ Error Messages
4. ตรวจสอบ API permissions

### Stock ไม่ sync:
1. ตรวจสอบ Product Bindings
2. ตรวจสอบ Sync Rules
3. ตรวจสอบ Stock Quantity ใน Odoo
4. ตรวจสอบ Job Status

### API Errors:
1. ตรวจสอบ Access Token
2. ตรวจสอบ Shop ID
3. ตรวจสอบ API permissions
4. ตรวจสอบ Rate Limiting

## 🎯 Next Steps

หลังจากทดสอบเสร็จ:
1. ตั้งค่า Sync Rules สำหรับ production
2. ตั้งค่า Cron Jobs
3. ตั้งค่า Webhooks (ถ้ามี)
4. ตั้งค่า Error Notifications
5. ตั้งค่า Monitoring/Alerts

