# คู่มือการเชื่อมต่อ WooCommerce

## ภาพรวม

WooCommerce integration ใช้ WooCommerce REST API เพื่อ:
- ดึง orders จาก WooCommerce store
- อัพเดท stock quantity ใน WooCommerce
- รับ webhooks จาก WooCommerce

## ขั้นตอนการตั้งค่า

### 1. สร้าง API Keys ใน WooCommerce

1. เข้าสู่ระบบ WooCommerce Admin
2. ไปที่ **WooCommerce > Settings > Advanced > REST API**
3. คลิก **Add Key**
4. กรอกข้อมูล:
   - **Description**: เช่น "Odoo Integration"
   - **User**: เลือก user ที่มีสิทธิ์ (แนะนำ: Administrator)
   - **Permissions**: เลือก **Read/Write** (ต้องใช้ Read/Write เพื่ออัพเดท stock)
5. คลิก **Generate API Key**
6. **บันทึกข้อมูลต่อไปนี้** (จะแสดงครั้งเดียว):
   - **Consumer Key**: เช่น `ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`
   - **Consumer Secret**: เช่น `cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### 2. สร้าง Marketplace Account ใน Odoo

1. ไปที่ **Marketplace > Accounts**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Account Name**: ชื่อ account (เช่น "WooCommerce Store")
   - **Channel**: เลือก **WooCommerce**
   - **Company**: เลือกบริษัทที่ต้องการ
   - **Store URL**: **ใส่ Store URL** (เช่น `https://yourstore.com`)
     - ⚠️ **สำคัญ**: ใส่ URL ของ WooCommerce store
   - **Consumer Key**: **ใส่ Consumer Key** (เช่น `ck_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
     - ⚠️ **สำคัญ**: ใส่ Consumer Key ที่ได้จาก WooCommerce
   - **Consumer Secret**: **ใส่ Consumer Secret** (เช่น `cs_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`)
     - ⚠️ **สำคัญ**: ใส่ Consumer Secret ที่ได้จาก WooCommerce
4. **Save**

### 4. สร้าง Shop

1. ในหน้า Marketplace Account → แท็บ **Shops**
2. คลิก **Add a line**
3. กรอกข้อมูล:
   - **Shop Name**: ชื่อร้าน (เช่น "Main Store")
   - **External Shop ID**: ใส่ `1` (WooCommerce มักมี shop เดียว)
   - **Warehouse**: เลือก warehouse ที่ใช้สำหรับ orders
   - **Sales Team**: เลือก sales team (optional)
4. **Save**

### 5. Mapping Products (SKU Binding)

1. ไปที่ **Marketplace > Product Bindings**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Product**: เลือกสินค้าใน Odoo
   - **Shop**: เลือก WooCommerce shop
   - **External SKU**: SKU ที่ใช้ใน WooCommerce
   - **External Product ID**: Product ID จาก WooCommerce (optional)
4. **Save**

## การใช้งาน

### ดึง Orders จาก WooCommerce

1. ไปที่ **Marketplace > Jobs**
2. คลิก **Create**
3. กรอกข้อมูล:
   - **Job Name**: เช่น "Pull Orders from WooCommerce"
   - **Job Type**: เลือก **Pull Orders**
   - **Account**: เลือก WooCommerce account
   - **Shop**: เลือก shop
   - **Payload**: 
     ```json
     {
       "since": "2024-01-01T00:00:00"
     }
     ```
4. **Save** และรอให้ job ทำงาน
5. ตรวจสอบ **Marketplace > Orders**

### อัพเดท Stock ใน WooCommerce

1. ไปที่ **Marketplace > Product Bindings**
2. เปิด product binding ที่ต้องการ
3. คลิก **Push Stock**
4. ตรวจสอบ stock ใน WooCommerce

### ตั้งค่า Auto Sync Orders (Optional)

1. ไปที่ **Marketplace > Accounts > WooCommerce Account**
2. ตรวจสอบว่า **Sync Enabled** ถูกเลือก
3. ระบบจะดึง orders อัตโนมัติตาม cron job ที่ตั้งค่าไว้

## Troubleshooting

### Error: "Store URL is required for WooCommerce"

**สาเหตุ**: ไม่ได้ใส่ Store URL ใน Client ID field

**แก้ไข**: 
- ตรวจสอบว่า Client ID field มี Store URL (เช่น `https://yourstore.com`)
- ไม่ใช่ Consumer Key

### Error: "Consumer Secret is required for WooCommerce API"

**สาเหตุ**: ไม่ได้ใส่ Consumer Secret ใน Client Secret field

**แก้ไข**:
- ตรวจสอบว่า Client Secret field มี Consumer Secret จาก WooCommerce
- Consumer Secret ควรขึ้นต้นด้วย `cs_`

### Error: "401 Unauthorized" หรือ "403 Forbidden"

**สาเหตุ**: API keys ไม่ถูกต้องหรือไม่มีสิทธิ์

**แก้ไข**:
1. ตรวจสอบ Consumer Key และ Consumer Secret ใน WooCommerce
2. ตรวจสอบว่า API key มีสิทธิ์ **Read/Write**
3. ตรวจสอบว่า user ที่สร้าง API key มีสิทธิ์ Administrator

### Error: "Product with SKU not found"

**สาเหตุ**: SKU ใน WooCommerce ไม่ตรงกับ External SKU ใน Product Binding

**แก้ไข**:
1. ตรวจสอบ SKU ใน WooCommerce (Product > Edit > SKU)
2. ตรวจสอบ External SKU ใน Product Binding
3. ตรวจสอบว่า SKU ตรงกัน (case-sensitive)

### Orders ไม่ถูกดึงมา

**สาเหตุ**: อาจเป็นเพราะ:
- API keys ไม่ถูกต้อง
- Store URL ไม่ถูกต้อง
- ไม่มี orders ในช่วงเวลาที่กำหนด

**แก้ไข**:
1. ทดสอบ API connection:
   - ไปที่ **Marketplace > Accounts > WooCommerce Account**
   - ตรวจสอบว่าไม่มี error messages
2. ตรวจสอบ logs:
   ```bash
   docker compose logs odoo | grep -i woocommerce
   ```
3. ทดสอบดึง orders ด้วย date range ที่กว้างขึ้น

## API Endpoints ที่ใช้

- `GET /wp-json/wc/v3/orders` - ดึง orders
- `PUT /wp-json/wc/v3/products/{id}` - อัพเดท product (stock)
- `GET /wp-json/wc/v3/products` - ค้นหา product โดย SKU

## หมายเหตุ

- WooCommerce **ไม่ใช้ OAuth** - ใช้ API keys (Consumer Key/Secret) แทน
- ไม่ต้องกดปุ่ม "Connect OAuth" สำหรับ WooCommerce
- Store URL ต้องเป็น full URL (เช่น `https://yourstore.com` ไม่ใช่ `yourstore.com`)
- Consumer Key และ Consumer Secret จะแสดงครั้งเดียวเมื่อสร้าง - ต้องบันทึกไว้

