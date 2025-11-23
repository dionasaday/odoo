# วิธีตรวจสอบและแก้ไข Shopee OAuth Setup

## ปัญหา: "no timestamp" error

ถ้ายังพบ error "no timestamp" หลังจาก upgrade module แล้ว ให้ทำตามขั้นตอนนี้:

### 1. ตรวจสอบว่า Code ถูก Update แล้ว

**วิธีที่ 1: ตรวจสอบผ่าน Odoo Shell**
1. ไปที่ Settings > Technical > Database Structure > Odoo Shell
2. รันโค้ดนี้:
```python
from odoo.addons.otd_marketplace_stock.models import shopee_adapter
import inspect

# Check get_authorize_url method
method = shopee_adapter.ShopeeAdapter.get_authorize_url
source = inspect.getsource(method)
print("Method contains 'timestamp':", 'timestamp' in source)
print("Method contains 'sign':", 'sign' in source)
```

**วิธีที่ 2: ตรวจสอบไฟล์โดยตรง**
```bash
docker compose exec odoo grep -n "timestamp" /mnt/extra-addons/otd_marketplace_stock/models/shopee_adapter.py
```

### 2. Upgrade Module

**วิธีที่ 1: ผ่าน UI**
1. ไปที่ Apps
2. ค้นหา "OTD Marketplace Stock"
3. คลิก "Upgrade"

**วิธีที่ 2: ผ่าน Command Line**
```bash
docker compose exec odoo odoo -u otd_marketplace_stock -d your_database_name --stop-after-init
docker compose restart odoo
```

### 3. Restart Odoo

```bash
docker compose restart odoo
```

### 4. ทดสอบ OAuth URL Generation

**ผ่าน Odoo Shell:**
```python
env = self.env
account = env['marketplace.account'].search([('channel', '=', 'shopee')], limit=1)

if account:
    adapter = account._get_adapter()
    auth_url = adapter.get_authorize_url()
    print(f"Generated URL: {auth_url}")
    
    # Check if URL contains timestamp
    if 'timestamp=' in auth_url:
        print("✅ URL contains timestamp")
    else:
        print("❌ URL missing timestamp")
        
    # Check if URL contains sign
    if 'sign=' in auth_url:
        print("✅ URL contains signature")
    else:
        print("❌ URL missing signature")
else:
    print("❌ No Shopee account found")
```

### 5. ตรวจสอบ Parameters ที่ถูกต้อง

URL ที่ถูกต้องควรมี parameters เหล่านี้:
- `partner_id`: Partner ID (Client ID)
- `redirect`: Redirect URI (full URL)
- `timestamp`: Unix timestamp
- `sign`: HMAC-SHA256 signature

**ตัวอย่าง URL ที่ถูกต้อง:**
```
https://partner.test-stable.shopeemobile.com/api/v2/shop/auth_partner?partner_id=1100886&redirect=https%3A%2F%2F43276ed5d1e3.ngrok-free.app%2Fmarketplace%2Foauth%2Fcallback%2Fshopee&timestamp=1762346091&sign=abc123...
```

### 6. Troubleshooting

**ถ้ายังมี error:**
1. ตรวจสอบว่า Client ID และ Client Secret ถูกต้อง
2. ตรวจสอบว่า web.base.url ถูกตั้งค่าแล้ว
3. ตรวจสอบ Odoo logs:
   ```bash
   docker compose logs odoo | grep -i shopee
   ```
4. ตรวจสอบว่า module ถูก upgrade แล้ว:
   ```sql
   SELECT state FROM ir_module_module WHERE name = 'otd_marketplace_stock';
   ```

### 7. Manual Test

ทดสอบสร้าง URL โดยตรง:
```python
import time
import hmac
import hashlib
import urllib.parse

partner_id = 1100886  # Your Partner ID
client_secret = "your_secret"  # Your Partner Key
redirect_uri = "https://43276ed5d1e3.ngrok-free.app/marketplace/oauth/callback/shopee"
timestamp = int(time.time())
path = '/api/v2/shop/auth_partner'

params_dict = {
    'partner_id': partner_id,
    'redirect': redirect_uri,
    'timestamp': timestamp,
}

# Generate signature
base_string = f"{partner_id}{path}{timestamp}"
signature = hmac.new(
    client_secret.encode('utf-8'),
    base_string.encode('utf-8'),
    hashlib.sha256
).hexdigest()

params_dict['sign'] = signature

# Build URL
auth_url = f"https://partner.test-stable.shopeemobile.com{path}"
auth_url += '?' + urllib.parse.urlencode(params_dict)

print(auth_url)
```

## หมายเหตุ

- Shopee API ต้องการ timestamp และ signature สำหรับทุก authorization request
- Signature ต้องคำนวณจาก: `partner_id + path + timestamp`
- Timestamp ต้องเป็น Unix timestamp (integer)
- URL จะ expire หลังจาก timestamp ผ่านไป (ปกติประมาณ 5-10 นาที)

