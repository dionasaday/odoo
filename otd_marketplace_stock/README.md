# OTD Marketplace Stock - Odoo 19 Module

โมดูล Odoo 19 สำหรับจัดการสต๊อกกลางและเชื่อมต่อมาร์เก็ตเพลส (Shopee, Lazada, TikTok Shop) คล้าย Zortout

## คุณสมบัติหลัก

- **Multi-Company & Multi-Store**: รองรับหลายบริษัทและหลายร้านต่อช่องทาง
- **Order Pull**: ดึงคำสั่งซื้อจากมาร์เก็ตเพลส → สร้าง sale.order + จองสต๊อก + ทำเอกสารส่งของ
- **Stock Push**: ซิงก์สต๊อกจาก Odoo → อัปเดตไปทุกมาร์เก็ตเพลส (กัน oversell)
- **SKU Mapping**: แม็พสินค้าระหว่าง product.product กับรายการบนมาร์เก็ตเพลส
- **Order Status**: รองรับสถานะออเดอร์/คืนสินค้า/ยกเลิก พร้อมบันทึกเหตุผล
- **Sync Rules**: บริหารกฎซิงก์ (buffer, minimum qty, rounding, exclude product)
- **Job Queue**: บันทึก Log/Retry/Dead-letter สำหรับงานที่ล้มเหลว
- **OAuth & Webhooks**: ตั้งค่า credential/OAuth/webhook ได้จาก Settings
- **Dashboard**: แดชบอร์ดสรุปยอดขาย/ออเดอร์ที่ติดค้าง/สต๊อกคงเหลือต่อช่องทาง

## การติดตั้ง

### 1. ติดตั้งโมดูล

```bash
# คัดลอกโมดูลไปยัง addons directory
cp -r otd_marketplace_stock /path/to/odoo/addons/

# หรือใช้ symbolic link
ln -s /path/to/otd_marketplace_stock /path/to/odoo/addons/

# อัปเดต app list
# ใน Odoo: Apps → Update Apps List → Search "OTD Marketplace Stock" → Install
```

### 2. ตั้งค่า Dependencies

โมดูลนี้ขึ้นอยู่กับ:
- `sale_management`
- `stock`
- `contacts`
- `mail`

### 3. ตั้งค่า Environment Variables (สำหรับ On-Premise/Synology)

สร้างไฟล์ `.env` หรือตั้งค่า environment variables:

```bash
# Marketplace API Base URLs (optional, มี default)
MARKETPLACE_SHOPEE_BASE_URL=https://partner.test-stable.shopeemobile.com/api/v2
MARKETPLACE_LAZADA_BASE_URL=https://api.lazada.com.my/rest
MARKETPLACE_TIKTOK_BASE_URL=https://open-api.tiktokglobalshop.com

# Odoo Base URL (สำหรับ OAuth callback)
ODOO_BASE_URL=https://your-odoo-instance.com
```

## การใช้งาน

### 1. สร้าง Marketplace Account

1. ไปที่ **Marketplace → Accounts**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Account Name**: ชื่อบัญชี
   - **Channel**: เลือก Shopee, Lazada, หรือ TikTok Shop
   - **Company**: เลือกบริษัท
   - **Client ID** และ **Client Secret**: จากมาร์เก็ตเพลส
4. คลิก **Connect OAuth** เพื่อเชื่อมต่อ OAuth

### 2. สร้าง Shop

1. ในหน้า Account → แท็บ **Shops**
2. คลิก **Add a line**
3. กรอก:
   - **Shop Name**: ชื่อร้าน
   - **External Shop ID**: Shop ID จากมาร์เก็ตเพลส
   - **Warehouse**: คลังสินค้าที่ใช้
   - **Sales Team**: ทีมขาย

### 3. แม็พสินค้า (Product Binding)

1. ไปที่ **Marketplace → Product Bindings**
2. คลิก **Create**
3. เลือก:
   - **Product**: สินค้าใน Odoo
   - **Shop**: ร้านที่ต้องการ
   - **External SKU**: SKU บนมาร์เก็ตเพลส
