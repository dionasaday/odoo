# วิธีลบ Asset Records ด้วย SQL

## วิธีที่ 1: ใช้ psql (PostgreSQL Command Line)

### ขั้นตอน:
1. **เปิด Terminal**
2. **เชื่อมต่อฐานข้อมูล:**
   ```bash
   psql -U <username> -d <database_name>
   ```
   หรือถ้าใช้ default odoo user:
   ```bash
   psql -U odoo -d <database_name>
   ```

3. **รันคำสั่ง SQL:**
   ```sql
   DELETE FROM ir_asset 
   WHERE path LIKE '/om_account_asset/static/%'
   AND (name = 'Account Assets' OR name = 'aAccount Assets SCSS');
   ```

4. **ตรวจสอบว่าลบสำเร็จ:**
   ```sql
   SELECT id, name, path FROM ir_asset WHERE path LIKE '/om_account_asset/static/%';
   ```
   (ควรไม่มีผลลัพธ์)

5. **ออกจาก psql:**
   ```sql
   \q
   ```

---

## วิธีที่ 2: ใช้ pgAdmin (GUI)

1. **เปิด pgAdmin**
2. **เชื่อมต่อกับ database**
3. **ไปที่ Tools → Query Tool**
4. **รันคำสั่ง SQL:**
   ```sql
   DELETE FROM ir_asset 
   WHERE path LIKE '/om_account_asset/static/%'
   AND (name = 'Account Assets' OR name = 'aAccount Assets SCSS');
   ```
5. **กด Execute (F5)**

---

## วิธีที่ 3: ใช้ Odoo Shell (Python)

1. **เปิด Terminal**
2. **เข้า Odoo shell:**
   ```bash
   python3 odoo-bin shell -d <database_name>
   ```

3. **รัน Python code:**
   ```python
   assets = env['ir.asset'].search([
       ('path', 'like', '/om_account_asset/static/%')
   ])
   print(f"Found {len(assets)} assets to delete")
   assets.unlink()
   print("Deleted successfully!")
   ```

4. **ออกจาก shell:**
   ```python
   exit()
   ```

---

## วิธีที่ 4: ใช้ Odoo UI (ไม่ต้องเขียน SQL)

1. **Enable Developer Mode:**
   - ไปที่ Settings
   - กด "Activate the developer mode"

2. **เปิด Technical Menu:**
   - ไปที่ Settings → Technical → Assets
   - หรือ URL: `/web#action=base.action_asset`

3. **ค้นหาและลบ:**
   - ค้นหา "Account Assets" หรือ "aAccount Assets SCSS"
   - เลือก records ที่มี path ขึ้นต้นด้วย `/om_account_asset/static/`
   - กด "Delete"

---

## คำสั่ง SQL แบบละเอียด

### ดู asset records ที่จะลบก่อน:
```sql
SELECT id, name, path, bundle, active 
FROM ir_asset 
WHERE path LIKE '/om_account_asset/static/%';
```

### ลบเฉพาะ SCSS file:
```sql
DELETE FROM ir_asset 
WHERE path = '/om_account_asset/static/src/scss/account_asset.scss';
```

### ลบเฉพาะ JS file:
```sql
DELETE FROM ir_asset 
WHERE path = '/om_account_asset/static/src/js/account_asset.js';
```

### ลบทั้งหมดที่เกี่ยวข้องกับ om_account_asset:
```sql
DELETE FROM ir_asset 
WHERE path LIKE '/om_account_asset/%';
```

---

## ตรวจสอบผลลัพธ์

หลังจากลบแล้ว ให้ตรวจสอบว่า:
1. ไม่มี asset records เหลืออยู่
2. Restart Odoo server
3. Hard reload browser (Ctrl+Shift+R หรือ Cmd+Shift+R)
4. Error ควรหายไป

---

## ⚠️ ข้อควรระวัง

- **Backup database ก่อน** ถ้ามีข้อมูลสำคัญ
- ตรวจสอบ path ให้ถูกต้องก่อนลบ
- ถ้าไม่แน่ใจ ให้ดูข้อมูลก่อนด้วย `SELECT` แล้วค่อยลบ

