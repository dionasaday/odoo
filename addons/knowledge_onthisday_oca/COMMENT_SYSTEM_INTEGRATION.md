# 📝 Comment System Integration Guide

## ✅ สิ่งที่สร้างเสร็จแล้ว

### Backend (100%)
- ✅ Model: `knowledge_article_comment.py`
- ✅ Views: `knowledge_article_comment_views.xml`
- ✅ Security: Access rights + Record rules
- ✅ Relationships: `comment_ids` in article model

### Frontend Components (95%)
- ✅ Text Selection Handler: `text_selection.js`
- ✅ Comment Manager: `comment_manager.js`
- ✅ Comment Overlay Component: `comment_overlay.js`
- ✅ Comment Overlay UI: `comment_overlay.xml` + `comment_overlay.scss`
- ✅ Manifest updated with assets

## ⏳ สิ่งที่ยังต้องทำ (Integration)

### 1. อัปเดต `knowledge_document_controller.js`

เพิ่ม import และ state:
```javascript
import { CommentOverlay } from './comment/comment_overlay';

// ใน setup() เพิ่ม state:
showCommentPanel: false, // Toggle comment panel visibility
```

เพิ่ม method:
```javascript
toggleCommentPanel() {
    this.state.showCommentPanel = !this.state.showCommentPanel;
}
```

### 2. อัปเดต `knowledge_document_view.xml`

แก้ไขปุ่ม Comments (บรรทัด 473):
```xml
<button 
    class="btn btn-link" 
    t-att-class="{'o_active': state.showCommentPanel}"
    t-on-click="() => this.toggleCommentPanel()"
    title="Comments">
    💬
    <t t-if="state.currentArticle and state.currentArticle.comment_count">
        <span class="badge" t-esc="state.currentArticle.comment_count"/>
    </t>
</button>
```

เพิ่ม Comment Overlay component หลัง article content:
```xml
<t t-if="state.currentArticle and state.showCommentPanel">
    <CommentOverlay 
        articleId="state.currentArticle.id"
        contentElement="contentRef.el"/>
</t>
```

### 3. เพิ่ม Comment Panel Layout

แก้ไข structure เพื่อรองรับ comment panel:
- Option 1: Side panel (ด้านขวา)
- Option 2: Bottom panel
- Option 3: Overlay (แบบ Google Docs)

## 🎯 ขั้นตอนการ Integration

1. **Import CommentOverlay component** ใน controller
2. **เพิ่ม state และ methods** สำหรับ comment panel
3. **แก้ไขปุ่ม Comments** ให้ toggle panel
4. **เพิ่ม CommentOverlay component** ใน XML template
5. **ปรับ layout** เพื่อรองรับ comment panel
6. **ทดสอบ basic features**

## 📚 เอกสารอ้างอิง

- GOOGLE_DOCS_COMMENT_SYSTEM.md - แผนการพัฒนาระบบ comment
- comment_overlay.js - Comment Overlay component
- comment_manager.js - Comment Manager logic
- text_selection.js - Text Selection Handler

---

**Last Updated**: 2025-12-05  
**Status**: ⏳ Awaiting Integration

