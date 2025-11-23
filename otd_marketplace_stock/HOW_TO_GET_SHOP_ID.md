# วิธีหา External Shop ID สำหรับ Shopee

## External Shop ID คืออะไร?
External Shop ID (shop_id) คือรหัสประจำร้านค้า Shopee ที่ใช้สำหรับการเรียก API เพื่อดึงข้อมูล orders, stock, และจัดการร้านค้า

## วิธีหา Shop ID

### วิธีที่ 1: จาก OAuth Callback (แนะนำ)
หลังจาก OAuth authorization สำเร็จ:
1. ตรวจสอบ **Activity Log** ใน Marketplace Account
2. ดู message "OAuth authorization successful"
3. ถ้ามี Shop ID จะแสดงใน message: `Shop ID: 123456`

**หรือตรวจสอบ logs:**
```bash
docker compose logs odoo | grep "Shop ID from OAuth callback"
```

### วิธีที่ 2: จาก Shopee Seller Center
1. ไปที่ [Shopee Seller Center](https://seller.shopee.co.th/)
2. ลงชื่อเข้าใช้
3. ไปที่ **ร้านค้า** > **รายละเอียดร้านค้า**
4. คลิก **ดูร้านค้า**
5. ดู URL: `https://shopee.co.th/shop/123456`
6. ตัวเลขที่ตามหลัง `/shop/` คือ Shop ID

### วิธีที่ 3: จาก Shopee API (หลังจากมี Access Token)
เรียก API เพื่อดึงรายชื่อ shops:
```python
# GET /api/v2/shop/get_shop_info
# หรือ
# GET /api/v2/public/get_shops_by_partner
```

### วิธีที่ 4: ตรวจสอบ Browser URL เมื่อ OAuth
เมื่อ Shopee redirect กลับมาที่ OAuth callback:
- URL จะมี format: `.../oauth/callback/shopee?code=...&shop_id=123456`
- shop_id จะอยู่ใน URL parameters

## วิธีใช้ Shop ID

### 1. สร้าง Shop Record ใน Odoo
1. ไปที่ **Marketplace** > **Shops**
2. คลิก **New**
3. กรอกข้อมูล:
   - **Shop Name**: ชื่อร้าน (เช่น "Shopee Shop 1")
   - **Account**: เลือก "Shopee Thailand"
   - **External Shop ID**: ใส่ Shop ID ที่ได้ (เช่น `123456`)
   - **Warehouse**: เลือก warehouse
   - **Timezone**: `Asia/Bangkok`
   - **Active**: ✓

### 2. ตรวจสอบ Shop ID ถูกต้อง
หลังจากสร้าง Shop แล้ว:
1. ทดสอบดึง Orders: **Marketplace** > **Jobs** > สร้าง job `pull_orders`
2. ถ้าได้ orders = Shop ID ถูกต้อง
3. ถ้าได้ error = Shop ID อาจไม่ถูกต้อง

## Troubleshooting

### ไม่มี Shop ID ใน OAuth Callback?
- Shopee อาจไม่ส่ง shop_id ใน callback
- ตรวจสอบ logs: `docker compose logs odoo | grep "OAuth callback"`
- หรือใช้วิธีที่ 2 (Shopee Seller Center)

### Shop ID ไม่ถูกต้อง?
- ตรวจสอบว่าเป็น Shop ID ของร้านที่ authorize
- ลองใช้ Shop ID จาก Seller Center
- ทดสอบด้วย API call

## หมายเหตุ
- Shop ID เป็นตัวเลข (integer)
- แต่ละ Shopee account อาจมีหลาย shops
- ต้องใช้ Shop ID ที่ถูกต้องกับร้านที่ authorize

