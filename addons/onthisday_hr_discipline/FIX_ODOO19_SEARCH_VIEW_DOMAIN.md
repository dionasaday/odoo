# แก้ไข Search View Domain สำหรับ Odoo 19

## ปัญหา

```
Invalid view hr.lateness.monthly_summary.search definition
```

## สาเหตุ

ใน Odoo search view, domain ใน XML **ไม่สามารถใช้ Python functions** เช่น:
- `context_today()`
- `relativedelta()`
- `.replace()`
- หรือ Python expressions อื่นๆ

Search view domain ต้องเป็น **static domain** หรือใช้ **date filter widget**

## วิธีแก้ไข

### 1. ลบ Dynamic Domain ที่ใช้ Python Functions

**เดิม (ไม่ทำงาน):**
```xml
<filter string="This Month" name="this_month" 
        domain="[('period_date', '>=', (context_today() - relativedelta(months=1)).replace(day=1))]"/>
```

**ใหม่ (ใช้ date filter widget):**
```xml
<filter string="Period Date" name="period_date" date="period_date"/>
```

### 2. ลบ Filter ที่ใช้ context_today()

**เดิม (ไม่ทำงาน):**
```xml
<filter string="This Year" name="this_year" domain="[('year','=', (context_today().year))]"/>
```

**ใหม่ (ลบออก หรือใช้ domain ใน action/context):**
```xml
<!-- Note: Dynamic year filter removed - use domain in action or context instead -->
```

### 3. ทางเลือก: ใช้ Domain ใน Action หรือ Context

ถ้าต้องการ dynamic domain สามารถทำได้ใน Python:

```python
# ใน action หรือ model method
action = {
    'name': 'My Action',
    'domain': [('year', '=', fields.Date.today().year)],
    # ...
}
```

## ไฟล์ที่แก้ไข

1. ✅ `views/lateness_monthly_summary_views.xml` - เปลี่ยนเป็น date filter widget
2. ✅ `views/my_summary_views.xml` - ลบ dynamic year filter

## สรุป

✅ แก้ไขเสร็จสมบูรณ์  
✅ XML syntax ถูกต้อง  
✅ ตามมาตรฐาน Odoo 19  
✅ ไม่มี dynamic Python expressions ใน search view domain แล้ว  

โมดูลพร้อมติดตั้งแล้ว!

