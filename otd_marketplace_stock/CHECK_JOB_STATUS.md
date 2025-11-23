# 🔍 วิธีตรวจสอบ Job Status และ Logs

## วิธีที่ 1: ตรวจสอบผ่าน Odoo UI (แนะนำ)

1. **ไปที่ Marketplace > Jobs**
2. **ค้นหา Job:**
   - ค้นหา "Import Products from Zortout - Zortout"
   - หรือ filter โดย Job Type: "Sync Products from Zortout"
3. **ตรวจสอบ Status:**
   - **In Progress**: Job กำลังทำงานอยู่
   - **Done**: Job เสร็จสมบูรณ์แล้ว
   - **Failed**: Job ล้มเหลว
   - **Pending**: Job กำลังรอการทำงาน
4. **ดู Result:**
   - เปิด Job และดู Result field
   - ดู Last Error ถ้ามี

## วิธีที่ 2: ตรวจสอบ Logs ผ่าน Terminal

### ตรวจสอบ Logs แบบ Real-time:

```bash
cd /Users/nattaphonsupa/odoo19
./addons/otd_marketplace_stock/watch_job_realtime.sh
```

### ตรวจสอบ Logs ล่าสุด:

```bash
cd /Users/nattaphonsupa/odoo19
./addons/otd_marketplace_stock/check_job_logs.sh
```

### ตรวจสอบ Logs โดยตรง:

```bash
cd /Users/nattaphonsupa/odoo19
docker compose exec odoo tail -f /var/log/odoo/odoo.log | grep -E "(Import Products|Sync Product|Zortout|marketplace.job)"
```

## วิธีที่ 3: ตรวจสอบ Job Status ผ่าน Database

```bash
cd /Users/nattaphonsupa/odoo19
docker compose exec odoo odoo shell -d odoo19 --no-http --stop-after-init << 'EOF'
env = self.env
job = env['marketplace.job'].search([
    ('name', '=', 'Import Products from Zortout - Zortout')
], order='create_date desc', limit=1)
if job:
    print(f"Job ID: {job.id}")
    print(f"State: {job.state}")
    print(f"Started At: {job.started_at}")
    print(f"Completed At: {job.completed_at}")
    print(f"Result: {job.result}")
    print(f"Last Error: {job.last_error}")
else:
    print("Job not found")
EOF
```

## วิธีที่ 4: ตรวจสอบ Cron Job

```bash
cd /Users/nattaphonsupa/odoo19
docker compose exec odoo tail -f /var/log/odoo/odoo.log | grep -E "Processing.*marketplace jobs"
```

## สัญญาณที่บอกว่า Job ยังทำงานอยู่:

1. **Status = "In Progress"** ใน Odoo UI
2. **Started At** มีค่า แต่ **Completed At** ยังว่าง
3. **Duration** เพิ่มขึ้นเรื่อยๆ
4. **Logs** แสดง activity ล่าสุด (เช่น "Syncing products", "Fetching products")

## สัญญาณที่บอกว่า Job เสร็จแล้ว:

1. **Status = "Done"** หรือ **"Failed"** ใน Odoo UI
2. **Completed At** มีค่า
3. **Result** field มีข้อมูล
4. **Logs** แสดง "Job completed" หรือ "Job failed"

## Troubleshooting

### ถ้า Job ค้างอยู่ (In Progress นานเกินไป):

1. **ตรวจสอบ Logs:**
   ```bash
   docker compose exec odoo tail -500 /var/log/odoo/odoo.log | grep -E "(ERROR|Exception|Failed)" | tail -20
   ```

2. **ตรวจสอบว่า Cron ทำงานหรือไม่:**
   ```bash
   docker compose exec odoo tail -f /var/log/odoo/odoo.log | grep "Processing.*marketplace jobs"
   ```

3. **Restart Job:**
   - ไปที่ Marketplace > Jobs
   - เปิด Job ที่ค้างอยู่
   - กดปุ่ม "Move to Dead Letter"
   - สร้าง Job ใหม่

### ถ้าไม่พบ Logs:

1. **ตรวจสอบ Log Level:**
   - ไปที่ Settings > Technical > Parameters > System Parameters
   - ตรวจสอบ `log_level` (ควรเป็น `info` หรือ `debug`)

2. **ตรวจสอบ Log File:**
   ```bash
   docker compose exec odoo ls -lh /var/log/odoo/
   ```

