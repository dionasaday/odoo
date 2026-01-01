# คำแนะนำการ Upgrade Module

## วิธีแก้ปัญหา "inconsistent states" error

1. **Restart Odoo server** (ถ้ายังไม่ได้ restart)

2. **Upgrade module:**
   ```
   - ไปที่ Apps
   - ค้นหา "OnThisDay HR Discipline"
   - กด "Upgrade"
   ```

   หรือใช้ command line:
   ```bash
   python3 odoo-bin -u onthisday_hr_discipline -d <database_name>
   ```

3. **ตรวจสอบว่า model ถูกสร้างแล้ว:**
   - ไปที่ Settings > Technical > Database Structure > Models
   - ค้นหา "hr.lateness.monthly_summary"
   - ตรวจสอบว่ามีอยู่

4. **ตรวจสอบ cron job:**
   - ไปที่ Settings > Technical > Automation > Scheduled Actions
   - ค้นหา "Lateness Monthly Summary - Create & Send"
   - ตรวจสอบว่ามีอยู่และ active

## Troubleshooting

- ถ้ายังมี error: ลอง restart Odoo อีกครั้ง
- ถ้า cron ไม่ทำงาน: ตรวจสอบ nextcall date
- ถ้า mail template ไม่พบ: ตรวจสอบว่า mail_templates.xml ถูกโหลด

