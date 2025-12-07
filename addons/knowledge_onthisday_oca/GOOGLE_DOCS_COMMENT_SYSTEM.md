# 📝 Google Docs-Style Comment System สำหรับ Knowledge Base

## 🎯 ภาพรวม

เอกสารนี้อธิบายการพัฒนาระบบ Comment แบบ Google Docs สำหรับโมดูล `knowledge_onthisday_oca` ซึ่งจะทำให้ผู้ใช้สามารถ:

1. ✅ เลือกข้อความในบทความและเพิ่ม comment
2. ✅ แสดง comment overlay ด้านขวาของเอกสาร
3. ✅ Reply ใน comment thread
4. ✅ Mention ผู้ใช้อื่นด้วย @
5. ✅ Resolve/Unresolve comments
6. ✅ Real-time collaboration (เห็น comment ใหม่ทันที)

---

## ✅ ความเป็นไปได้ (Feasibility)

### พื้นฐานที่มีอยู่แล้ว:

1. ✅ **mail.thread & mail.activity.mixin**: โมดูลมีอยู่แล้ว
   - `knowledge.article` มี `_inherit = ['mail.thread', 'mail.activity.mixin']`
   - รองรับ chatter widget ใน form view

2. ✅ **Odoo Real-time Support**:
   - WebSocket/Long Polling สำหรับ real-time updates
   - Bus service สำหรับ notifications

3. ✅ **JavaScript Framework**:
   - Owl Framework (Odoo 19)
   - Component-based architecture

---

## 🏗️ Architecture Design

### 1. Database Model

```python
# models/knowledge_article_comment.py
class KnowledgeArticleComment(models.Model):
    _name = 'knowledge.article.comment'
    _description = 'Knowledge Article Comment'
    _inherit = ['mail.thread']
    _order = 'create_date asc'
    
    article_id = fields.Many2one(
        'knowledge.article',
        string='Article',
        required=True,
        ondelete='cascade'
    )
    
    # Text Selection Info
    selected_text = fields.Text(
        string='Selected Text',
        required=True,
        help='The text that was selected when comment was created'
    )
    
    # Range/Position Info (for highlighting)
    start_offset = fields.Integer(
        string='Start Offset',
        required=True,
        help='Character offset from start of content'
    )
    
    end_offset = fields.Integer(
        string='End Offset',
        required=True,
        help='Character offset from end of selection'
    )
    
    # XPath or CSS selector for element containing selection
    element_selector = fields.Char(
        string='Element Selector',
        help='CSS selector or XPath to locate the element containing selection'
    )
    
    # Comment Content
    body = fields.Html(
        string='Comment',
        required=True,
        help='Comment content (supports HTML)'
    )
    
    # Status
    resolved = fields.Boolean(
        string='Resolved',
        default=False,
        tracking=True,
        help='Whether this comment has been resolved'
    )
    
    resolved_by = fields.Many2one(
        'res.users',
        string='Resolved By',
        help='User who resolved this comment'
    )
    
    resolved_date = fields.Datetime(
        string='Resolved Date',
        help='Date when comment was resolved'
    )
    
    # Threading
    parent_id = fields.Many2one(
        'knowledge.article.comment',
        string='Parent Comment',
        ondelete='cascade',
        help='Parent comment if this is a reply'
    )
    
    child_ids = fields.One2many(
        'knowledge.article.comment',
        'parent_id',
        string='Replies',
        help='Replies to this comment'
    )
    
    # Mentions
    mentioned_user_ids = fields.Many2many(
        'res.users',
        'knowledge_comment_mention_rel',
        'comment_id',
        'user_id',
        string='Mentioned Users',
        help='Users mentioned in this comment with @'
    )
    
    # Author
    author_id = fields.Many2one(
        'res.users',
        string='Author',
        default=lambda self: self.env.user,
        required=True,
        help='User who created this comment'
    )
    
    # Highlight Color (for UI)
    highlight_color = fields.Char(
        string='Highlight Color',
        default='#ffeb3b',  # Yellow (Google Docs default)
        help='Color used to highlight selected text'
    )
```

### 2. JavaScript Component Structure

```
static/src/
├── js/
│   ├── comment/
│   │   ├── comment_overlay.js       # Comment overlay UI
│   │   ├── comment_manager.js       # Comment management logic
│   │   ├── text_selection.js        # Text selection handler
│   │   └── comment_thread.js        # Comment threading UI
│   └── knowledge_document_controller.js (แก้ไขเพิ่มเติม)
├── xml/
│   └── comment/
│       ├── comment_overlay.xml      # Comment overlay template
│       └── comment_thread.xml       # Comment thread template
└── scss/
    └── comment/
        └── comment_overlay.scss     # Comment overlay styles
```

