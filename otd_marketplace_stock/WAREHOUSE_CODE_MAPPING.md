# 🔄 Warehouse Code Mapping Guide

## ปัญหา

- **Odoo Warehouse Short Name**: จำกัดแค่ **5 หลัก** (เช่น `ODS00`)
- **Zortout Warehouse Code**: สามารถเป็น **6 หลัก** หรือมากกว่า (เช่น `ODS001`)

## วิธีแก้ไข

### วิธีที่ 1: ใช้การ Sync โดยไม่ระบุ Warehouse Code (แนะนำ)

เนื่องจาก Odoo จำกัด Short Name แค่ 5 หลัก แต่ Zortout ใช้ `ODS001` (6 หลัก):

1. **ตั้งค่า Stock Location:**
   - ไปที่ **Marketplace** > **Accounts** > **Zortout**
   - ไปที่ Tab **"Stock Configuration"**
   - เลือก **Stock Location** ที่ต้องการใช้ (เช่น `ODS00/Stock`)
   - **Save**

2. **กดปุ่ม "ดึงสต็อกสินค้า":**
   - ระบบจะดึงสินค้าทั้งหมดจากทุก warehouse ใน Zortout
   - และอัปเดต stock ใน location ที่เลือกไว้

### วิธีที่ 2: ตั้งค่า Zortout Warehouse Code ผ่าน System Parameter

ถ้าต้องการระบุ warehouse code ที่ถูกต้อง (`ODS001`) แม้ว่า Odoo จะใช้ `ODS00`:

1. **ห Warehouse ID:**
   - ไปที่ **Inventory** > **Configuration** > **Warehouses**
   - เปิด Warehouse ที่ต้องการ (เช่น "คลังสินค้าหลัก")
   - ดู ID จาก URL หรือจากหน้า Warehouse (เช่น ID = 3)

2. **ตั้งค่า System Parameter:**
   - ไปที่ **Settings** > **Technical** > **Parameters** > **System Parameters**
   - คลิก **New**
   - กรอกข้อมูล:
     - **Key**: `marketplace.zortout.warehouse_code.3` (เปลี่ยน 3 เป็น Warehouse ID ของคุณ)
     - **Value**: `ODS001` (Zortout warehouse code ที่ถูกต้อง)
   - **Save**

3. **ทดสอบ:**
   - กลับไปที่ **Marketplace** > **Accounts** > **Zortout**
   - กดปุ่ม **"ทดสอบ Warehouse Code"**
   - ควรเห็น: `✅ Success: Found X products` สำหรับ warehouse code `ODS001`

### วิธีที่ 3: ใช้ Warehouse Code ที่สั้นกว่า (ถ้า Zortout รองรับ)

ถ้า Zortout รองรับ warehouse code ที่สั้นกว่า:

1. **ตรวจสอบใน Zortout:**
   - ดูว่า warehouse code `ODS00` ใช้งานได้หรือไม่
   - หรือมี warehouse code อื่นที่สั้นกว่า 5 หลัก

2. **ตั้งค่าใน Odoo:**
   - ใช้ warehouse code ที่สั้นกว่า 5 หลัก
   - ตั้งค่า Stock Location ให้ชี้ไปที่ warehouse นั้น

## สรุป

- **Odoo Short Name**: จำกัด 5 หลัก (`ODS00`)
- **Zortout Code**: สามารถเป็น 6 หลัก (`ODS001`)
- **วิธีแก้**: ใช้การ sync โดยไม่ระบุ warehouse code (ทำงานได้แล้ว) หรือตั้งค่า System Parameter เพื่อ map warehouse code

## Warehouse List จาก Zortout

1. **คลังสินค้าหลัก** - Code: `ODS001` (6 หลัก) ⚠️
2. **คลังสินค้าตำหนิ** - Code: `ODS002` (6 หลัก) ⚠️
3. **Thailand Coffee Fest** - Code: `W0005` (5 หลัก) ✅
4. **supercheap** - Code: `W0006` (5 หลัก) ✅

Warehouse ที่มี code 5 หลักสามารถใช้ได้โดยตรงใน Odoo

