# 🔐 คู่มือการตั้งค่าสิทธิ์โมดูล Knowledge Base

## 📋 สรุปการตั้งค่าสิทธิ์ปัจจุบัน

โมดูล `knowledge_onthisday_oca` มีการตั้งค่าสิทธิ์ 2 ระดับ:

### 1. Access Rights (Model-Level Security)
กำหนดสิทธิ์การเข้าถึง model โดยรวม

### 2. Record Rules (Row-Level Security)
กำหนดสิทธิ์การเข้าถึงข้อมูลแต่ละ record

---

## 🔍 สถานะปัจจุบัน

### Access Rights (`security/ir.model.access.csv`)

| Model | Group | Read | Write | Create | Delete |
|-------|-------|------|-------|--------|--------|
| `knowledge.article` | `base.group_user` (User ทั่วไป) | ✅ | ✅ | ✅ | ❌ |
| `knowledge.article` | `base.group_system` (Admin) | ✅ | ✅ | ✅ | ✅ |
| `knowledge.article.category` | `base.group_user` | ✅ | ✅ | ✅ | ❌ |
| `knowledge.article.category` | `base.group_system` | ✅ | ✅ | ✅ | ✅ |
| `knowledge.article.tag` | `base.group_user` | ✅ | ✅ | ✅ | ❌ |
| `knowledge.article.tag` | `base.group_system` | ✅ | ✅ | ✅ | ✅ |

### Record Rules (`security/ir_rule.xml`)

#### สำหรับ User ทั่วไป (`base.group_user`):
- ✅ **Articles**: เห็นเฉพาะ articles ที่ `active = True` (ไม่เห็น trash)
- ✅ **Categories**: เห็นทั้งหมด
- ✅ **Tags**: เห็นทั้งหมด

#### สำหรับ Admin (`base.group_system`):
- ✅ **Articles**: เห็นทั้งหมด (รวม trash/inactive)
- ✅ **Categories**: เห็นทั้งหมด
- ✅ **Tags**: เห็นทั้งหมด

---

## 🎯 การตั้งค่าสิทธิ์ตาม Roles

### Scenario 1: User ทั่วไป (Default)

**สิทธิ์ที่ได้รับ:**
- ✅ อ่าน articles ทั้งหมด (เฉพาะ active)
- ✅ สร้าง articles ใหม่
- ✅ แก้ไข articles
- ❌ **ไม่สามารถลบ articles** (สามารถ archive ได้ แต่ไม่สามารถ delete ถาวร)
- ✅ จัดการ Categories และ Tags
- ❌ ไม่เห็น Trash

**วิธีการตั้งค่า:**
- User จะอยู่ใน `base.group_user` โดยอัตโนมัติ
- ไม่ต้องตั้งค่าเพิ่มเติม

---

### Scenario 2: Admin/System User

**สิทธิ์ที่ได้รับ:**
- ✅ อ่าน articles ทั้งหมด (รวม trash/inactive)
- ✅ สร้าง articles ใหม่
- ✅ แก้ไข articles
- ✅ **ลบ articles ถาวร** (permanent delete)
- ✅ จัดการ Categories และ Tags
- ✅ เห็นและกู้คืน Trash

**วิธีการตั้งค่า:**
1. ไปที่ **Settings > Users & Companies > Users**
2. เลือก user ที่ต้องการเป็น Admin
3. ไปที่ tab **Access Rights**
4. ติ๊กเลือก **Administration > Access Rights**
   - หรือเลือก group: **Settings / Administrator**
5. บันทึก

**หรือตั้งค่าผ่าน Technical Menu:**
1. ไปที่ **Settings > Technical > Users & Companies > Users**
2. เลือก user
3. ใน tab **Access Rights** ให้เลือก:
   - ✅ `Administration / Settings`
   - ✅ `Administration / Access Rights`

---

### Scenario 3: สร้าง Custom Group (สำหรับทีมเฉพาะ)

ตัวอย่าง: สร้าง group สำหรับ "Knowledge Manager"

#### ขั้นตอนที่ 1: สร้างไฟล์ `security/knowledge_groups.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<odoo>
    <data noupdate="1">
        
        <!-- Knowledge Manager Group -->
        <record id="group_knowledge_manager" model="res.groups">
            <field name="name">Knowledge Manager</field>
            <field name="category_id" ref="base.module_category_knowledge"/>
            <field name="comment">สามารถจัดการ Knowledge Base ได้ทั้งหมด รวมถึงลบ articles</field>
        </record>
        
    </data>
</odoo>
```

#### ขั้นตอนที่ 2: อัปเดต `security/ir.model.access.csv`

เพิ่มบรรทัดใหม่:
```csv
access_knowledge_article_manager,knowledge.article.manager,model_knowledge_article,group_knowledge_manager,1,1,1,1
access_knowledge_article_category_manager,knowledge.article.category.manager,model_knowledge_article_category,group_knowledge_manager,1,1,1,1
access_knowledge_article_tag_manager,knowledge.article.tag.manager,model_knowledge_article_tag,group_knowledge_manager,1,1,1,1
```

#### ขั้นตอนที่ 3: อัปเดต `security/ir_rule.xml`

เพิ่ม record rule:
```xml
<!-- Rule: Knowledge Managers can see all articles -->
<record id="knowledge_article_manager_rule" model="ir.rule">
    <field name="name">Knowledge Article: Manager Access - All Articles</field>
    <field name="model_id" ref="model_knowledge_article"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('group_knowledge_manager'))]"/>