4. หรือใช้ **Bulk Binding Wizard** เพื่อสร้างหลายสินค้าพร้อมกัน

### 4. ตั้งค่า Sync Rules (Optional)

1. ไปที่ **Marketplace → Sync Rules**
2. สร้างกฎสำหรับ:
   - **Buffer Quantity**: ปริมาณที่หักจากสต๊อก
   - **Minimum Quantity**: ปริมาณต่ำสุดที่แสดงออนไลน์
   - **Rounding**: ปัดเศษ
   - **Exclude Push**: ไม่ push สต๊อก

### 5. ตรวจสอบ Jobs

1. ไปที่ **Marketplace → Jobs**
2. ดูสถานะงานที่กำลังรัน/ล้มเหลว
3. คลิก **Retry** สำหรับงานที่ล้มเหลว

### 6. Dashboard

ไปที่ **Marketplace → Dashboard** เพื่อดูสรุป:
- ยอดขายต่อช่องทาง
- ออเดอร์ที่ติดค้าง
- สต๊อกคงเหลือ

## การตั้งค่าบน Synology NAS

### วิธีที่ 1: Docker Compose

สร้างไฟล์ `docker-compose.yml`:

```yaml
version: '3.8'

services:
  odoo:
    image: odoo:19
    container_name: odoo_marketplace
    environment:
      - HOST=postgres
      - USER=odoo
      - PASSWORD=your_password
      - MARKETPLACE_SHOPEE_BASE_URL=https://partner.test-stable.shopeemobile.com/api/v2
      - MARKETPLACE_LAZADA_BASE_URL=https://api.lazada.com.my/rest
      - MARKETPLACE_TIKTOK_BASE_URL=https://open-api.tiktokglobalshop.com
    volumes:
      - ./addons:/mnt/extra-addons
      - ./config:/etc/odoo
    ports:
      - "8069:8069"
    depends_on:
      - postgres
  
  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_USER=odoo
      - POSTGRES_PASSWORD=your_password
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

รันด้วย:
```bash
docker-compose up -d
```

### วิธีที่ 2: Systemd Service

สร้างไฟล์ `/etc/systemd/system/odoo-marketplace.service`:

```ini
[Unit]
Description=Odoo Marketplace Service
After=network.target

[Service]
Type=simple
User=odoo
Group=odoo
WorkingDirectory=/opt/odoo
ExecStart=/opt/odoo/odoo-bin -c /opt/odoo/config/odoo.conf
Restart=always
RestartSec=10

Environment="MARKETPLACE_SHOPEE_BASE_URL=https://partner.test-stable.shopeemobile.com/api/v2"
Environment="MARKETPLACE_LAZADA_BASE_URL=https://api.lazada.com.my/rest"
Environment="MARKETPLACE_TIKTOK_BASE_URL=https://open-api.tiktokglobalshop.com"

[Install]
WantedBy=multi-user.target
```

Enable และ start service:
```bash
sudo systemctl enable odoo-marketplace.service
sudo systemctl start odoo-marketplace.service
```

## การตั้งค่า OAuth

### Shopee

1. สร้าง Partner Account ที่ [Shopee Partner Center](https://partner.shopeemobile.com/)
2. สร้าง Application และได้ **Client ID** และ **Client Secret**
3. ตั้งค่า Redirect URI: `https://your-odoo-instance.com/marketplace/oauth/callback/shopee`
4. ใส่ Client ID และ Client Secret ใน Marketplace Account
5. คลิก **Connect OAuth**

### Lazada