### 3. Features Implementation

#### A. Text Selection & Highlighting

```javascript
// static/src/js/comment/text_selection.js
class TextSelectionHandler {
    /**
     * Get selected text and its position
     */
    getSelection() {
        const selection = window.getSelection();
        if (selection.rangeCount === 0) return null;
        
        const range = selection.getRangeAt(0);
        const selectedText = range.toString();
        
        if (!selectedText.trim()) return null;
        
        // Calculate offsets
        const contentEl = this.getContentElement();
        const startOffset = this.getTextOffset(contentEl, range.startContainer, range.startOffset);
        const endOffset = this.getTextOffset(contentEl, range.endContainer, range.endOffset);
        
        // Get element selector
        const elementSelector = this.getElementSelector(range.commonAncestorContainer);
        
        return {
            text: selectedText,
            startOffset,
            endOffset,
            elementSelector,
            range: range.cloneRange()
        };
    }
    
    /**
     * Highlight selected text with comment marker
     */
    highlightText(commentId, startOffset, endOffset, color = '#ffeb3b') {
        // Create highlight element
        const highlight = document.createElement('span');
        highlight.className = 'o_knowledge_comment_highlight';
        highlight.setAttribute('data-comment-id', commentId);
        highlight.style.backgroundColor = color;
        highlight.style.cursor = 'pointer';
        
        // Apply highlight using Range API
        // ...
    }
}
```

#### B. Comment Overlay

```javascript
// static/src/js/comment/comment_overlay.js
class CommentOverlay extends Component {
    static template = "knowledge_onthisday_oca.CommentOverlay";
    
    setup() {
        this.orm = useService("orm");
        this.bus = useService("bus_service");
        
        this.state = useState({
            comments: [],           // Comments for current article
            selectedComment: null,  // Currently selected comment
            isCreating: false,      // Is creating new comment
            selectedText: null,     // Currently selected text
        });
    }
    
    /**
     * Show comment overlay for selected text
     */
    async onCreateComment(selection) {
        this.state.isCreating = true;
        this.state.selectedText = selection;
        
        // Show overlay at selection position
        this._positionOverlay(selection);
    }
    
    /**
     * Position overlay next to selected text
     */
    _positionOverlay(selection) {
        const rect = selection.range.getBoundingClientRect();
        const overlay = this.overlayRef.el;
        
        overlay.style.top = `${rect.top}px`;
        overlay.style.left = `${rect.right + 20}px`; // 20px to the right
        overlay.style.display = 'block';
    }
}
```

#### C. Comment Threading

```javascript
// static/src/js/comment/comment_thread.js
class CommentThread extends Component {
    static template = "knowledge_onthisday_oca.CommentThread";
    
    /**
     * Reply to comment
     */
    async onReply(commentId, replyText, mentionedUsers = []) {
        const result = await this.orm.call(
            'knowledge.article.comment',
            'create',
            [{
                parent_id: commentId,
                body: replyText,
                mentioned_user_ids: mentionedUsers.map(u => u.id),
                // ... other fields
            }]
        );
        
        // Notify mentioned users
        await this._notifyMentionedUsers(mentionedUsers);
        
        // Refresh comment thread
        await this.loadComments();
    }
}
```

#### D. Real-time Updates

```javascript
// In knowledge_document_controller.js
setup() {
    // ... existing code ...
    
    // Subscribe to comment updates
    this.bus = useService("bus_service");
    
    onMounted(() => {
        this.bus.subscribe(
            'knowledge.article.comment',
            this._onCommentUpdate.bind(this)
        );
    });
}

_onCommentUpdate(message) {
    if (message.type === 'comment.created' || message.type === 'comment.updated') {
        // Refresh comments
        this.loadComments();
    }
}
```

---

## 📋 Implementation Plan

### Phase 1: Basic Comment System (2-3 สัปดาห์)

1. **Database Model**
   - [ ] สร้าง `knowledge.article.comment` model
   - [ ] เพิ่ม security/access rights
   - [ ] สร้าง XML views (list, form)

2. **Text Selection**
   - [ ] Implement text selection handler
   - [ ] Calculate text offsets
   - [ ] Store selection metadata

