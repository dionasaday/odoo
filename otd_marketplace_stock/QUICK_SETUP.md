# Quick Setup Guide - Shopee Integration

## ขั้นตอนด่วน (5 นาที)

### 1. เริ่ม ngrok (Terminal ใหม่)

```bash
cd /Users/nattaphonsupa/odoo19
./start_ngrok.sh
```

หรือเริ่มเอง:
```bash
ngrok http 8069
```

**คัดลอก HTTPS URL** ที่ได้ (เช่น: `https://abc123.ngrok.io`)

### 2. ตั้งค่าใน Shopee Partner Center

1. ไปที่ Shopee Partner Center > App Management > Edit APP
2. ใน **Test Redirect URL Domain** ใส่:
   ```
   https://YOUR_NGROK_URL.ngrok.io/marketplace/oauth/callback/shopee
   ```
   ตัวอย่าง: `https://abc123.ngrok.io/marketplace/oauth/callback/shopee`
3. **บันทึก**

### 3. ตั้งค่า Odoo Base URL

**วิธีที่ 1: ผ่าน Odoo UI**
1. ไปที่ Settings > Technical > Parameters > System Parameters
2. ค้นหา `web.base.url`
3. แก้ไข Value เป็น: `https://YOUR_NGROK_URL.ngrok.io`
4. บันทึก

**วิธีที่ 2: ผ่าน config file**
แก้ไข `config/odoo.conf`:
```ini
web.base.url = https://YOUR_NGROK_URL.ngrok.io
```
แล้ว restart Odoo

### 4. สร้าง Shopee Account ใน Odoo

1. ไปที่ **Marketplace > Accounts**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Account Name**: Shopee Thailand
   - **Channel**: Shopee
   - **Client ID**: จาก Shopee Partner Center (Partner ID)
   - **Client Secret**: จาก Shopee Partner Center (Partner Key)
4. **บันทึก**

### 5. เชื่อมต่อ OAuth

1. เปิด Marketplace Account ที่สร้างไว้
2. คลิกปุ่ม **"Connect OAuth"** หรือ **"Authorize"**
3. อนุมัติในหน้า Shopee
4. ตรวจสอบว่า Access Token ถูกบันทึก

### 6. สร้าง Shop

1. ไปที่ **Marketplace > Shops**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Shop Name**: ชื่อร้าน
   - **Account**: เลือก Shopee account
   - **External Shop ID**: Shop ID จาก Shopee
4. **บันทึก**

## ✅ เสร็จสิ้น!

ตอนนี้พร้อมทดสอบ:
- ดึง Orders จาก Shopee
- Push Stock ไปยัง Shopee

## ⚠️ หมายเหตุสำคัญ

1. **ngrok URL เปลี่ยนทุกครั้งที่ restart**
   - ต้องอัปเดต Shopee และ Odoo ทุกครั้ง

2. **สำหรับ Production:**
   - ใช้ domain จริง
   - ตั้งค่า SSL certificate
   - ใช้ Live Redirect URL Domain

3. **Troubleshooting:**
   - ตรวจสอบ ngrok ว่า running: `curl http://localhost:4040`
   - ตรวจสอบ Odoo logs: `docker compose logs odoo`
   - ตรวจสอบ web.base.url ตรงกับ ngrok URL

