# 🔴 Direct SQL Fix - แก้ Error โดยลบ Fields จาก View

## ปัญหา

Error: `can't access property "relation", models[resModel][fieldName] is undefined`

View 3505 ใช้ fields ที่ client-side JavaScript ไม่มี definition

## วิธีแก้ไขแบบ Direct (แก้ทันที)

### วิธีที่ 1: ลบ Fields จาก View (แนะนำ)

ลบ fields ที่ทำให้เกิด error ออกจาก view:

```sql
-- แก้ไข view 3505 เพื่อลบ fields ที่มีปัญหา
UPDATE ir_ui_view 
SET arch_db = jsonb_set(
    arch_db,
    '{en_US}',
    '"<xpath expr=\"//div[hasclass(''"'"'settings'"'"')]\" position=\"inside\"><div class=\"app_settings_block\" data-string=\"Payroll\" string=\"Payroll\" data-key=\"hr_payroll_community\" invisible=\"1\"></div></xpath>"'
)
WHERE id = 3505;
```

### วิธีที่ 2: ซ่อน View ทั้งหมด

```sql
-- ซ่อน view 3505
UPDATE ir_ui_view SET active = false WHERE id = 3505;
```

### วิธีที่ 3: ลบ View

```sql
-- ลบ view 3505 (ถ้าไม่จำเป็น)
DELETE FROM ir_ui_view WHERE id = 3505;
```

## วิธีแก้ไขแบบถาวร (แนะนำ)

### Restart Odoo Server + Clear Browser Cache

1. **Restart Odoo Server**
   ```bash
   # หยุด Odoo server (Ctrl+C)
   ./venv/bin/python3 odoo-bin -d nt --addons-path=./odoo/addons,./addons,./custom_addons
   ```

2. **Clear Browser Cache**
   - F12 → Right-click Reload → "Empty Cache and Hard Reload"
   - หรือ Ctrl+Shift+Delete → Clear cache

3. **Hard Reload**: Ctrl+Shift+R

## สรุป

- **วิธีแก้ทันที**: ลบ/ซ่อน view 3505 หรือลบ fields ออกจาก view
- **วิธีแก้ถาวร**: Restart server + Clear browser cache

เลือกวิธีที่เหมาะสมกับสถานการณ์

