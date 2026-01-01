# แก้ไข Security Groups สำหรับ Odoo 19

## ปัญหา

เมื่อติดตั้งโมดูลใน Odoo 19 เกิด error:
```
ValueError: Invalid field 'category_id' in 'res.groups'
```

## สาเหตุ

ใน Odoo 19 มีการเปลี่ยนแปลง API ของ `res.groups`:
- **Odoo 16**: `res.groups` ใช้ `category_id` โดยตรง
- **Odoo 19**: `res.groups` ไม่มี `category_id` แล้ว ต้องใช้ `privilege_id` แทน

## วิธีแก้ไข

### 1. สร้าง `res.groups.privilege` ก่อน

```xml
<record id="res_groups_privilege_discipline" model="res.groups.privilege">
    <field name="name">Discipline</field>
    <field name="sequence">10</field>
    <field name="category_id" ref="base.module_category_human_resources"/>
</record>
```

### 2. ใช้ `privilege_id` ใน `res.groups`

**เดิม (Odoo 16):**
```xml
<record id="group_discipline_user" model="res.groups">
    <field name="name">Discipline User</field>
    <field name="category_id" ref="base.module_category_human_resources"/>
</record>
```

**ใหม่ (Odoo 19):**
```xml
<record id="group_discipline_user" model="res.groups">
    <field name="name">Discipline User</field>
    <field name="privilege_id" ref="res_groups_privilege_discipline"/>
</record>
```

## ไฟล์ที่แก้ไข

- `security/security.xml` - แก้ไข groups ทั้งหมดให้ใช้ `privilege_id`

## สรุป

✅ แก้ไขเสร็จสมบูรณ์  
✅ XML syntax ถูกต้อง  
✅ ตามมาตรฐาน Odoo 19  

โมดูลพร้อมติดตั้งแล้ว!

