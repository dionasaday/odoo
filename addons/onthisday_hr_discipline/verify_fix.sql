-- ============================================================
-- ✅ Script ตรวจสอบ Production Fix
-- ============================================================
-- ใช้สคริปต์นี้เพื่อตรวจสอบว่า metadata ครบถ้วนแล้ว

SELECT 
    model,
    COUNT(*) FILTER (WHERE relation_table IS NOT NULL AND column1 IS NOT NULL AND column2 IS NOT NULL) as with_metadata,
    COUNT(*) FILTER (WHERE relation_table IS NULL OR column1 IS NULL OR column2 IS NULL) as missing_metadata,
    COUNT(*) as total,
    CASE 
        WHEN COUNT(*) FILTER (WHERE relation_table IS NULL OR column1 IS NULL OR column2 IS NULL) = 0 
        THEN '✅ OK'
        ELSE '⚠️  NEEDS FIX'
    END as status
FROM ir_model_fields
WHERE ttype = 'many2many'
  AND model IN ('hr.employee', 'hr.contract', 'res.company', 'res.config.settings')
  AND relation IS NOT NULL
GROUP BY model
ORDER BY model;

-- ตรวจสอบรายละเอียด fields ที่ยังขาด metadata (ควรจะไม่มี)
SELECT 
    model,
    name,
    relation,
    relation_table,
    column1,
    column2
FROM ir_model_fields
WHERE ttype = 'many2many'
  AND model IN ('hr.employee', 'hr.contract', 'res.company', 'res.config.settings')
  AND relation IS NOT NULL
  AND (relation_table IS NULL OR column1 IS NULL OR column2 IS NULL)
ORDER BY model, name;

