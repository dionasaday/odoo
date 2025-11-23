# 🔄 Zortout Integration Setup Guide

## Overview
ระบบเชื่อมต่อกับ Zortout เพื่อดึงสินค้าและสต็อกแบบ Realtime จาก Zortout มาไว้ใน Odoo

## API Reference
- **Documentation**: https://developers.zortout.com/api-reference/product
- **Base URL**: `https://open-api.zortout.com/v4`
- **Authentication**: API Key based (storename, apikey, apisecret)

## 📋 ขั้นตอนการตั้งค่า

### 1. สร้าง Zortout Account ใน Odoo

1. ไปที่ **Marketplace** > **Accounts**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Account Name**: `Zortout Main`
   - **Channel**: `Zortout`
   - **Company**: เลือกบริษัท
   - **Sync Enabled**: ✓

### 2. ตั้งค่า API Credentials

จาก Zortout Console (https://secure.zortout.com/Integration/ApiReference):

1. คัดลอก **Store Name** (Email):
   - ตัวอย่าง: `supa.nattaphon@gmail.com`
   - ใส่ใน **Client ID / Store Name**

2. คัดลอก **API Key**:
   - ตัวอย่าง: `V9JPcSPlg3gerpw3BT/ZxR0PSUR7Lo10hedW4v6HZk=`
   - ใส่ใน **Client Secret / API Key**

3. คัดลอก **API Secret**:
   - ตัวอย่าง: `Iv2QGNVPDXxz2LMnG6V8KlmcjCfzZsb5Lgp7Blq3F0=`
   - ใส่ใน **Access Token / API Secret**

4. **Save**

### 3. ตั้งค่า Warehouse Code (ถ้าจำเป็น)

1. ไปที่ **Inventory** > **Configuration** > **Warehouses**
2. ตรวจสอบ Warehouse Code (หรือสร้างใหม่)
3. ใช้ Warehouse Code นี้ในการ sync stock

## 🧪 ทดสอบการเชื่อมต่อ

### ทดสอบดึงสินค้า (Products)

1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Job Name**: `Sync Products from Zortout`
   - **Job Type**: `Sync Products from Zortout`
   - **Account**: Zortout Main
   - **Payload** (JSON):
     ```json
     {
       "fetch_all": true,
       "warehouse_code": "WH001",
       "filters": {
         "activestatus": 1
       }
     }
     ```
4. **Save** และรอให้ job ทำงาน

### ทดสอบดึงสต็อก (Stock) - Realtime

1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Job Name**: `Sync Stock from Zortout`
   - **Job Type**: `Sync Stock from Zortout`
   - **Account**: Zortout Main
   - **Payload** (JSON):
     ```json
     {
       "warehouse_code": "WH001",
       "sku_list": ["P0001", "P0002"]
     }
     ```
     หรือปล่อย `sku_list` ว่างเพื่อ sync ทั้งหมด
4. **Save** และรอให้ job ทำงาน

## 📊 Job Payload Options

### Sync Products Payload:
```json
{
  "fetch_all": true,              // true = ดึงทั้งหมด, false = ดึงตาม page
  "warehouse_code": "WH001",      // Warehouse Code (optional)
  "page": 1,                      // Page number (if fetch_all = false)
  "limit": 500,                    // Limit per page (max 500)
  "filters": {
    "createdafter": "2024-01-01", // Created after date
    "createdbefore": "2024-12-31", // Created before date
    "updatedafter": "2024-01-01",  // Updated after date
    "updatedbefore": "2024-12-31", // Updated before date
    "keyword": "search term",       // Search keyword (min 3 chars)
    "searchsku": "P0001",           // Search by SKU
    "variationid": 123,             // Variation ID
    "categoryid": 456,              // Category ID
    "activestatus": 1               // 1 = Active only
  }
}
```

### Sync Stock Payload:
```json
{
  "warehouse_code": "WH001",      // Required: Warehouse Code
  "sku_list": ["P0001", "P0002"]  // Optional: SKU list (empty = sync all)
}
```

## 🔄 ตั้งค่า Cron Job สำหรับ Realtime Sync

### สร้าง Cron Job สำหรับ Stock Sync:

1. ไปที่ **Settings** > **Technical** > **Automation** > **Scheduled Actions**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Name**: `Zortout: Sync Stock Realtime`
   - **Model**: `marketplace.job`
   - **Interval**: `1` minutes (หรือตามต้องการ)
   - **Code**: 
     ```python
     account = env['marketplace.account'].search([('channel', '=', 'zortout'), ('active', '=', True)], limit=1)
     if account:
         env['marketplace.job'].create({
             'name': 'Zortout Stock Sync',
             'job_type': 'sync_stock_from_zortout',
             'account_id': account.id,
             'payload': {
                 'warehouse_code': 'WH001',  # เปลี่ยนเป็น Warehouse Code ของคุณ
             },
             'state': 'pending',
         })
     ```

## 📝 Product Mapping

เมื่อ sync products จาก Zortout:
- **SKU** → `default_code` (Product SKU)
- **Name** → `name` (Product Name)
- **Sell Price** → `list_price` (Sale Price)
- **Purchase Price** → `standard_price` (Cost)
- **Barcode** → `barcode`
- **Stock** → Stock Quantity (ถ้า warehouse_code ถูกกำหนด)
- **Available Stock** → Available Quantity

## 🔍 ตรวจสอบผลลัพธ์

### ตรวจสอบ Products:
- ไปที่ **Inventory** > **Products**
- ควรเห็นสินค้าที่ sync จาก Zortout
- ตรวจสอบ SKU, Price, Stock

### ตรวจสอบ Stock:
- ไปที่ **Inventory** > **Products**
- เลือกสินค้า
- ดู **On Hand** quantity
- ควรตรงกับ Available Stock จาก Zortout

### ตรวจสอบ Jobs:
- ไปที่ **Marketplace** > **Jobs**
- ดู Job Status และ Result
- ตรวจสอบ Error Messages (ถ้ามี)

## ⚠️ Troubleshooting

### API Error:
- ตรวจสอบ Store Name, API Key, API Secret ถูกต้อง
- ตรวจสอบ Warehouse Code (ถ้าใช้)
- ตรวจสอบ Logs: `docker compose logs odoo | grep -i zortout`

### Products ไม่ sync:
- ตรวจสอบ Job Status และ Error Messages
- ตรวจสอบ Payload ถูกต้อง
- ตรวจสอบว่า Products ใน Zortout มี SKU หรือไม่

### Stock ไม่ sync:
- ตรวจสอบ Warehouse Code ถูกต้อง
- ตรวจสอบว่า Products มี default_code (SKU)
- ตรวจสอบว่า Warehouse Code ตรงกับ Zortout

## 📚 API Endpoints ที่ใช้

1. **GET /Product/GetProducts** - ดึงรายการสินค้า
2. **GET /Product/GetProductDetail** - ดึงรายละเอียดสินค้า
3. **POST /Product/UpdateProductStockList** - อัปเดตสต็อก (ถ้าต้องการ push กลับไป Zortout)

## 🎯 Next Steps

1. ✅ ตั้งค่า Zortout Account
2. ✅ ทดสอบดึงสินค้า
3. ✅ ทดสอบดึงสต็อก
4. ⚠️ ตั้งค่า Cron Job สำหรับ Realtime Sync
5. ⚠️ ตั้งค่า Product Bindings (ถ้าต้องการ sync กลับไป marketplace)

