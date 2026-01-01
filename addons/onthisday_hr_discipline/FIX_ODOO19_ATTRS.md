# แก้ไข attrs Attribute สำหรับ Odoo 19

## ปัญหา

```
Since 17.0, the "attrs" and "states" attributes are no longer used.
```

## สาเหตุ

ใน Odoo 19 (และตั้งแต่ 17.0) ไม่ใช้ `attrs` และ `states` attributes แล้ว:
- **Odoo 16**: ใช้ `attrs="{'invisible': [...], 'readonly': [...], 'required': [...]}"`
- **Odoo 19**: ใช้ attributes โดยตรง: `invisible`, `readonly`, `required`

## วิธีแก้ไข

### 1. invisible

**เดิม (Odoo 16):**
```xml
<field name="field_name" attrs="{'invisible': [('other_field', '=', False)]}"/>
```

**ใหม่ (Odoo 19):**
```xml
<field name="field_name" invisible="not other_field"/>
```

หรือ
```xml
<field name="field_name" invisible="other_field == False"/>
```

### 2. readonly

**เดิม (Odoo 16):**
```xml
<field name="field_name" attrs="{'readonly': [('state', '=', 'done')]}"/>
```

**ใหม่ (Odoo 19):**
```xml
<field name="field_name" readonly="state == 'done'"/>
```

### 3. required

**เดิม (Odoo 16):**
```xml
<field name="field_name" attrs="{'required': [('type', '=', 'sale')]}"/>
```

**ใหม่ (Odoo 19):**
```xml
<field name="field_name" required="type == 'sale'"/>
```

### 4. ตัวอย่างการแปลง

| Odoo 16 (attrs) | Odoo 19 (direct attribute) |
|----------------|---------------------------|
| `attrs="{'invisible': [('field', '=', False)]}"` | `invisible="not field"` |
| `attrs="{'invisible': [('field', '!=', 'value')]}"` | `invisible="field != 'value'"` |
| `attrs="{'invisible': [('field', 'in', ['a', 'b'])]}"` | `invisible="field in ['a', 'b']"` |
| `attrs="{'readonly': [('state', '=', 'done')]}"` | `readonly="state == 'done'"` |
| `attrs="{'required': [('type', '=', 'sale')]}"` | `required="type == 'sale'"` |

## ไฟล์ที่แก้ไข

1. ✅ `views/case_views.xml`
2. ✅ `views/lateness_log_views.xml`
3. ✅ `views/attendance_views.xml`
4. ✅ `views/company_lateness_views.xml`
5. ✅ `views/lateness_monthly_summary_views.xml`
6. ✅ `views/attendance_award_views.xml`
7. ✅ `views/res_company_views.xml`
8. ✅ `views/hr_discipline_case_views.xml`

## สรุป

✅ แก้ไขเสร็จสมบูรณ์  
✅ XML syntax ถูกต้อง  
✅ ตามมาตรฐาน Odoo 19  
✅ ไม่มี `attrs` เหลืออยู่แล้ว  

โมดูลพร้อมติดตั้งแล้ว!