3. **Basic UI**
   - [ ] Comment overlay component
   - [ ] Comment list/thread UI
   - [ ] Basic styling

### Phase 2: Advanced Features (2-3 สัปดาห์)

4. **Comment Threading**
   - [ ] Reply to comments
   - [ ] Thread display
   - [ ] Nested replies

5. **Mention System**
   - [ ] @ mention detection
   - [ ] User autocomplete
   - [ ] Notification to mentioned users

6. **Highlighting**
   - [ ] Text highlighting with colors
   - [ ] Highlight persistence
   - [ ] Click highlight to show comment

### Phase 3: Real-time & Polish (1-2 สัปดาห์)

7. **Real-time Collaboration**
   - [ ] WebSocket integration
   - [ ] Live comment updates
   - [ ] Presence indicators

8. **Resolve System**
   - [ ] Resolve/unresolve comments
   - [ ] Resolved comment styling
   - [ ] Filter resolved comments

9. **Polish & Testing**
   - [ ] Mobile responsive
   - [ ] Performance optimization
   - [ ] User testing

---

## 🔧 Technical Considerations

### 1. Text Selection Challenges

**ปัญหา:**
- HTML content มี nested elements
- การคำนวณ offset ต้องคำนึงถึง HTML structure
- การ highlight อาจถูก overwrite เมื่อ content เปลี่ยนแปลง

**วิธีแก้:**
- ใช้ `TreeWalker` API สำหรับ traverse DOM
- เก็บทั้ง offset และ element selector
- ใช้ `MutationObserver` เพื่อ detect content changes

### 2. Performance

**ปัญหา:**
- จำนวน comments มากอาจช้า
- Real-time updates อาจส่งผลต่อ performance

**วิธีแก้:**
- Lazy loading สำหรับ comments
- Debounce real-time updates
- Virtual scrolling สำหรับ comment list

### 3. Security

- ✅ ใช้ Odoo's access rights
- ✅ ตรวจสอบ permissions ก่อนสร้าง/แก้ไข comment
- ✅ Sanitize HTML input (Odoo ทำให้แล้ว)

---

## 🎨 UI/UX Design

### Comment Overlay Layout

```
┌─────────────────────────────────────────────────┐
│  Article Content                                │
│                                                 │
│  This is some text [highlighted] and more...   │
│                            ┌─────────────────┐  │
│                            │ 💬 Comment Box  │  │
│                            │                 │  │
│                            │ Author: User    │  │
│                            │ "Great point!"  │  │
│                            │                 │  │
│                            │ [Reply] [✓]     │  │
│                            └─────────────────┘  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Comment Thread UI

```
┌─────────────────────────────────────────────────┐
│  💬 Comments (5)                                │
├─────────────────────────────────────────────────┤
│  👤 John Doe                                    │
│  "This section needs more detail"               │
│  [Reply] [Resolve]                              │
│    └─ 👤 Jane Smith (replied)                   │
│       "I'll add more info"                      │
│       [Reply]                                   │
├─────────────────────────────────────────────────┤
│  👤 Admin                                       │
│  "@john Please review this section"             │
│  [Reply] [Resolve]                              │
└─────────────────────────────────────────────────┘
```

---

## 📚 References

1. **Odoo Mail Thread**: https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html#mail-thread
2. **Odoo Bus Service**: https://www.odoo.com/documentation/19.0/developer/reference/javascript/services.html#bus-service
3. **Range API**: https://developer.mozilla.org/en-US/docs/Web/API/Range
4. **Selection API**: https://developer.mozilla.org/en-US/docs/Web/API/Selection

---

## ✅ สรุป

**การพัฒนา Google Docs-style comment system เป็นไปได้** โดย:

1. ✅ ใช้ Odoo's existing infrastructure (mail.thread, bus service)
2. ✅ ใช้ JavaScript/Range API สำหรับ text selection
3. ✅ ใช้ Owl Framework สำหรับ UI components
4. ✅ ใช้ WebSocket สำหรับ real-time collaboration

**ข้อดี:**
- ✅ Integrated กับ Odoo ecosystem
- ✅ ใช้ existing security/access rights
- ✅ Real-time updates built-in
- ✅ Mobile-friendly architecture

**ข้อควรระวัง:**
- ⚠️ Text selection ใน HTML ซับซ้อน
- ⚠️ ต้องจัดการ edge cases มาก
- ⚠️ ต้องทดสอบ performance อย่างละเอียด

---

**Last Updated**: 2025-12-05  
**Status**: 📋 Planning Phase

