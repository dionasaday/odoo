# สถานะการติดตั้ง Helpdesk Module

## สิ่งที่ทำไปแล้ว:

✅ Clone OCA helpdesk repository (branch 18.0) มาไว้ที่ `/Users/nattaphonsupa/odoo19/addons/helpdesk`

✅ สร้าง symbolic links สำหรับโมดูลทั้งหมด (22 โมดูล) เพื่อให้ Odoo เห็นโมดูลใน addons_path

✅ แก้ไข compatibility issues สำหรับ Odoo 19:
   - เปลี่ยน version ใน manifest จาก 18.0 เป็น 19.0
   - แก้ไข res.groups ให้ใช้ `privilege_id` แทน `category_id`
   - เพิ่ม `res.groups.privilege` record ใน data file
   - แก้ไข `users` เป็น `user_ids` ใน res.groups
   - ลบ `target="inline"` ออกจาก action (ไม่รองรับใน Odoo 19)

## สิ่งที่ยังต้องแก้ไข:

⚠️ มี error ใน search view definition (`helpdesk.ticket.search`) ที่ต้องแก้ไข

## แนะนำขั้นตอนต่อไป:

### วิธีที่ 1: ติดตั้งผ่าน Odoo UI (แนะนำ)

1. Restart Odoo:
   ```bash
   make restart
   ```

2. เปิดเบราว์เซอร์ไปที่: http://localhost:8069

3. ไปที่ **Apps** > คลิก **"Update Apps List"**

4. ค้นหา **"Helpdesk Management"** หรือ **"helpdesk_mgmt"**

5. หากมี error ให้ดู logs เพื่อหาปัญหาและแก้ไข

### วิธีที่ 2: แก้ไข error แล้วติดตั้งผ่าน command line

แก้ไข error ใน search view แล้วรัน:
```bash
docker-compose exec -T odoo odoo shell -d odoo19 --no-http --stop-after-init -c /etc/odoo/odoo.conf << 'EOF'
module = self.env['ir.module.module'].search([('name', '=', 'helpdesk_mgmt')], limit=1)
if module:
    module.button_immediate_install()
    print("Installation completed")
EOF
```

## โมดูล Helpdesk ที่พร้อมใช้งาน:

โมดูลทั้งหมดถูก clone และสร้าง symlinks แล้ว:
- helpdesk_mgmt (โมดูลหลัก)
- helpdesk_mgmt_crm
- helpdesk_mgmt_project
- helpdesk_mgmt_sale
- helpdesk_mgmt_sla
- helpdesk_mgmt_timesheet
- และอื่นๆ อีก 16 โมดูล

## หมายเหตุ:

- โมดูลนี้เป็น branch 18.0 ซึ่งต้องแก้ไข compatibility issues สำหรับ Odoo 19
- บางส่วนยังอาจต้องแก้ไขเพิ่มเติมเพื่อให้ทำงานได้สมบูรณ์ใน Odoo 19
