# 🚀 Zortout Integration - Quick Start Guide

## 📋 ขั้นตอนการตั้งค่า (Step-by-Step)

### ✅ Step 1: เปิด Zortout Console

1. ไปที่ **https://secure.zortout.com/Integration/ApiReference**
2. Login เข้าสู่ระบบ Zortout
3. หน้า API Reference จะแสดง:
   - **Endpoint Url**: `https://open-api.zortout.com/v4`
   - **storename**: (Email ของคุณ)
   - **apikey**: (API Key)
   - **apisecret**: (API Secret)

### ✅ Step 2: คัดลอก API Credentials

จาก Zortout Console ให้คัดลอก:

1. **Store Name** (Email):
   - ตัวอย่าง: `supa.nattaphon@gmail.com`
   - คลิกปุ่ม **Copy** ข้างๆ Store Name

2. **API Key**:
   - ตัวอย่าง: `V9JPcSPlg3gerpw3BT/ZxR0PSUR7Lo10hedW4v6HZk=`
   - คลิกปุ่ม **Copy** ข้างๆ API Key

3. **API Secret**:
   - ตัวอย่าง: `Iv2QGNVPDXxz2LMnG6V8KlmcjCfzZsb5Lgp7Blq3F0=`
   - คลิกปุ่ม **Copy** ข้างๆ API Secret

### ✅ Step 3: ตั้งค่าใน Odoo

1. กลับไปที่ Odoo > **Marketplace** > **Accounts**
2. เปิด Account **Zortout** ที่สร้างไว้
3. ไปที่ Tab **"OAuth Configuration / API Credentials"**
4. วางข้อมูลที่คัดลอกมา:
   - **Store Name**: วาง Store Name (Email) ที่คัดลอกมา
   - **API Key**: วาง API Key ที่คัดลอกมา
   - **API Secret**: วาง API Secret ที่คัดลอกมา
5. **Save**

### ✅ Step 4: ตรวจสอบ Warehouse Code

1. ไปที่ **Inventory** > **Configuration** > **Warehouses**
2. ตรวจสอบ **Warehouse Code** ของ Warehouse ที่ต้องการใช้
   - ตัวอย่าง: `WH001`, `MAIN`, `CENTRAL`
3. จดไว้เพื่อใช้ในการ Sync Stock

### ✅ Step 5: ทดสอบการเชื่อมต่อ

#### วิธีที่ 1: ทดสอบดึงสินค้า (Products)

1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   ```
   Job Name: Sync Products from Zortout - Test
   Job Type: Sync Products from Zortout
   Account: Zortout (เลือก Account ที่สร้างไว้)
   Shop: (เว้นว่าง - ไม่ต้องเลือก)
   Payload (JSON):
   ```
   ```json
   {
     "fetch_all": true,
     "warehouse_code": "WH001",
     "filters": {
       "activestatus": 1
     }
   }
   ```
   **หมายเหตุ**: เปลี่ยน `WH001` เป็น Warehouse Code ของคุณ
4. คลิก **Save**
5. Job จะทำงานทันที (ถ้า State = Pending)
6. ตรวจสอบผลลัพธ์:
   - ไปที่ **Marketplace** > **Jobs**
   - เปิด Job ที่สร้าง
   - ดู **Result**:
     - `products_fetched`: จำนวนสินค้าที่ดึงมา
     - `products_created`: สินค้าใหม่ที่สร้าง
     - `products_updated`: สินค้าที่อัปเดต
   - ตรวจสอบ **Activity** log สำหรับ Error (ถ้ามี)

#### วิธีที่ 2: ทดสอบดึงสต็อก (Stock)

1. ไปที่ **Marketplace** > **Jobs**
2. คลิก **New**
3. กรอกข้อมูล:
   ```
   Job Name: Sync Stock from Zortout - Test
   Job Type: Sync Stock from Zortout
   Account: Zortout
   Shop: (เว้นว่าง)
   Payload (JSON):
   ```
   ```json
   {
     "warehouse_code": "WH001",
     "sku_list": ["P0001", "P0002"]
   }
   ```
   **หมายเหตุ**: 
   - เปลี่ยน `WH001` เป็น Warehouse Code ของคุณ
   - `sku_list` เป็น optional - ปล่อยว่างเพื่อ sync ทั้งหมด
4. คลิก **Save**
5. ตรวจสอบผลลัพธ์:
   - ดู **Result**:
     - `products_synced`: จำนวนสินค้าที่ sync
     - `stocks_updated`: จำนวนสต็อกที่อัปเดต
   - ไปที่ **Inventory** > **Products** เพื่อตรวจสอบ Stock

