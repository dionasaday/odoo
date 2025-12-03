# วิธีแก้ไข Browser Cache Error

หากคุณยังเจอ error: `"knowledge.article"."category" field is undefined` หลังจาก upgrade module แล้ว

## สาเหตุ
Error นี้เกิดจาก **browser cache** ที่ยังมี JavaScript assets เก่าอยู่

## วิธีแก้ไข (ทำตามลำดับ)

### วิธีที่ 1: Hard Refresh (ทำก่อน)
1. เปิด Odoo ใน browser
2. กด **`Ctrl + Shift + R`** (Windows/Linux) หรือ **`Cmd + Shift + R`** (Mac)
3. รอให้หน้าโหลดใหม่

### วิธีที่ 2: Clear Browser Cache (ถ้ายังไม่ได้)
1. กด **`Ctrl + Shift + Delete`** (Windows/Linux) หรือ **`Cmd + Shift + Delete`** (Mac)
2. เลือก:
   - ✅ Cached images and files
   - ✅ Cookies and other site data (เฉพาะ localhost:8069)
3. Time range: **All time**
4. กด **Clear data**
5. **ปิด browser หมด** แล้วเปิดใหม่
6. Login Odoo อีกครั้ง

### วิธีที่ 3: ใช้ Developer Tools (แนะนำ)
1. เปิด Odoo
2. กด **`F12`** (เปิด Developer Tools)
3. ไปที่แท็บ **Application**
4. ใน **Storage**:
   - คลิกขวาที่ `localhost:8069` → **Clear**
   - หรือ **Clear site data**
5. กด **`Ctrl + Shift + R`** (Hard refresh)
6. ปิด Developer Tools
7. Login Odoo อีกครั้ง

### วิธีที่ 4: ทดสอบใน Incognito Mode (ยืนยันปัญหา)
1. เปิด **Incognito/Private window**:
   - Chrome: `Ctrl + Shift + N` (Windows) หรือ `Cmd + Shift + N` (Mac)
   - Firefox: `Ctrl + Shift + P` (Windows) หรือ `Cmd + Shift + P` (Mac)
2. เปิด `http://localhost:8069`
3. Login Odoo
4. ทดสอบเปิด **Knowledge > Knowledge Base**

**ถ้าใน Incognito mode ใช้งานได้ = ปัญหาคือ browser cache**

### วิธีที่ 5: Clear Odoo Assets Cache (Server-side)
ถ้ายังไม่ได้ผล ให้ restart Odoo เพื่อ rebuild assets:

```bash
cd /Users/nattaphonsupa/odoo19
docker compose restart odoo
```

รอ 30 วินาที แล้ว refresh browser ด้วย **`Ctrl + Shift + R`**

---

## สรุป Checklist
- [ ] Hard Refresh (`Ctrl + Shift + R`)
- [ ] Clear Browser Cache
- [ ] Clear Site Data (Developer Tools)
- [ ] ทดสอบใน Incognito Mode
- [ ] Restart Odoo Container
- [ ] Hard Refresh อีกครั้ง

---

## ถ้ายังไม่ได้ผล
แจ้งรายละเอียด:
- Browser ที่ใช้ (Chrome, Firefox, Safari)
- Error message ที่เจอ
- URL ที่ error เกิดขึ้น
- Screenshot ของ Developer Console (F12 → Console tab)
