# 🚀 Quick Test Guide - Marketplace Integration

## ✅ สถานะปัจจุบัน
- ✅ OAuth Connection สำเร็จ
- ✅ Shop Record สร้างอัตโนมัติ (Shop ID: 95152937)
- ✅ Ready to test!

## 🎯 ขั้นตอนทดสอบ (ลำดับความสำคัญ)

### 1️⃣ ทดสอบดึง Orders (สำคัญที่สุด) ⭐

#### วิธีง่ายที่สุด:
1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอก:
   - **Job Name**: `Test Pull Orders`
   - **Job Type**: `pull_order`
   - **Account**: Shopee Thailand
   - **Shop**: Shopee Shop 95152937
   - **Payload**: 
     ```json
     {
       "since": "2024-11-01T00:00:00"
     }
     ```
4. **Save**
5. รอสักครู่ แล้วตรวจสอบ:
   - **Marketplace** > **Jobs** > ดู State
   - **Marketplace** > **Orders** > ดู orders ที่ดึงมา

#### ตรวจสอบ Logs:
```bash
docker compose logs -f odoo | grep -i "order\|shopee\|job"
```

### 2️⃣ ทดสอบ Product Bindings

#### สร้าง Binding:
1. **Marketplace** > **Product Bindings** > **New**
2. กรอก:
   - **Shop**: Shopee Shop 95152937
   - **Product**: เลือกสินค้าจาก Odoo
   - **External Product ID**: ใส่ Shopee Product ID
   - **External SKU**: ใส่ Shopee SKU

### 3️⃣ ทดสอบ Stock Sync

#### ตั้งค่า Sync Rule:
1. **Marketplace** > **Sync Rules** > **New**
2. กรอก:
   - **Shop**: Shopee Shop 95152937
   - **Buffer Quantity**: 10
   - **Min Online Quantity**: 5

#### Push Stock:
1. **Marketplace** > **Jobs** > **New**
2. **Job Type**: `push_stock`
3. **Account**: Shopee Thailand
4. **Shop**: Shopee Shop 95152937

## 🔍 ตรวจสอบผลลัพธ์

### ตรวจสอบ Orders:
- **Marketplace** > **Orders**
- ควรเห็น orders จาก Shopee
- ตรวจสอบ State: `pending`, `processing`, `completed`

### ตรวจสอบ Jobs:
- **Marketplace** > **Jobs**
- ดู State: `done` = สำเร็จ, `failed` = ล้มเหลว
- ดู Error Messages (ถ้ามี)

### ตรวจสอบ Logs:
```bash
# ดู logs ทั้งหมด
docker compose logs -f odoo

# ดู logs เฉพาะ Marketplace
docker compose logs odoo | grep -i "marketplace"

# ดู logs ของ Jobs
docker compose logs odoo | grep -i "job"
```

## ⚠️ Troubleshooting

### Orders ไม่ถูกดึงมา:
1. ตรวจสอบ Access Token ยังไม่หมดอายุ
2. ตรวจสอบ Shop ID ถูกต้อง (95152937)
3. ตรวจสอบ Job State และ Error
4. ตรวจสอบ API permissions

### Job Failed:
1. ดู Error Message ใน Job
2. ตรวจสอบ Logs
3. ตรวจสอบ Access Token
4. ตรวจสอบ Shop ID

## 📊 Dashboard

ตรวจสอบ Dashboard:
- **Marketplace** > **Dashboard**
- ดูสรุป Sales, Orders, Stock

## 🎯 Next Steps

หลังจากทดสอบสำเร็จ:
1. ตั้งค่า Sync Rules สำหรับ production
2. ตั้งค่า Cron Jobs
3. ตั้งค่า Monitoring
4. ตั้งค่า Error Notifications

