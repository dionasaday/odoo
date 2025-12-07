# คำแนะนำสำหรับ Debug Highlight ที่ไม่แสดงผล

## ขั้นตอนการตรวจสอบ

### 1. ตรวจสอบว่า Highlight ถูกสร้างหรือไม่

1. เปิด Browser Console (F12 > Console tab)
2. เปิดบทความและกดปุ่ม Comments (💬)
3. เลือกข้อความในบทความ
4. ดู logs ใน Console ควรเห็น:
   - `highlightSelectedText called`
   - `Created span element`
   - `surroundContents successful`
   - `Highlight created successfully`

### 2. ตรวจสอบ DOM Element

1. เปิด Browser DevTools (F12 > Elements/Inspector tab)
2. ใช้ Selector tool (กด Ctrl+Shift+C หรือ Cmd+Shift+C)
3. Hover ไปที่ข้อความที่เลือก
4. ตรวจสอบว่าเห็น `<span class="o_knowledge_comment_temp_highlight">` หรือไม่

### 3. ตรวจสอบ Computed Styles

1. ใน Elements tab, คลิกขวาที่ `<span>` element ที่มี class `o_knowledge_comment_temp_highlight`
2. เลือก "Inspect"
3. ดูที่ Styles panel ทางด้านขวา
4. ตรวจสอบ:
   - `background-color` ควรเป็น `#ffeb3b` หรือ `rgb(255, 235, 59)`
   - `display` ควรเป็น `inline`
   - `visibility` ควรเป็น `visible`
   - `opacity` ควรเป็น `1`

### 4. ตรวจสอบว่า Highlight ถูก Override หรือไม่

1. ใน Styles panel, ดูที่ "Computed" tab
2. ตรวจสอบ `background-color`
3. ดูว่ามี CSS rule อื่นที่ override หรือไม่ (แสดงเป็น strikethrough)
4. ดูที่ "Box Model" ว่ามีขนาดหรือไม่

### 5. ตรวจสอบด้วย Console Commands

รันคำสั่งเหล่านี้ใน Console:

```javascript
// หา highlight elements ทั้งหมด
document.querySelectorAll('.o_knowledge_comment_temp_highlight')

// ตรวจสอบ highlight element แรก
const highlight = document.querySelector('.o_knowledge_comment_temp_highlight')
if (highlight) {
    console.log('Found highlight:', highlight)
    console.log('Text:', highlight.textContent)
    console.log('Computed style:', window.getComputedStyle(highlight).backgroundColor)
    console.log('Inline style:', highlight.getAttribute('style'))
    console.log('In DOM:', highlight.parentNode !== null)
}
```

## ปัญหาที่เป็นไปได้และวิธีแก้

### ปัญหา 1: Highlight ไม่ถูกสร้าง
- **สาเหตุ**: `surroundContents` ล้มเหลว
- **แก้ไข**: ตรวจสอบ logs ใน Console ว่ามี error หรือไม่

### ปัญหา 2: Highlight ถูกสร้างแต่ไม่เห็น
- **สาเหตุ**: CSS ถูก override
- **แก้ไข**: ตรวจสอบ Computed Styles และใช้ `!important`

### ปัญหา 3: Highlight หายไปทันที
- **สาเหตุ**: ถูกลบโดย code อื่น
- **แก้ไข**: ตรวจสอบว่า `removeTemporaryHighlight()` ถูกเรียกหรือไม่

## ข้อมูลเพิ่มเติม

ถ้ายังมีปัญหา ให้ส่ง:
1. Screenshot ของ Elements tab ที่แสดง highlight element
2. Screenshot ของ Styles panel ที่แสดง computed styles
3. Logs จาก Console
4. คำอธิบายว่าทำอะไรก่อนที่ highlight จะหายไป

