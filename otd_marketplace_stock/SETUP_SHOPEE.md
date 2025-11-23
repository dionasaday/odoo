# คู่มือการตั้งค่า Shopee Integration

## ขั้นตอนการตั้งค่า

### 1. ตั้งค่า Redirect URL ใน Shopee Partner Center

#### วิธีที่ 1: ใช้ ngrok (แนะนำสำหรับการทดสอบ)

**1.1 ติดตั้ง ngrok:**
```bash
# macOS
brew install ngrok

# หรือดาวน์โหลดจาก https://ngrok.com/download
```

**1.2 เริ่ม ngrok:**
```bash
ngrok http 8069
```

**1.3 คัดลอก HTTPS URL:**
- จะได้ URL ประมาณ: `https://abc123.ngrok.io`
- ใช้ URL นี้ใน Shopee: `https://abc123.ngrok.io/marketplace/oauth/callback/shopee`

**1.4 ตั้งค่าใน Shopee Partner Center:**
- Test Redirect URL Domain: `https://abc123.ngrok.io/marketplace/oauth/callback/shopee`

**หมายเหตุ:** ngrok URL จะเปลี่ยนทุกครั้งที่ restart (เว้นแต่จะใช้ paid plan)

#### วิธีที่ 2: ใช้ IP Address (สำหรับ local network)

**1.1 หา IP Address ของเครื่อง:**
```bash
# macOS/Linux
ifconfig | grep "inet " | grep -v 127.0.0.1

# หรือ
ipconfig getifaddr en0
```

**1.2 ตั้งค่าใน Shopee:**
- Test Redirect URL Domain: `http://YOUR_IP:8069/marketplace/oauth/callback/shopee`
- ตัวอย่าง: `http://192.168.1.100:8069/marketplace/oauth/callback/shopee`

**หมายเหตุ:** วิธีนี้ใช้ได้เฉพาะใน local network เท่านั้น

#### วิธีที่ 3: ใช้ Domain จริง (สำหรับ production)

**1.1 ตั้งค่า DNS:**
- ชี้ domain ไปที่ Odoo server

**1.2 ตั้งค่า SSL Certificate:**
- ใช้ Let's Encrypt หรือ certificate อื่น

**1.3 ตั้งค่าใน Shopee:**
- Live Redirect URL Domain: `https://yourdomain.com/marketplace/oauth/callback/shopee`

### 2. ตั้งค่า Odoo Base URL

**2.1 ไปที่ Settings > Technical > Parameters > System Parameters**

**2.2 ตรวจสอบหรือสร้าง parameter:**
- Key: `web.base.url`
- Value: URL ที่ใช้ใน Shopee (เช่น `https://abc123.ngrok.io` หรือ `http://YOUR_IP:8069`)

**หรือตั้งค่าผ่าน config file:**
```ini
[options]
# ... existing config ...
web.base.url = https://abc123.ngrok.io
```

### 3. สร้าง Shopee Marketplace Account ใน Odoo

**3.1 ไปที่ Marketplace > Accounts**

**3.2 คลิก Create และกรอกข้อมูล:**
- **Account Name**: เช่น "Shopee Thailand"
- **Channel**: เลือก "Shopee"
- **Company**: เลือกบริษัท
- **Client ID**: Partner ID จาก Shopee Partner Center
- **Client Secret**: Partner Key จาก Shopee Partner Center

**3.3 บันทึก**

### 4. เชื่อมต่อ OAuth

**4.1 เปิด Marketplace Account ที่สร้างไว้**

**4.2 ตรวจสอบว่า:**
- Client ID และ Client Secret ถูกต้อง
- web.base.url ถูกตั้งค่าแล้ว

**4.3 คลิกปุ่ม "Connect OAuth" หรือ "Authorize"**

**4.4 ระบบจะ:**
- เปิดหน้า Shopee Authorization
- ขออนุมัติการเชื่อมต่อ
- Redirect กลับมาพร้อม authorization code
- Exchange code เป็น access token อัตโนมัติ

**4.5 ตรวจสอบว่า:**
- Access Token ถูกบันทึก
- Refresh Token ถูกบันทึก
- Access Token Expires At ถูกตั้งค่า

### 5. สร้าง Shop

**5.1 ไปที่ Marketplace > Shops**

**5.2 คลิก Create และกรอกข้อมูล:**
- **Shop Name**: ชื่อร้านค้า
- **Account**: เลือก Shopee account ที่เชื่อมต่อแล้ว
- **External Shop ID**: Shop ID จาก Shopee
  - หาได้จาก Shopee API หรือ Partner Center
- **Warehouse**: เลือก warehouse ที่ใช้สำหรับ orders
- **Sales Team**: เลือก sales team (optional)

**5.3 บันทึก**

### 6. Mapping Products (SKU Binding)

**6.1 ไปที่ Marketplace > Product Bindings**

**6.2 คลิก Create และกรอกข้อมูล:**
- **Product**: เลือกสินค้าใน Odoo
- **Shop**: เลือก Shopee shop
- **External SKU**: SKU ที่ใช้ใน Shopee
- **External Product ID**: Product ID จาก Shopee (optional)

**6.3 บันทึก**

### 7. ทดสอบการเชื่อมต่อ

#### ทดสอบ OAuth
1. เปิด Marketplace Account
2. คลิก "Connect OAuth"
3. ตรวจสอบว่า redirect สำเร็จและ token ถูกบันทึก

#### ทดสอบดึง Orders
1. ไปที่ Marketplace > Jobs
2. สร้าง job:
   - Job Type: `pull_orders`
   - Account: เลือก Shopee account
   - Shop: เลือก shop
   - Payload: `{"since": "2024-01-01T00:00:00"}`
3. รอให้ job ทำงาน
4. ตรวจสอบ Marketplace > Orders

#### ทดสอบ Push Stock
1. ไปที่ Marketplace > Product Bindings
2. เปิด product binding
3. คลิก "Push Stock"
4. ตรวจสอบ stock ใน Shopee

## Troubleshooting

### OAuth ไม่สำเร็จ
- ตรวจสอบ Client ID และ Client Secret
- ตรวจสอบ Redirect URL ใน Shopee ตรงกับ Odoo base URL
- ตรวจสอบ web.base.url ใน Odoo
- ดู Odoo logs สำหรับ error details

### API Request Failed
- ตรวจสอบ access token ว่ายัง valid
- ตรวจสอบ Shop ID ถูกต้อง
- ตรวจสอบ HMAC signature
- ดู Odoo logs

### Orders ไม่ถูกดึง
- ตรวจสอบ Shop ID
- ตรวจสอบ time range
- ตรวจสอบ job queue สำหรับ errors

## ข้อมูลเพิ่มเติม

- Shopee Partner API: https://open.shopee.com/documents
- Shopee Test Environment: https://partner.test-stable.shopeemobile.com
- Shopee Production: https://partner.shopeemobile.com

