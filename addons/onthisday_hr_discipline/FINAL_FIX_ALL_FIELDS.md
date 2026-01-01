# แก้ไข Many2many Fields ทั้งหมด - Final Fix

## สิ่งที่ทำไปแล้ว

### 1. อัพเดท Metadata สำหรับ Fields ทั้งหมด
อัพเดท relation metadata สำหรับ fields ใน:
- `hr.employee`: `kpi_missing_subordinate_ids`, `message_partner_ids`, `related_contact_ids`
- `res.config.settings`: `license_report_user_ids`, `knowsystem_sort_ids`, `knowsystem_ir_actions_server_ids`, `predictive_lead_scoring_fields`, `language_ids`
- `res.company`: `account_enabled_tax_country_ids`, `multi_vat_foreign_country_ids`

### 2. SQL Commands ที่ใช้

```sql
-- แก้ไข res.config.settings fields
UPDATE ir_model_fields 
SET relation_table = CASE 
    WHEN relation = 'res.lang' THEN 'res_config_settings_res_lang_rel'
    WHEN relation = 'knowsystem.custom.sort' THEN 'res_config_settings_knowsystem_sort_rel'
    WHEN relation = 'ir.actions.server' THEN 'res_config_settings_ir_actions_server_rel'
    WHEN relation = 'crm.lead.scoring.frequency.field' THEN 'res_config_settings_predictive_lead_scoring_rel'
    ELSE relation_table
END,
column1 = 'res_config_settings_id',
column2 = CASE 
    WHEN relation = 'res.lang' THEN 'res_lang_id'
    WHEN relation = 'knowsystem.custom.sort' THEN 'knowsystem_sort_id'
    WHEN relation = 'ir.actions.server' THEN 'ir_actions_server_id'
    WHEN relation = 'crm.lead.scoring.frequency.field' THEN 'crm_lead_scoring_frequency_field_id'
    ELSE column2
END
WHERE model = 'res.config.settings'
  AND ttype = 'many2many'
  AND (relation_table IS NULL OR column1 IS NULL OR column2 IS NULL)
  AND relation IS NOT NULL;

-- แก้ไข res.company fields
UPDATE ir_model_fields 
SET relation_table = CASE 
    WHEN name = 'account_enabled_tax_country_ids' THEN 'res_company_account_enabled_tax_country_rel'
    WHEN name = 'multi_vat_foreign_country_ids' THEN 'res_company_multi_vat_foreign_country_rel'
    ELSE relation_table
END,
column1 = 'company_id',
column2 = 'country_id'
WHERE model = 'res.company'
  AND ttype = 'many2many'
  AND (relation_table IS NULL OR column1 IS NULL OR column2 IS NULL)
  AND relation IS NOT NULL;
```

## ⚠️ ขั้นตอนต่อไป (สำคัญมาก!)

### 1. Restart Odoo Server (จำเป็น)
**ต้อง restart Odoo server** เพื่อให้ metadata ใหม่ถูกโหลด:

```bash
# หยุด Odoo server (กด Ctrl+C)
# แล้วเริ่มใหม่:
cd /Users/nattaphonsupa/odoo-16
./venv/bin/python3 odoo-bin -d nt --addons-path=./odoo/addons,./addons,./custom_addons
```

### 2. Hard Reload Browser
- **Hard Reload**: Ctrl+Shift+R (Windows/Linux) หรือ Cmd+Shift+R (Mac)
- หรือ Clear browser cache แบบเต็มรูปแบบ
- หรือเปิด Incognito/Private window

### 3. ทดสอบ
- เข้าหน้า **Employee** → ไม่ควรมี error
- เข้าหน้า **Settings** → ไม่ควรมี error

## ตรวจสอบ

```sql
-- ตรวจสอบว่ายังมี fields ที่ไม่มี metadata หรือไม่
SELECT model, name, relation 
FROM ir_model_fields 
WHERE ttype = 'many2many' 
  AND model IN ('hr.employee', 'res.config.settings', 'res.company') 
  AND (relation_table IS NULL OR column1 IS NULL OR column2 IS NULL) 
  AND relation IS NOT NULL;
```

ถ้ายังมี fields ที่ไม่มี metadata อาจต้องเพิ่ม metadata ให้ fields เหล่านั้นด้วย

## สรุป

✅ **Database metadata อัพเดทแล้วสำหรับ fields ทั้งหมด**  
⚠️ **ต้อง restart Odoo server**  
⚠️ **ต้อง hard reload browser**

**สำคัญ**: Odoo จะไม่ใช้ metadata ใหม่จนกว่า server จะ restart!

