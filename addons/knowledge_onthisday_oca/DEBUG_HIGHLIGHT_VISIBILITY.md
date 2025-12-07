# Debug Highlight Visibility Issue

## สถานการณ์

จาก logs ที่ได้รับ:
- ✅ Highlight ถูกสร้างสำเร็จแล้ว
- ✅ Highlight อยู่ใน DOM แล้ว (`inDOM: true`)
- ✅ CSS ถูก apply แล้ว (`backgroundColor: "rgb(255, 235, 59)"`)
- ✅ Highlight มีขนาดแล้ว (`width: 226.53px, height: 23px`)
- ✅ `hasSize: true`

แต่ highlight ยังไม่แสดงผล

## สาเหตุที่เป็นไปได้

1. **CSS ถูก override โดย Odoo's WYSIWYG editor**
   - Odoo 19 ใช้ ProseMirror/Quill ซึ่งอาจมี CSS ที่ override highlight
   - อาจมี inline styles ที่ถูก apply จาก editor

2. **Browser selection ยังครอบคลุมอยู่**
   - Browser selection อาจซ่อน highlight แม้ว่าจะ clear selection แล้ว

3. **CSS specificity ไม่พอ**
   - CSS rules ของเราอาจถูก override โดย CSS ของ Odoo

## วิธีแก้ไขที่ทำไปแล้ว

1. ✅ เพิ่ม CSS rules ที่มีความเฉพาะเจาะจงสูงขึ้น
2. ✅ เพิ่ม `background-clip: padding-box` เพื่อป้องกัน background ถูกซ่อน
3. ✅ เพิ่ม `::before` pseudo-element เป็น backup
4. ✅ ใช้ `!important` ในทุก CSS properties

## ขั้นตอน Debug

### 1. ตรวจสอบใน Browser DevTools

1. เปิด Elements/Inspector tab
2. ใช้ Selector tool (Ctrl+Shift+C หรือ Cmd+Shift+C)
3. คลิกที่ข้อความที่เลือก
4. ตรวจสอบว่าเห็น `<span class="o_knowledge_comment_temp_highlight">` หรือไม่

### 2. ตรวจสอบ Styles Panel

ใน Elements tab:
- ดูที่ Styles panel (ด้านขวา)
- ตรวจสอบว่า `background-color` ถูก apply หรือไม่
- ดูว่ามี CSS rule อื่นที่ override (แสดงเป็น strikethrough) หรือไม่

### 3. ตรวจสอบ Computed Styles

1. เปิด Computed tab ใน Styles panel
2. ตรวจสอบ `background-color` - ควรเป็น `rgb(255, 235, 59)`
3. ตรวจสอบ `display` - ควรเป็น `inline`
4. ตรวจสอบ `visibility` - ควรเป็น `visible`
5. ตรวจสอบ `opacity` - ควรเป็น `1`

### 4. รันคำสั่งใน Console

```javascript
const highlight = document.querySelector('.o_knowledge_comment_temp_highlight');
if (highlight) {
    console.log('=== Highlight Found ===');
    console.log('Element:', highlight);
    console.log('Text:', highlight.textContent);
    
    const computed = window.getComputedStyle(highlight);
    console.log('=== Computed Styles ===');
    console.log('backgroundColor:', computed.backgroundColor);
    console.log('background:', computed.background);
    console.log('display:', computed.display);
    console.log('width:', computed.width);
    console.log('height:', computed.height);
    
    const rect = highlight.getBoundingClientRect();
    console.log('=== Bounding Rect ===');
    console.log('width:', rect.width, 'height:', rect.height);
    
    // Try to force visibility
    highlight.style.setProperty('background-color', '#ffeb3b', 'important');
    highlight.style.setProperty('background', '#ffeb3b', 'important');
    highlight.style.setProperty('box-shadow', '0 0 0 2px #ffeb3b', 'important');
    
    console.log('=== After Force ===');
    console.log('backgroundColor:', window.getComputedStyle(highlight).backgroundColor);
} else {
    console.log('❌ No highlight found!');
}
```

### 5. ตรวจสอบว่า Highlight อยู่ใน DOM จริงๆ

```javascript
// Search for all highlight elements
const highlights = document.querySelectorAll('.o_knowledge_comment_temp_highlight');
console.log('Found highlights:', highlights.length);
highlights.forEach((h, i) => {
    console.log(`Highlight ${i + 1}:`, h);
    console.log('  Text:', h.textContent);
    console.log('  Parent:', h.parentNode);
    console.log('  Computed bg:', window.getComputedStyle(h).backgroundColor);
});
```

## วิธีแก้ไขเพิ่มเติม

### วิธีที่ 1: ใช้ Box Shadow แทน Background

ถ้า background-color ไม่แสดงผล อาจลองใช้ box-shadow แทน:

```css
.o_knowledge_comment_temp_highlight {
    box-shadow: 0 0 0 4px #ffeb3b inset !important;
}
```

### วิธีที่ 2: ใช้ Outline แทน Background

```css
.o_knowledge_comment_temp_highlight {
    outline: 2px solid #ffeb3b !important;
    outline-offset: -2px !important;
}
```

### วิธีที่ 3: ใช้ Border แทน Background

```css
.o_knowledge_comment_temp_highlight {
    border-bottom: 3px solid #ffeb3b !important;
}
```

### วิธีที่ 4: ใช้ Text Decoration

```css
.o_knowledge_comment_temp_highlight {
    text-decoration: underline !important;
    text-decoration-color: #ffeb3b !important;
    text-decoration-thickness: 3px !important;
}
```

## ถ้ายังไม่ได้ผล

กรุณาส่ง:
1. Screenshot ของ Elements tab ที่แสดง highlight element
2. Screenshot ของ Styles panel ที่แสดง computed styles
3. Console logs ทั้งหมด
4. ข้อมูลว่าอยู่ในโหมด edit หรือ view mode

