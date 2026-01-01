-- ============================================================
-- คำสั่ง SQL สำหรับลบ Asset Records จากโมดูล om_account_asset
-- ที่ถูก disable แล้ว เพื่อแก้ปัญหา SCSS compilation error
-- ============================================================

-- 1. ดู asset records ที่จะลบก่อน (แนะนำให้รันก่อน)
SELECT id, name, path, bundle, active 
FROM ir_asset 
WHERE path LIKE '/om_account_asset/static/%'
ORDER BY id;

-- 2. ลบ asset records ทั้งหมดที่เกี่ยวข้องกับ om_account_asset
DELETE FROM ir_asset 
WHERE path LIKE '/om_account_asset/static/%'
AND (name = 'Account Assets' OR name = 'aAccount Assets SCSS');

-- 3. ตรวจสอบว่าลบสำเร็จแล้ว (ควรไม่มีผลลัพธ์)
SELECT id, name, path FROM ir_asset 
WHERE path LIKE '/om_account_asset/static/%';

-- ============================================================
-- วิธีใช้งาน:
-- 1. เปิด psql: psql -U odoo -d nt
-- 2. Copy-paste คำสั่ง SQL ข้างบน
-- 3. กด Enter
-- ============================================================

