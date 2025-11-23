# วิธีตรวจสอบและตั้งค่า Zortout API Credentials

## ข้อมูลจาก Zortout API Reference

จากภาพที่คุณส่งมา:
- **Store Name**: `supa.nattaphon@gmail.com`
- **API Key**: `V9JPcSPlg3gerpw3BT/ZXR0PSUR7Lo10hedW4v6HZk=`
- **API Secret**: `Iv2QGNVPDXxz2LMnG6V8KlmcjCfzZsb5Lgp7Blq3F0=`
- **Endpoint**: `https://open-api.zortout.com/v4`
- **คลังสินค้า**: `คลังสินค้าหลัก` (Main Warehouse)

## การ Mapping ใน Odoo

ใน Odoo Marketplace Account:
- **Store Name** → เก็บใน field `Client ID`
- **API Key** → เก็บใน field `Client Secret`
- **API Secret** → เก็บใน field `Access Token`

## ขั้นตอนการตั้งค่า

1. ไปที่ **Marketplace > Accounts > Zortout**
2. ตรวจสอบและอัปเดต:
   - **Store Name** (Client ID): `supa.nattaphon@gmail.com`
   - **API Key** (Client Secret): `V9JPcSPlg3gerpw3BT/ZXR0PSUR7Lo10hedW4v6HZk=`
   - **API Secret** (Access Token): `Iv2QGNVPDXxz2LMnG6V8KlmcjCfzZsb5Lgp7Blq3F0=`

## ตรวจสอบ Warehouse Code

จาก Zortout API Reference แสดงว่า:
- คลังสินค้า: `คลังสินค้าหลัก` (Main Warehouse)

แต่ใน Odoo เราใช้ warehouse code `WHNON` ซึ่งอาจไม่ตรงกัน

### วิธีตรวจสอบ Warehouse Code ที่ถูกต้อง:

1. เปิด Zortout
2. ไปที่ Warehouse Management
3. ตรวจสอบว่า warehouse code ของ "คลังสินค้าหลัก" คืออะไร
4. อัปเดต Stock Location ใน Odoo ให้ตรงกับ warehouse code ที่ถูกต้อง

## ทดสอบการเชื่อมต่อ

หลังจากอัปเดต credentials แล้ว:

1. ไปที่ **Marketplace > Accounts > Zortout**
2. กดปุ่ม **"ดึงสต็อกสินค้า"**
3. ตรวจสอบ logs:
   ```bash
   docker compose exec odoo tail -f /var/log/odoo/odoo.log | grep -E "(Zortout|API|Access Denied|resCode)"
   ```

## ปัญหาที่อาจพบ

### 1. Access Denied (resCode: 100)
- **สาเหตุ**: API credentials ไม่ถูกต้อง
- **วิธีแก้**: ตรวจสอบว่า Store Name, API Key, และ API Secret ตรงกับที่เห็นใน Zortout API Reference

### 2. No products found
- **สาเหตุ**: Warehouse code ไม่ถูกต้อง หรือไม่มีสินค้าใน warehouse นั้น
- **วิธีแก้**: ตรวจสอบ warehouse code ใน Zortout และอัปเดตใน Odoo

### 3. Warehouse not found
- **สาเหตุ**: Warehouse code ใน Odoo ไม่ตรงกับใน Zortout
- **วิธีแก้**: ตรวจสอบ warehouse code ใน Zortout และอัปเดต Stock Location ใน Odoo