1. สร้าง Application ที่ [Lazada Open Platform](https://open.lazada.com/)
2. ได้ **App Key** และ **App Secret**
3. ตั้งค่า Redirect URI: `https://your-odoo-instance.com/marketplace/oauth/callback/lazada`
4. ใส่ใน Marketplace Account

### TikTok Shop

1. สร้าง Application ที่ [TikTok Shop Developer Portal](https://developers.tiktokshop.com/)
2. ได้ **App Key** และ **App Secret**
3. ตั้งค่า Redirect URI: `https://your-odoo-instance.com/marketplace/oauth/callback/tiktok`
4. ใส่ใน Marketplace Account

## Webhooks

### ตั้งค่า Webhook URL

สำหรับแต่ละช่องทาง:

- **Shopee**: `https://your-odoo-instance.com/marketplace/webhook/shopee/{shop_id}`
- **Lazada**: `https://your-odoo-instance.com/marketplace/webhook/lazada/{shop_id}`
- **TikTok**: `https://your-odoo-instance.com/marketplace/webhook/tiktok/{shop_id}`

### ตรวจสอบ Webhook

1. ไปที่ **Marketplace → Jobs**
2. กรองด้วย **Job Type = Webhook**
3. ดูสถานะและ error (ถ้ามี)

## Cron Jobs

โมดูลมี cron jobs อัตโนมัติ:

1. **Marketplace: Run Jobs** - รันทุก 1 นาที เพื่อประมวลผล job queue
2. **Marketplace: Pull Orders** - รันทุก 5 นาที เพื่อดึงออเดอร์ใหม่

สามารถปรับค่าได้ใน **Settings → Technical → Automation → Scheduled Actions**

## Troubleshooting

### ปัญหา: Token หมดอายุ

**แก้ไข**: คลิก **Refresh Token** ในหน้า Marketplace Account

### ปัญหา: Webhook ไม่ทำงาน

**ตรวจสอบ**:
1. Webhook URL ถูกต้องหรือไม่
2. Signature verification ผ่านหรือไม่ (ดูใน Jobs)
3. Firewall อนุญาต incoming connections หรือไม่

### ปัญหา: Stock ไม่ sync

**ตรวจสอบ**:
1. Product Binding ถูกต้องหรือไม่
2. Sync Rule มี exclude_push หรือไม่
3. Job Queue มี error หรือไม่

### ปัญหา: Order ไม่ถูกสร้าง SO

**ตรวจสอบ**:
1. Product Binding มีหรือไม่
2. Order state เป็น pending หรือไม่
3. ดู error ในหน้า Marketplace Order → Sync Info

## การพัฒนา

### โครงสร้างโมดูล

```
otd_marketplace_stock/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── marketplace_account.py
│   ├── marketplace_shop.py
│   ├── marketplace_product_binding.py
│   ├── marketplace_order.py
│   ├── sync_rule.py
│   ├── job_queue.py
│   ├── stock_sync.py
│   ├── adapters.py
│   ├── shopee_adapter.py
│   ├── lazada_adapter.py
│   └── tiktok_adapter.py
├── controllers/
│   ├── webhook.py
│   └── oauth_callback.py
├── views/
│   ├── menu.xml
│   ├── marketplace_account_views.xml
│   ├── marketplace_shop_views.xml
│   ├── product_binding_views.xml
│   ├── order_views.xml
│   ├── sync_rule_views.xml
│   ├── job_queue_views.xml
│   ├── dashboard_views.xml
│   └── res_config_settings_views.xml
├── security/
│   ├── ir.model.access.csv
│   └── ir_rule.xml
├── data/
│   ├── ir_cron_data.xml
│   └── sequences.xml
└── wizard/
    ├── bulk_binding_wizard.py
    └── order_repair_wizard.py
```

### การเพิ่ม Adapter ใหม่

1. สร้างไฟล์ใหม่ใน `models/` เช่น `new_adapter.py`
2. Inherit จาก `MarketplaceAdapter`
3. Implement abstract methods:
   - `_get_base_url()`
   - `get_authorize_url()`
   - `exchange_code()`
   - `refresh_access_token()`
   - `fetch_orders()`
   - `update_inventory()`
   - `verify_webhook()`
   - `parse_order_payload()`
4. Register ใน `models/__init__.py`:
   ```python
   from . import new_adapter
   adapters.MarketplaceAdapters.register_adapter('new_channel', new_adapter.NewAdapter)
   ```

## License

LGPL-3

## Author

OTD

## Support

สำหรับคำถามหรือปัญหา กรุณาติดต่อทีมพัฒนา