## 🔍 ตรวจสอบผลลัพธ์

### ตรวจสอบ Products:
1. ไปที่ **Inventory** > **Products**
2. ควรเห็นสินค้าที่ sync จาก Zortout
3. ตรวจสอบ:
   - **SKU** (default_code) ตรงกับ Zortout
   - **Price** (list_price) ตรงกับ Zortout
   - **Cost** (standard_price) ตรงกับ Zortout

### ตรวจสอบ Stock:
1. ไปที่ **Inventory** > **Products**
2. เลือกสินค้าที่ sync
3. ดู **On Hand** quantity
4. ควรตรงกับ **Available Stock** จาก Zortout

## ⚠️ Troubleshooting

### ❌ API Error: "Wrong credentials"
**แก้ไข**: 
- ตรวจสอบ Store Name, API Key, API Secret ถูกต้อง
- ตรวจสอบว่า Copy มาครบถ้วน (ไม่มี space ข้างหน้า/หลัง)
- ตรวจสอบว่า Account Zortout ยัง Active อยู่

### ❌ Products ไม่ sync
**แก้ไข**:
- ตรวจสอบ Job Status และ Error Messages
- ตรวจสอบ Payload ถูกต้อง (JSON format)
- ตรวจสอบ Warehouse Code ถูกต้อง
- ตรวจสอบว่า Products ใน Zortout มี SKU หรือไม่

### ❌ Stock ไม่ sync
**แก้ไข**:
- ตรวจสอบ Warehouse Code ถูกต้อง
- ตรวจสอบว่า Products มี default_code (SKU) ใน Odoo
- ตรวจสอบว่า Warehouse Code ตรงกับที่ตั้งค่าใน Zortout

### 📋 ตรวจสอบ Logs:
```bash
docker compose logs odoo | grep -i zortout
```

## 🎯 Payload Examples

### ดึงสินค้าทั้งหมด:
```json
{
  "fetch_all": true,
  "warehouse_code": "WH001",
  "filters": {
    "activestatus": 1
  }
}
```

### ดึงสินค้าตาม SKU:
```json
{
  "fetch_all": false,
  "page": 1,
  "limit": 100,
  "filters": {
    "searchsku": "P0001",
    "activestatus": 1
  }
}
```

### Sync Stock ทั้งหมด:
```json
{
  "warehouse_code": "WH001"
}
```

### Sync Stock เฉพาะบาง SKU:
```json
{
  "warehouse_code": "WH001",
  "sku_list": ["P0001", "P0002", "P0003"]
}
```

## ✅ Checklist

- [ ] สร้าง Zortout Account ใน Odoo
- [ ] ตั้งค่า Store Name, API Key, API Secret
- [ ] ตรวจสอบ Warehouse Code
- [ ] ทดสอบดึงสินค้า (Products)
- [ ] ทดสอบดึงสต็อก (Stock)
- [ ] ตรวจสอบ Products ใน Inventory
- [ ] ตรวจสอบ Stock quantities

## 🔄 ตั้งค่า Cron Job สำหรับ Realtime Sync (Optional)

หากต้องการให้ sync Stock อัตโนมัติทุก 5 นาที:

1. ไปที่ **Settings** > **Technical** > **Automation** > **Scheduled Actions**
2. คลิก **New**
3. กรอกข้อมูล:
   ```
   Name: Zortout: Sync Stock Realtime
   Model: marketplace.job
   Interval: 5 minutes
   Code:
   ```
   ```python
   account = env['marketplace.account'].search([
       ('channel', '=', 'zortout'),
       ('active', '=', True),
       ('sync_enabled', '=', True)
   ], limit=1)
   
   if account:
       env['marketplace.job'].create({
           'name': 'Zortout Stock Sync - Auto',
           'job_type': 'sync_stock_from_zortout',
           'account_id': account.id,
           'payload': {
               'warehouse_code': 'WH001',  # เปลี่ยนเป็น Warehouse Code ของคุณ
           },
           'state': 'pending',
       })
   ```
4. **Save** และ **Activate**

---

**💡 Tips:**
- เริ่มต้นด้วยการ sync Products ก่อน เพื่อให้มี Products ในระบบ
- จากนั้นค่อย sync Stock
- ตั้งค่า Cron Job สำหรับ Stock Sync เพื่อให้ได้ Realtime data
- ตรวจสอบ Logs อย่างสม่ำเสมอเพื่อพบปัญหาได้เร็ว

