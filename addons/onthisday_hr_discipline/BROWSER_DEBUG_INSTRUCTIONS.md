# 🔍 วิธี Debug Error "can't access property 'relation'"

## Error ที่เกิดขึ้น

```
TypeError: can't access property "relation", models[resModel][fieldName] is undefined
at processArch/<@web.assets_backend.min.js:6807:56
```

## สาเหตุที่เป็นไปได้

1. **Browser Cache**: ยังใช้ JavaScript bundle เก่า
2. **Field ไม่ถูกส่งมาใน fields_get**: Field ไหนที่ถูกใช้ใน view แต่ไม่ถูกส่งมาใน response
3. **Field Definition ไม่มีใน Registry**: Field ถูกใช้แต่ไม่มี definition

## 🔧 วิธี Debug

### 1. เปิด Browser Developer Tools

- กด **F12** หรือ **Ctrl+Shift+I** (Windows/Linux) / **Cmd+Option+I** (Mac)

### 2. ตรวจสอบ Browser Console

ใน **Console** tab:

```javascript
// ตรวจสอบว่า model อะไรที่ทำให้เกิด error
// Error จะบอกว่า models[resModel][fieldName] is undefined
```

### 3. ตรวจสอบ Network Tab

1. ไปที่ **Network** tab
2. **Refresh หน้า** (F5)
3. หา request ที่ชื่อ **`fields_get`** หรือ **`load_views`**
4. คลิกที่ request นั้น
5. ไปที่ **Response** tab
6. ตรวจสอบว่า fields ที่ถูกส่งมามีครบหรือไม่

### 4. ตรวจสอบว่า Field ไหนที่ทำให้เกิด Error

ใน **Console** tab พิมพ์:

```javascript
// ตรวจสอบ models ที่โหลดอยู่
console.log(Object.keys(window.odoo.web.client.actions));

// หรือตรวจสอบ fields ที่ถูกส่งมา
// (ต้องดูใน Network response)
```

### 5. หา View ที่กำลังโหลด

1. ใน **Network** tab
2. หา request **`load_views`**
3. ดู **Request** tab → **Form Data** หรือ **Payload**
4. ดูว่า `res_model` คืออะไร (น่าจะเป็น `hr.employee` หรือ `hr.contract`)
5. ดู `view_ids` ว่ามี view อะไรบ้าง

### 6. ตรวจสอบ Field ใน View XML

ใน **Network** tab:
- หา request **`load_views`**
- ดู **Response** tab
- ตรวจสอบว่า `fields` object มี field ที่ถูกใช้ใน view ครบหรือไม่

## 🎯 ข้อมูลที่ต้องการ

ถ้า error ยังคงอยู่ กรุณาส่งข้อมูลต่อไปนี้:

1. **Browser Console Error** (copy ทั้ง stack trace)
2. **Network Request** สำหรับ `fields_get` หรือ `load_views`:
   - Request URL
   - Request Payload (ถ้าเป็น POST)
   - Response JSON (copy มาเฉพาะส่วน `fields` object)
3. **บอกว่าหน้าไหน** ที่เกิด error (Employee, Contract, หรือ Settings)

## 📝 ตัวอย่างข้อมูลที่ต้องการ

### จาก Browser Console:
```
TypeError: can't access property "relation", models[resModel][fieldName] is undefined
    at processArch/<@...:6807:56
```

### จาก Network Tab:
```json
{
  "fields": {
    "category_ids": { ... },
    "message_partner_ids": { ... },
    // field ไหนที่ขาดหายไป?
  }
}
```

## 🚀 Quick Fix

### 1. Clear Browser Cache แบบเต็มรูปแบบ

1. **F12** → **Application** tab (Chrome) หรือ **Storage** tab (Firefox)
2. คลิก **"Clear site data"** หรือ **"Clear storage"**
3. **Refresh** หน้า (F5)

### 2. Incognito Window

- เปิด **Incognito/Private window**
- เข้า Odoo ใหม่

### 3. Hard Reload

- **Ctrl+Shift+R** (Windows/Linux) หรือ **Cmd+Shift+R** (Mac)

---

**ส่งข้อมูลมาให้ฉัน แล้วฉันจะช่วยแก้ไขต่อครับ!**