</record>
```

#### ขั้นตอนที่ 4: เพิ่มไฟล์ใน `__manifest__.py`

```python
'data': [
    # ... existing files ...
    'security/knowledge_groups.xml',  # เพิ่มบรรทัดนี้
],
```

---

## 📝 ตัวอย่างการใช้งาน

### ตรวจสอบสิทธิ์ของ User ปัจจุบัน

**ผ่าน Odoo Shell:**
```python
# เช็คว่า user ปัจจุบันอยู่ใน group ไหน
user = env.user
print("User:", user.name)
print("Groups:", user.groups_id.mapped('name'))

# เช็คว่าสามารถอ่าน/เขียน articles ได้ไหม
article = env['knowledge.article'].search([], limit=1)
if article:
    print("Can read:", article.check_access_rights('read', raise_exception=False))
    print("Can write:", article.check_access_rights('write', raise_exception=False))
    print("Can delete:", article.check_access_rights('unlink', raise_exception=False))
```

### ตรวจสอบ Record Rules

**ผ่าน Odoo Shell:**
```python
# เช็คว่า user เห็น articles กี่ตัว
articles = env['knowledge.article'].search([])
print(f"Total articles visible: {len(articles)}")

# เช็ค domain ที่ใช้
rules = env['ir.rule'].search([('model_id.model', '=', 'knowledge.article')])
for rule in rules:
    print(f"Rule: {rule.name}")
    print(f"  Domain: {rule.domain_force}")
    print(f"  Groups: {rule.groups_id.mapped('name')}")
```

---

## 🔧 การแก้ไขสิทธิ์

### วิธีที่ 1: แก้ไขผ่านไฟล์ (แนะนำสำหรับ Development)

1. แก้ไข `security/ir.model.access.csv` สำหรับ access rights
2. แก้ไข `security/ir_rule.xml` สำหรับ record rules
3. Upgrade module:
   ```bash
   docker compose exec odoo odoo -u knowledge_onthisday_oca -d your_database --stop-after-init
   docker compose restart odoo
   ```

### วิธีที่ 2: แก้ไขผ่าน Odoo UI (แนะนำสำหรับ Production)

1. ไปที่ **Settings > Technical > Security > Record Rules**
2. ค้นหา rules ที่เกี่ยวกับ `knowledge.article`
3. แก้ไข domain หรือ groups

หรือ

1. ไปที่ **Settings > Technical > Security > Access Rights**
2. ค้นหา access rights ที่เกี่ยวกับ `knowledge.article`
3. แก้ไข permissions

---

## ⚠️ ข้อควรระวัง

1. **Record Rules จะใช้ AND กับ Access Rights**
   - ถ้า Access Rights ไม่ให้อ่าน → ไม่เห็นเลย
   - ถ้า Record Rules ไม่ผ่าน → ไม่เห็น record นั้น

2. **การแก้ไข Record Rules ต้องระวัง**
   - Domain ที่ผิดอาจทำให้ users เห็นข้อมูลมากเกินไป หรือไม่เห็นเลย
   - ทดสอบก่อน deploy production

3. **Group `base.group_system` มีสิทธิ์เต็ม**
   - Bypass record rules ทั้งหมด
   - ใช้เฉพาะกับ System Administrators

4. **การลบ Articles**
   - User ทั่วไป: ไม่สามารถลบถาวร (perm_unlink = 0)
   - Admin: สามารถลบถาวรได้ (perm_unlink = 1)

---

## 📚 ตัวอย่าง Scenario เพิ่มเติม

### Scenario 4: เฉพาะผู้สร้างสามารถแก้ไขได้

**Record Rule:**
```xml
<record id="knowledge_article_creator_rule" model="ir.rule">
    <field name="name">Knowledge Article: Creator Only</field>
    <field name="model_id" ref="model_knowledge_article"/>
    <field name="domain_force">['|', ('create_uid', '=', user.id), ('write_uid', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>
```

### Scenario 5: แยกสิทธิ์ตาม Category

**Record Rule:**
```xml
<record id="knowledge_article_category_rule" model="ir.rule">
    <field name="name">Knowledge Article: Category Access</field>
    <field name="model_id" ref="model_knowledge_article"/>
    <field name="domain_force">[
        '|',
        ('category_id', '=', False),
        ('category_id.allowed_user_ids', 'in', [user.id])
    ]</field>
    <field name="groups" eval="[(4, ref('base.group_user'))]"/>
</record>
```

---

## ✅ Checklist การตั้งค่าสิทธิ์

- [ ] ตรวจสอบว่า Access Rights ถูกต้อง
- [ ] ตรวจสอบว่า Record Rules ทำงานตามต้องการ
- [ ] ทดสอบด้วย user หลาย roles
- [ ] ตรวจสอบว่า Admin เห็น Trash ได้
- [ ] ตรวจสอบว่า User ทั่วไปไม่เห็น Trash
- [ ] ตรวจสอบว่า User ทั่วไปไม่สามารถลบถาวรได้
- [ ] ทดสอบการสร้าง/แก้ไข/ลบ articles

---

## 📞 ติดต่อ

ถ้ามีคำถามเพิ่มเติมเกี่ยวกับการตั้งค่าสิทธิ์ กรุณาติดต่อทีมพัฒนาหรือดูเอกสาร Odoo Security Documentation

