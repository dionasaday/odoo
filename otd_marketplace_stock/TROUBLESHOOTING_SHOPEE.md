# Troubleshooting Shopee Integration

## Error: "Wrong sign"

### สาเหตุที่เป็นไปได้:

1. **Client Secret ไม่ถูกต้อง**
   - ตรวจสอบว่าใช้ Test API Partner Key สำหรับ test environment
   - ตรวจสอบว่าไม่มีช่องว่างหรือตัวอักษรพิเศษ

2. **Signature Calculation ผิด**
   - Base string: `partner_id + path + timestamp`
   - ไม่รวม redirect_uri ใน signature
   - ใช้ HMAC-SHA256

3. **redirect_uri ไม่ตรงกับ Shopee**
   - ตรวจสอบว่า redirect_uri ใน URL ตรงกับที่ตั้งใน Shopee Partner Center
   - ต้องใช้ HTTPS สำหรับ production

### วิธีตรวจสอบ:

**1. ตรวจสอบ Signature Calculation:**
```python
import hmac
import hashlib
import time

partner_id = 1100886
path = '/api/v2/shop/auth_partner'
timestamp = int(time.time())
client_secret = "shpk6b6174484e4f4e575a4f7a646644646a4a7077796a4f774c6b5257614b76"

base_string = f"{partner_id}{path}{timestamp}"
signature = hmac.new(
    client_secret.encode('utf-8'),
    base_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

print(f"Base: {base_string}")
print(f"Signature: {signature}")
```

**2. ตรวจสอบ Redirect URI:**
- Shopee Partner Center: ต้องตั้งค่า domain เท่านั้น (ไม่รวม path)
- Odoo: web.base.url ต้องเป็น HTTPS
- URL ที่สร้าง: redirect parameter ต้องตรงกับที่ตั้งใน Shopee

**3. ตรวจสอบ Parameters:**
- `partner_id`: ต้องตรงกับ Test Partner ID
- `timestamp`: ต้องเป็น current time
- `redirect`: ต้องเป็น full URL (https://...)
- `sign`: ต้องคำนวณจาก base_string ที่ถูกต้อง

## Error: "no timestamp"

- ตรวจสอบว่า timestamp parameter ถูกส่งไปใน URL
- ตรวจสอบว่า timestamp เป็น integer (ไม่ใช่ string)

## Error: Redirect URI mismatch

- ตรวจสอบว่า redirect_uri ตรงกับที่ตั้งใน Shopee Partner Center
- ตรวจสอบว่าใช้ HTTPS (ไม่ใช่ HTTP)
- ตรวจสอบว่า path `/marketplace/oauth/callback/shopee` ถูกต้อง

## Checklist

- [ ] Client ID (Partner ID) ถูกต้อง
- [ ] Client Secret (Partner Key) ถูกต้อง
- [ ] web.base.url ตั้งเป็น HTTPS URL
- [ ] Redirect URI ใน Shopee ตั้งเป็น domain เท่านั้น (ไม่รวม path)
- [ ] Signature calculation ถูกต้อง
- [ ] Timestamp เป็น current time
- [ ] URL parameters ครบถ้วน

## Debug Steps

1. **ตรวจสอบ URL ที่สร้าง:**
   - เปิด Marketplace Account
   - คลิก "Connect OAuth"
   - ดู URL ที่ถูกสร้าง
   - ตรวจสอบว่ามี timestamp, sign, redirect

2. **ทดสอบ Signature:**
   - ใช้ Python script ด้านบน
   - เปรียบเทียบกับ signature ใน URL

3. **ตรวจสอบ Odoo Logs:**
   ```bash
   docker compose logs odoo | grep -i shopee
   ```

4. **ทดสอบด้วย Postman/curl:**
   - สร้าง URL ด้วย signature ที่คำนวณเอง
   - ทดสอบว่า Shopee ยอมรับหรือไม่

