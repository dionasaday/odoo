# คู่มือการเชื่อมต่อ Shopee

## ขั้นตอนการตั้งค่า Shopee Account

### 1. สร้าง Marketplace Account

1. ไปที่ **Marketplace > Accounts**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Account Name**: ชื่อ account (เช่น "Shopee Thailand")
   - **Channel**: เลือก **Shopee**
   - **Company**: เลือกบริษัทที่ต้องการ
   - **Client ID**: Partner ID จาก Shopee Partner Center
   - **Client Secret**: Partner Key จาก Shopee Partner Center

### 2. ตั้งค่า OAuth Redirect URI

ใน Shopee Partner Center ต้องตั้งค่า Redirect URI:
```
https://your-odoo-domain.com/marketplace/oauth/callback/shopee
```

### 3. เชื่อมต่อ OAuth

1. เปิด Marketplace Account ที่สร้างไว้
2. ตรวจสอบว่า **Client ID** และ **Client Secret** ถูกต้อง
3. คลิกปุ่ม **Connect OAuth** (หรือ **Authorize**)
4. ระบบจะเปิดหน้า Shopee Authorization
5. อนุมัติการเชื่อมต่อ
6. ระบบจะ redirect กลับมาพร้อม access token

### 4. สร้าง Shop

หลังจากเชื่อมต่อ OAuth สำเร็จ:

1. ไปที่ **Marketplace > Shops**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Shop Name**: ชื่อร้านค้า
   - **Account**: เลือก Shopee account ที่เชื่อมต่อแล้ว
   - **External Shop ID**: Shop ID จาก Shopee (หาได้จาก Shopee API หรือ Partner Center)
   - **Warehouse**: เลือก warehouse ที่ใช้สำหรับคำสั่งซื้อจากร้านนี้
   - **Sales Team**: เลือก sales team (ถ้ามี)

### 5. Mapping Products (SKU Binding)

1. ไปที่ **Marketplace > Product Bindings**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Product**: เลือกสินค้าใน Odoo
   - **Shop**: เลือก Shopee shop
   - **External SKU**: SKU ที่ใช้ใน Shopee
   - **External Product ID**: Product ID จาก Shopee (ถ้ามี)

### 6. ตั้งค่า Sync Rules (ถ้าต้องการ)

1. ไปที่ **Marketplace > Sync Rules**
2. ตั้งค่า buffer quantity, minimum quantity, rounding ตามต้องการ

## การทดสอบการเชื่อมต่อ

### ทดสอบ OAuth

1. เปิด Marketplace Account
2. คลิก **Connect OAuth**
3. ตรวจสอบว่า redirect ไปหน้า Shopee และกลับมาสำเร็จ
4. ตรวจสอบว่า **Access Token** ถูกบันทึกไว้

### ทดสอบดึง Orders

1. ไปที่ **Marketplace > Jobs**
2. สร้าง job ใหม่:
   - **Job Type**: `pull_orders`
   - **Account**: เลือก Shopee account
   - **Shop**: เลือก shop
   - **Payload**: `{"since": "2024-01-01T00:00:00"}`
3. รอให้ job ทำงาน (หรือรัน cron job)
4. ตรวจสอบ **Marketplace > Orders** ว่ามี orders ใหม่

### ทดสอบ Push Stock

1. ไปที่ **Marketplace > Product Bindings**
2. เปิด product binding ที่ต้องการ
3. คลิกปุ่ม **Push Stock**
4. ตรวจสอบ **Last Stock Push At** ว่าอัปเดต
5. ตรวจสอบ stock ใน Shopee ว่าถูกอัปเดต

## หมายเหตุสำคัญ

### Shopee API Environment

- **Test Environment**: `https://partner.test-stable.shopeemobile.com/api/v2`
- **Production Environment**: `https://partner.shopeemobile.com/api/v2`

ตั้งค่า base URL ผ่าน **Settings > Technical > Parameters > System Parameters**:
- Key: `marketplace.shopee.base_url`
- Value: URL ของ environment ที่ต้องการ

### Shopee API Requirements

1. **HMAC Signature**: ทุก request ต้องมี signature ที่ถูกต้อง
2. **Rate Limiting**: Shopee มี rate limit ตรวจสอบ response 429
3. **Shop ID**: ต้องมี Shop ID สำหรับทุก operation

### Troubleshooting

#### OAuth ไม่สำเร็จ
- ตรวจสอบ Client ID และ Client Secret
- ตรวจสอบ Redirect URI ใน Shopee Partner Center
- ตรวจสอบ Odoo base URL ใน Settings

#### API Request Failed
- ตรวจสอบ access token ว่ายัง valid หรือไม่
- ตรวจสอบ HMAC signature
- ตรวจสอบ Odoo logs สำหรับ error details

#### Orders ไม่ถูกดึง
- ตรวจสอบว่า Shop ID ถูกต้อง
- ตรวจสอบว่า time range ถูกต้อง
- ตรวจสอบ job queue สำหรับ errors

## API Documentation

อ้างอิง Shopee Partner API Documentation:
- [Shopee Partner API](https://open.shopee.com/documents?version=1)

