# -*- coding: utf-8 -*-
"""
Script to setup parent/child relationships for existing knowledge articles

═══════════════════════════════════════════════════════════════════════
วิธีใช้ (แนะนำ):
═══════════════════════════════════════════════════════════════════════

1. เปิด Odoo ใน Browser
2. ไปที่: Settings (⚙️) > Technical > Database Structure > Odoo Shell
3. Copy โค้ดทั้งหมดด้านล่าง (จากบรรทัด "env = self.env" ลงมา)
4. Paste ลงใน Odoo Shell
5. กด "Run" หรือกด Enter

═══════════════════════════════════════════════════════════════════════
หรือรันผ่าน Command Line:
═══════════════════════════════════════════════════════════════════════

docker compose exec odoo python3 /mnt/extra-addons/knowledge_onthisday_oca/setup_parent_child_relationships.py

═══════════════════════════════════════════════════════════════════════
"""

print("=" * 70)
print("Setting up Parent/Child Relationships for Knowledge Articles")
print("=" * 70)

# Get environment (เมื่อรันใน Odoo Shell, self.env จะมีอยู่แล้ว)
try:
    env = self.env
except NameError:
    # ถ้ารันผ่าน command line ต้อง setup environment เอง
    import odoo
    from odoo import api, SUPERUSER_ID
    from odoo.api import Environment
    
    db_name = 'odoo'  # เปลี่ยนชื่อ database ตามที่ใช้
    with api.Environment.manage():
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            env = Environment(cr, SUPERUSER_ID, {})

Article = env['knowledge.article']

# Get all active articles
articles = Article.search([('active', '=', True)], order='id')
print(f"\nFound {len(articles)} active articles:")

for article in articles:
    parent_name = article.parent_id.name if article.parent_id else "None"
    print(f"  ID {article.id}: {article.name[:60]}")
    print(f"    Current parent: {parent_name}")

# สร้างโครงสร้าง hierarchy
# โครงสร้างที่แนะนำ:
# - Article 1 (CAFÉ DIVISION) เป็น parent
# - Article 2 และ 3 เป็น children ของ Article 1

print("\n" + "=" * 70)
print("Creating Parent/Child Relationships...")
print("=" * 70)

# หา articles ตามชื่อ
article_1 = None
article_2 = None
article_3 = None

for article in articles:
    if "CAFÉ DIVISION" in article.name.upper() or "CAFE DIVISION" in article.name.upper():
        article_1 = article
        print(f"  ✓ Found Article 1 (Parent): {article.name[:60]}")
    elif "OPERATIONS & PROCUREMENT" in article.name.upper() or "OPERATIONS AND PROCUREMENT" in article.name.upper():
        article_2 = article
        print(f"  ✓ Found Article 2 (Child): {article.name[:60]}")
    elif "BASKET DEX" in article.name.upper() or "BEP MHW" in article.name.upper():
        article_3 = article
        print(f"  ✓ Found Article 3 (Child): {article.name[:60]}")

# สร้าง relationships
updated_count = 0

if article_1 and article_2:
    # Article 2 เป็น child ของ Article 1
    if article_2.parent_id != article_1:
        article_2.write({'parent_id': article_1.id})
        print(f"\n  ✅ Set Article 2 as child of Article 1")
        updated_count += 1
    else:
        print(f"\n  ℹ️  Article 2 already has correct parent")

if article_1 and article_3:
    # Article 3 เป็น child ของ Article 1
    if article_3.parent_id != article_1:
        article_3.write({'parent_id': article_1.id})
        print(f"  ✅ Set Article 3 as child of Article 1")
        updated_count += 1
    else:
        print(f"  ℹ️  Article 3 already has correct parent")

# Commit changes (ถ้ารันใน Odoo Shell จะ commit อัตโนมัติ)
try:
    if hasattr(env.cr, 'commit') and not getattr(env, '_from_shell', False):
        env.cr.commit()
except:
    pass

print("\n" + "=" * 70)
print(f"✅ Updated {updated_count} article(s)")
print("=" * 70)

# แสดงผลลัพธ์
print("\nFinal structure:")
print("-" * 70)

for article in Article.search([('active', '=', True)], order='id'):
    parent_name = article.parent_id.name if article.parent_id else "None (Root)"
    child_count = len(article.child_ids)
    
    print(f"  ID {article.id}: {article.name[:50]}")
    print(f"    Parent: {parent_name}")
    print(f"    Children: {child_count}")
    
    if child_count > 0:
        for child in article.child_ids:
            print(f"      └─ {child.name[:45]}")

print("\n" + "=" * 70)
print("✅ Done! Please refresh your browser to see the tree structure.")
print("=" * 70)

