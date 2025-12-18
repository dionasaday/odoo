# แก้ไข Kanban Color Error ใน Helpdesk Module

## ปัญหา:
Error: `ctx.kanban_color is not a function` เกิดขึ้นเมื่อเปิด Helpdesk kanban view

## สาเหตุ:
ใน Odoo 19, `kanban_color()` function ถูก deprecated แล้ว และไม่สามารถใช้ได้ใน template

## การแก้ไข:
แก้ไขไฟล์ `views/helpdesk_dashboard_views.xml` โดย:

1. **เพิ่ม `highlight_color="color"` attribute** ใน `<kanban>` tag:
   ```xml
   <kanban class="o_kanban_mobile" create="0" js_class="helpdesk_kanban" highlight_color="color">
   ```

2. **ลบการใช้ `kanban_color()` function** ใน template:
   - เดิม: `<div t-attf-class="#{kanban_color(record.color.raw_value)}">`
   - ใหม่: `<div>`

Odoo 19 จะจัดการ color class อัตโนมัติผ่าน `highlight_color` attribute

## หมายเหตุ:
- ใน Odoo 19 ใช้ `highlight_color="field_name"` แทน `kanban_color()` function
- `oe_kanban_color_X` classes ถูก deprecated แล้ว
- Browser cache อาจต้อง clear (Ctrl+Shift+R หรือ Cmd+Shift+R)

## สถานะ:
✅ แก้ไขเรียบร้อยแล้ว
✅ Module upgrade แล้ว
⚠️ อาจต้อง clear browser cache เพื่อให้เห็นการเปลี่ยนแปลง
