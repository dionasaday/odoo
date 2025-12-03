/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, useRef, useEffect, onMounted, onWillUpdateProps, onRendered } from "@odoo/owl";

export class KnowledgeDocumentController extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.contentRef = useRef("content");
        this._userHistoryKeyPrefix = "knowledge_onthisday_history";
        
        this.state = useState({
            selectedArticleId: null,
            searchQuery: "",
            activeSection: "workspace", // workspace, favorites, shared, private
            articles: [],
            currentArticle: null,
            loading: false,
            currentUserId: null,
            expandedArticles: new Set(), // Track which articles are expanded
            expandedCategories: new Set(), // Track which categories are expanded
            showShareDialog: false, // Show share link dialog
            shareLink: null, // Generated share link
            selectedTagId: null, // Selected tag for filtering
            availableTags: [], // List of all available tags
        });

        onWillStart(async () => {
            // Load tags first
            await this.loadTags();
            
            // Get current user ID - try multiple methods
            // Note: User ID is optional for this component to work
            try {
                // Try method 1: Use res.users context (most reliable)
                const users = await this.orm.searchRead(
                    "res.users",
                    [["id", "=", this.orm.userId || 2]], // fallback to admin user
                    ["id"],
                    { limit: 1 }
                );
                if (users && users.length > 0) {
                    this.state.currentUserId = users[0].id;
                } else {
                    this.state.currentUserId = null;
                }
            } catch (error) {
                // User ID not available, continuing without user filtering
                // Continue without user ID - component will work but won't filter by user
                console.error("Error getting user ID:", error);
                this.state.currentUserId = null;
            }
            await this.loadArticles();
        });

        // According to Odoo 19 docs, use lifecycle hooks for DOM manipulation
        // onMounted: called after component is mounted to DOM
        onMounted(() => {
            if (this.contentRef.el && this.state.currentArticle) {
                this.renderContent();
            }
        });
        
        // onRendered: called after each render
        onRendered(() => {
            if (this.contentRef.el && this.state.currentArticle) {
                // Use requestAnimationFrame to ensure DOM is fully updated
                requestAnimationFrame(() => {
                    if (this.contentRef.el && this.state.currentArticle) {
                        this.renderContent();
                    }
                });
            }
        });
        
        // Also keep useEffect as fallback for content changes
        useEffect(() => {
            if (this.contentRef.el && this.state.currentArticle) {
                // Use a small delay to ensure DOM is ready
                setTimeout(() => {
                    if (this.contentRef.el && this.state.currentArticle) {
                        this.renderContent();
                    }
                }, 50);
            }
        }, () => [this.state.currentArticle?.id, this.state.currentArticle?.content]);
    }

    renderContent() {
        if (!this.contentRef.el) {
            return;
        }
        
        if (!this.state.currentArticle) {
            this.contentRef.el.innerHTML = "";
            return;
        }
        
        const content = this.state.currentArticle.content;
        
        // Helper function to check if stylesheets are loaded
        const areStylesheetsLoaded = () => {
            try {
                // Check if document is ready
                if (document.readyState === 'loading') {
                    return false;
                }
                // Check if we have stylesheets
                if (document.styleSheets.length === 0) {
                    return false;
                }
                // Check if at least one stylesheet is loaded
                let loadedCount = 0;
                for (let i = 0; i < document.styleSheets.length; i++) {
                    try {
                        const sheet = document.styleSheets[i];
                        if (sheet && sheet.cssRules) {
                            loadedCount++;
                        }
                    } catch (e) {
                        // Cross-origin stylesheet, assume loaded
                        loadedCount++;
                    }
                }
                return loadedCount > 0;
            } catch (e) {
                // If check fails, assume ready after a delay
                return true;
            }
        };
        
        // Render content with proper stylesheet loading check
        if (content && typeof content === 'string' && content.trim().length > 0) {
            // Wait for stylesheets to load to prevent FOUC and layout warnings
            if (!areStylesheetsLoaded()) {
                // Wait for stylesheets to be ready with multiple checks
                const checkAndRender = () => {
                    if (areStylesheetsLoaded()) {
                        if (this.contentRef.el && this.state.currentArticle) {
                            this.contentRef.el.innerHTML = content;
                            this.processTOCAfterRender();
                        }
                    } else {
                        // Retry after a short delay
                        requestAnimationFrame(() => {
                            setTimeout(checkAndRender, 50);
                        });
                    }
                };
                requestAnimationFrame(checkAndRender);
                return;
            }
            
            // Use requestAnimationFrame to ensure layout is ready
            requestAnimationFrame(() => {
                if (this.contentRef.el && this.state.currentArticle) {
                    this.contentRef.el.innerHTML = content;
                    this.processTOCAfterRender();
                }
            });
        } else {
            // Show empty state with edit button
            this.contentRef.el.innerHTML = `
                <div class='o_knowledge_empty_content' style='text-align: center; padding: 40px; color: #999;'>
                    <p style='font-size: 16px; margin-bottom: 20px;'>ยังไม่มีเนื้อหา</p>
                    <button class='btn btn-primary' style='padding: 10px 20px;'>
                        ✏️ แก้ไขเนื้อหา
                    </button>
                </div>
            `;
            // Add event listener for edit button
            const editButton = this.contentRef.el.querySelector('button');
            if (editButton) {
                editButton.addEventListener('click', () => {
                    this.onEditArticle();
                });
            }
        }
    }

    processTOCAfterRender() {
        if (!this.contentRef.el) {
            return;
        }
        
        // First, ensure all headings have IDs (in case content was re-rendered)
        const allHeadings = this.contentRef.el.querySelectorAll('h1, h2, h3, h4, h5, h6');
        allHeadings.forEach((heading, index) => {
            if (!heading.id || heading.id.trim() === '') {
                const headingText = heading.textContent.trim();
                let headingId = `toc-heading-${index}-${headingText.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 50)}`;
                // Ensure ID is unique
                let counter = 0;
                let finalHeadingId = headingId;
                while (this.contentRef.el.querySelector(`#${finalHeadingId}`)) {
                    counter++;
                    finalHeadingId = `${headingId}-${counter}`;
                }
                heading.id = finalHeadingId;
            }
        });
        
        // Find TOC element by any means
        const tocByDataAttr = this.contentRef.el.querySelector('[data-embedded="tableOfContent"]');
        const tocByClass = this.contentRef.el.querySelector('.tableOfContent');
        const tocById = this.contentRef.el.querySelector('#tableOfContent');
        const allDivs = this.contentRef.el.querySelectorAll('div');
        const tocDivs = Array.from(allDivs).filter(div => {
            const text = div.textContent || '';
            const hasTOCText = text.toLowerCase().includes('table of contents') || 
                              text.toLowerCase().includes('สารบัญ');
            const hasTOCAttr = div.hasAttribute('data-embedded') && 
                               div.getAttribute('data-embedded') === 'tableOfContent';
            return hasTOCText || hasTOCAttr;
        });
        
        // Try to find TOC by any means
        const tocElement = tocByDataAttr || tocByClass || tocById || (tocDivs.length > 0 ? tocDivs[0] : null);
        
        if (tocElement) {
            // Check if TOC is empty and needs to be generated
            const tocInnerHTML = tocElement.innerHTML || '';
            const tocInnerHTMLTrimmed = tocInnerHTML.trim();
            const tocIsEmpty = !tocInnerHTML || tocInnerHTMLTrimmed.length === 0;
            
            if (tocIsEmpty) {
                this.generateTOCContent(tocElement);
            }
        }
        
        // Also check after a short delay to ensure all styles are applied
        setTimeout(() => {
            if (this.contentRef.el) {
                // Re-check headings IDs in case content was re-rendered
                const allHeadingsDelayed = this.contentRef.el.querySelectorAll('h1, h2, h3, h4, h5, h6');
                allHeadingsDelayed.forEach((heading, index) => {
                    if (!heading.id || heading.id.trim() === '') {
                        const headingText = heading.textContent.trim();
                        let headingId = `toc-heading-${index}-${headingText.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 50)}`;
                        let counter = 0;
                        let finalHeadingId = headingId;
                        while (this.contentRef.el.querySelector(`#${finalHeadingId}`)) {
                            counter++;
                            finalHeadingId = `${headingId}-${counter}`;
                        }
                        heading.id = finalHeadingId;
                    }
                });
                
                const tocByDataAttrDelayed = this.contentRef.el.querySelector('[data-embedded="tableOfContent"]');
                const tocByClassDelayed = this.contentRef.el.querySelector('.tableOfContent');
                const tocByIdDelayed = this.contentRef.el.querySelector('#tableOfContent');
                const allDivsDelayed = this.contentRef.el.querySelectorAll('div');
                const tocDivsDelayed = Array.from(allDivsDelayed).filter(div => {
                    const text = div.textContent || '';
                    const hasTOCText = text.toLowerCase().includes('table of contents') || 
                                      text.toLowerCase().includes('สารบัญ');
                    const hasTOCAttr = div.hasAttribute('data-embedded') && 
                                       div.getAttribute('data-embedded') === 'tableOfContent';
                    return hasTOCText || hasTOCAttr;
                });
                
                const tocElementDelayed = tocByDataAttrDelayed || tocByClassDelayed || tocByIdDelayed || (tocDivsDelayed.length > 0 ? tocDivsDelayed[0] : null);
                
                if (tocElementDelayed) {
                    // Check if TOC is empty and needs to be generated (delayed check)
                    const tocInnerHTMLDelayed = tocElementDelayed.innerHTML || '';
                    const tocInnerHTMLTrimmedDelayed = tocInnerHTMLDelayed.trim();
                    const tocIsEmptyDelayed = !tocInnerHTMLDelayed || tocInnerHTMLTrimmedDelayed.length === 0;
                    
                    if (tocIsEmptyDelayed) {
                        this.generateTOCContent(tocElementDelayed);
                    }
                }
            }
        }, 200);
    }

    async loadArticles() {
        this.state.loading = true;
        try {
            // Load ALL categories first (ordered by sequence, then name)
            const allCategories = await this.orm.searchRead(
                "knowledge.article.category",
                [],
                ["id", "name", "icon", "code", "sequence"],
                { limit: 1000, order: "sequence, name" }
            );
            
            // Create category map with all categories
            const categoryMap = new Map();
            allCategories.forEach(cat => {
                // Parse category name if it's a JSON format (for translatable fields)
                let categoryName = cat.name || '';
                if (typeof categoryName === 'string' && categoryName.trim().startsWith('{')) {
                    try {
                        // Validate that it looks like JSON before parsing
                        const trimmed = categoryName.trim();
                        if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
                            const parsed = JSON.parse(trimmed);
                            // Validate parsed result is an object
                            if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
                                // Get first value from JSON object (usually 'en_US' or similar)
                                const values = Object.values(parsed);
                                if (values.length > 0 && typeof values[0] === 'string') {
                                    categoryName = values[0];
                                } else {
                                    categoryName = cat.name || '';
                                }
                            } else {
                                categoryName = cat.name || '';
                            }
                        } else {
                            // Doesn't look like valid JSON, use original
                            categoryName = cat.name || '';
                        }
                    } catch (e) {
                        // If parsing fails, use original name
                        console.warn("Failed to parse category name as JSON:", e);
                        categoryName = cat.name || '';
                    }
                }
                
                categoryMap.set(cat.id, {
                    id: cat.id,
                    name: categoryName,
                    icon: cat.icon || '📝',
                    code: cat.code || '',
                    sequence: cat.sequence || 999,
                    articles: []
                });
            });
            
            // Load articles
            const domain = this.getDomain();
            let articles = [];
            // According to Odoo 19 docs, start with minimal fields to avoid RPC errors
            // Then add more fields if successful
            const basicFields = ["id", "name", "active"];
            const extendedFields = ["category_id", "parent_id", "responsible_id"];
            const relationFields = ["favorite_user_ids", "shared_user_ids", "share_token", "tag_ids"];
            
            try {
                // Step 1: Try with basic fields only first
                articles = await this.orm.searchRead(
                    "knowledge.article",
                    domain,
                    basicFields,
                    { limit: 1000 }
                );
                
                // Step 2: If successful, read extended fields
                if (articles && articles.length > 0) {
                    const articleIds = articles.map(a => a.id);
                    try {
                        const extendedData = await this.orm.read(
                            "knowledge.article",
                            articleIds,
                            [...basicFields, ...extendedFields, ...relationFields]
                        );
                        // Merge extended data back into articles
                        const extendedMap = new Map(extendedData.map(a => [a.id, a]));
                        articles = articles.map(article => ({
                            ...article,
                            ...extendedMap.get(article.id)
                        }));
                    } catch (readError) {
                        // Continue with basic fields only
                    }
                    
                    // Compute share_link manually
                    const baseUrl = window.location.origin;
                    articles = articles.map(article => {
                        if (article.share_token) {
                            article.share_link = `${baseUrl}/knowledge/article/${article.share_token}`;
                        }
                        // Normalize responsible_name for display if available
                        if (article.responsible_id && Array.isArray(article.responsible_id) && article.responsible_id.length > 1) {
                            article.responsible_name = article.responsible_id[1];
                        }
                        return article;
                    });
                }
            } catch (searchReadError) {
                console.error("Error loading articles:", searchReadError);
                // Fallback: try search() only (no read)
                try {
                    const articleIds = await this.orm.search(
                        "knowledge.article",
                        domain,
                        { limit: 1000 }
                    );
                    
                    if (articleIds && articleIds.length > 0) {
                        // Try to read with minimal fields
                        try {
                            articles = await this.orm.read(
                                "knowledge.article",
                                articleIds,
                                basicFields
                            );
                        } catch (readError) {
                            // Last resort: create minimal article objects from IDs
                            articles = articleIds.map(id => ({
                                id: id,
                                name: `Article ${id}`,
                                active: true
                            }));
                        }
                    }
                } catch (searchError) {
                    // Last resort: try without active filter
                    try {
                        const fallbackDomain = domain.filter(d => d[0] !== 'active');
                        const articleIds = await this.orm.search(
                            "knowledge.article",
                            fallbackDomain.length > 0 ? fallbackDomain : [],
                            { limit: 1000 }
                        );
                        if (articleIds && articleIds.length > 0) {
                            try {
                                articles = await this.orm.read(
                                    "knowledge.article",
                                    articleIds,
                                    basicFields
                                );
                                // Filter active articles manually
                                if (articles && articles.length > 0) {
                                    articles = articles.filter(a => a.active !== false);
                                }
                            } catch (readError2) {
                                console.error("Error reading articles:", readError2);
                            }
                        }
                    } catch (fallbackError) {
                        console.error("Error in fallback search:", fallbackError);
                    }
                }
            }
            
            // Load responsible avatars (unique user ids)
            const responsibleIds = Array.from(
                new Set(
                    (articles || [])
                        .map(a => (Array.isArray(a.responsible_id) ? a.responsible_id[0] : null))
                        .filter(id => !!id)
                )
            );
            let responsibleMap = new Map();
            if (responsibleIds.length) {
                try {
                    const users = await this.orm.read(
                        "res.users",
                        responsibleIds,
                        ["id", "name", "image_128"]
                    );
                    responsibleMap = new Map(users.map(u => [u.id, u]));
                } catch (e) {
                    console.error("Error loading responsible avatars:", e);
                }
            }
            
            // Add category info and responsible info
            articles.forEach(article => {
                // Normalize responsible name/avatar
                if (article.responsible_id && Array.isArray(article.responsible_id) && article.responsible_id.length > 0) {
                    const respId = article.responsible_id[0];
                    const resp = responsibleMap.get(respId);
                    if (resp) {
                        article.responsible_name = resp.name;
                        article.responsible_avatar = resp.image_128;
                    } else if (article.responsible_id.length > 1) {
                        article.responsible_name = article.responsible_id[1];
                    }
                }

                if (article.category_id && article.category_id.length > 0) {
                    const categoryId = article.category_id[0];
                    const category = categoryMap.get(categoryId);
                    if (category) {
                        article.category_icon = category.icon;
                        article.category_name = category.name;
                        // Ensure category.articles array exists
                        if (!category.articles) {
                            category.articles = [];
                        }
                    } else {
                        // Category not found in map - might be deleted or not loaded
                        article.category_icon = '📝';
                        article.category_name = 'Unknown Category';
                        // Add to uncategorized instead
                        if (!categoryMap.has('uncategorized')) {
                            categoryMap.set('uncategorized', {
                                id: 'uncategorized',
                                name: 'Uncategorized',
                                icon: '📝',
                                code: 'uncategorized',
                                sequence: 9999,
                                articles: []
                            });
                        }
                        // Use uncategorized as fallback
                        article.category_id = ['uncategorized'];
                    }
                } else {
                    article.category_icon = '📝';
                    article.category_name = '';
                    // Add to uncategorized
                    if (!categoryMap.has('uncategorized')) {
                        categoryMap.set('uncategorized', {
                            id: 'uncategorized',
                            name: 'Uncategorized',
                            icon: '📝',
                            code: 'uncategorized',
                            sequence: 9999,
                            articles: []
                        });
                    }
                    article.category_id = ['uncategorized'];
                }
            });
            
            // Build tree structure
            // For favorites/shared/private sections, don't group by category
            if (this.state.activeSection === "favorites" || 
                this.state.activeSection === "shared" || 
                this.state.activeSection === "private") {
                // For these sections, create a flat list without category grouping
                const flatTree = this.buildFlatTree(articles);
                // Set articles directly without category structure
                this.state.articles = flatTree;
                return; // Early return for flat sections
            }
            
            // For workspace, use category grouping
            this.buildTree(articles, categoryMap);
            
            // Convert category map to array, sorted by sequence then name
            const categoryList = Array.from(categoryMap.values()).sort((a, b) => {
                // First sort by sequence (lower number = higher priority)
                if (a.sequence !== b.sequence) {
                    return (a.sequence || 999) - (b.sequence || 999);
                }
                // If sequence is same, sort by name
                return (a.name || '').localeCompare(b.name || '');
            });
            
            // IMPORTANT: Create a new array to trigger reactivity
            // Also create new objects for each category to ensure reactivity
            const newCategoryList = categoryList.map(cat => ({
                ...cat,
                articles: cat.articles ? [...cat.articles] : []
            }));
            this.state.articles = newCategoryList;

            // Auto-expand all categories by default when in workspace section
            if (this.state.activeSection === 'workspace' || this.state.activeSection === null || this.state.activeSection === undefined) {
                // Create new Set to ensure reactivity
                const newExpandedSet = new Set();
                categoryList.forEach(category => {
                    // Always expand categories in workspace, even if empty
                    newExpandedSet.add(category.id);
                });
                // IMPORTANT: Use Object.assign or direct assignment to trigger reactivity properly
                // Don't mutate the Set directly, create a new one
                this.state.expandedCategories = newExpandedSet;
            }
        } catch (error) {
            // Error loading articles - will be handled by UI showing empty state
            console.error("Error loading articles:", error);
            console.error("Error details:", {
                message: error.message,
                stack: error.stack,
                domain: this.getDomain(),
                activeSection: this.state.activeSection,
                currentUserId: this.state.currentUserId
            });
            this.state.articles = [];
        } finally {
            this.state.loading = false;
        }
    }

    getDomain() {
        // For workspace, show all active articles (no additional filters)
        // For other sections, apply specific filters
        const domain = [];
        
        // Try to filter by active, but if it causes RPC error, we'll handle it in loadArticles
        // Note: Some Odoo versions or configurations might have issues with active field
        if (this.state.activeSection === "workspace" || !this.state.activeSection) {
            // Only add active filter if we're in workspace
            // If it causes error, fallback will handle it
            domain.push(["active", "=", true]);
        }
        
        if (this.state.searchQuery) {
            domain.push(["name", "ilike", this.state.searchQuery]);
        }
        
        // Filter by selected tag
        if (this.state.selectedTagId) {
            domain.push(["tag_ids", "in", [this.state.selectedTagId]]);
        }
        
        switch (this.state.activeSection) {
            case "favorites":
                // Favorites: Filter articles favorited by current user
                if (this.state.currentUserId) {
                    domain.push(["favorite_user_ids", "in", [this.state.currentUserId]]);
                } else {
                    // If no user ID, return empty domain (no results)
                    return [["id", "=", false]];
                }
                return domain;
            case "shared":
                // Shared: Filter articles shared with current user
                if (this.state.currentUserId) {
                    domain.push(["shared_user_ids", "in", [this.state.currentUserId]]);
                } else {
                    // If no user ID, return empty domain (no results)
                    return [["id", "=", false]];
                }
                return domain;
            case "private":
                if (this.state.currentUserId) {
                    domain.push(["responsible_id", "=", this.state.currentUserId]);
                } else {
                    // If no user ID, return empty domain (no results)
                    return [["id", "=", false]];
                }
                return domain;
            case "workspace":
            default:
                return domain;
        }
    }

    buildTree(articles, categoryMap) {
        const articleMap = new Map();

        // Create map of all articles with all properties preserved
        articles.forEach(article => {
            articleMap.set(article.id, {
                ...article,
                children: []
            });
        });

        // Build tree structure within each category
        // First pass: add all articles to their categories (only root articles)
        articles.forEach(article => {
            const articleNode = articleMap.get(article.id);
            // Ensure category data is preserved
            if (article.category_icon) {
                articleNode.category_icon = article.category_icon;
            }
            if (article.category_name) {
                articleNode.category_name = article.category_name;
            }
            
            // Get category ID (use category_id[0] if it's a Many2one field)
            let categoryId = article.category_id && article.category_id.length > 0 
                ? article.category_id[0] 
                : 'uncategorized';
            
            // Get category from map (should already exist)
            let category = categoryMap.get(categoryId);
            if (!category) {
                // Category not found, add to uncategorized instead
                categoryId = 'uncategorized';
                if (!categoryMap.has('uncategorized')) {
                    categoryMap.set('uncategorized', {
                        id: 'uncategorized',
                        name: 'Uncategorized',
                        icon: '📝',
                        code: 'uncategorized',
                        sequence: 9999,
                        articles: []
                    });
                }
                category = categoryMap.get('uncategorized');
            }
            
            // Only add root articles (no parent_id) to categories in first pass
            if (!article.parent_id || !article.parent_id.length || !articleMap.has(article.parent_id[0])) {
                // Root article - add to category (only if category exists)
                if (category) {
                    // Ensure articles array exists
                    if (!category.articles) {
                        category.articles = [];
                    }
                    // Check if article is not already in the category
                    const exists = category.articles.some(a => a.id === article.id);
                    if (!exists) {
                        category.articles.push(articleNode);
                    }
                }
            }
        });

        // Second pass: add children to their parents (regardless of category)
        articles.forEach(article => {
            if (article.parent_id && article.parent_id.length > 0 && articleMap.has(article.parent_id[0])) {
                const articleNode = articleMap.get(article.id);
                const parentNode = articleMap.get(article.parent_id[0]);
                
                // Add as child to parent
                parentNode.children.push(articleNode);
                
                // Remove from root articles in category if it was added there
                let categoryId = article.category_id && article.category_id.length > 0 
                    ? article.category_id[0] 
                    : 'uncategorized';
                let category = categoryMap.get(categoryId);
                if (!category) {
                    categoryId = 'uncategorized';
                    category = categoryMap.get('uncategorized');
                }
                if (category && category.articles) {
                    const index = category.articles.findIndex(a => a.id === article.id);
                    if (index !== -1) {
                        category.articles.splice(index, 1);
                    }
                }
            }
        });

        // Category map is already populated, no need to convert
        return categoryMap;
    }

    buildFlatTree(articles) {
        // Build a flat tree structure for favorites/shared/private sections
        // No category grouping, just parent-child relationships
        const articleMap = new Map();
        const rootArticles = [];

        // Create map of all articles
        articles.forEach(article => {
            articleMap.set(article.id, {
                ...article,
                children: [],
                hasChildren: false,
                childrenCount: 0
            });
        });

        // Build parent-child relationships
        articles.forEach(article => {
            const articleNode = articleMap.get(article.id);
            
            // Check if article has a parent
            if (article.parent_id && article.parent_id.length > 0) {
                const parentId = article.parent_id[0];
                const parentNode = articleMap.get(parentId);
                if (parentNode) {
                    parentNode.children.push(articleNode);
                    parentNode.hasChildren = true;
                    parentNode.childrenCount = parentNode.children.length;
                }
            } else {
                // Root article (no parent)
                rootArticles.push(articleNode);
            }
        });

        // Return flat list of root articles (with children nested)
        return rootArticles;
    }

    async onArticleClick(articleId, event) {
        // If clicking on expand icon, toggle expand/collapse
        if (event && event.target) {
            const isExpandIcon = event.target.classList.contains('o_knowledge_expand_icon') ||
                                event.target.closest('.o_knowledge_expand_icon');
            if (isExpandIcon) {
                event.stopPropagation();
                event.preventDefault();
                this.toggleExpand(articleId);
                return;
            }
        }
        
        this.state.selectedArticleId = articleId;
        await this.openArticle(articleId);
    }

    toggleExpand(articleId) {
        const newSet = new Set(this.state.expandedArticles);
        if (newSet.has(articleId)) {
            newSet.delete(articleId);
        } else {
            newSet.add(articleId);
        }
        // Trigger reactivity by creating new Set
        this.state.expandedArticles = newSet;
    }

    isExpanded(articleId) {
        return this.state.expandedArticles.has(articleId);
    }

    toggleExpandCategory(categoryId) {
        const newSet = new Set(this.state.expandedCategories);
        if (newSet.has(categoryId)) {
            newSet.delete(categoryId);
        } else {
            newSet.add(categoryId);
        }
        this.state.expandedCategories = newSet;
    }

    isCategoryExpanded(categoryId) {
        return this.state.expandedCategories.has(categoryId);
    }

    onEditContent() {
        // Open article form in edit mode
        if (this.state.currentArticle && this.state.currentArticle.id) {
            const action = {
                type: "ir.actions.act_window",
                res_model: "knowledge.article",
                res_id: this.state.currentArticle.id,
                view_mode: "form",
                views: [[false, "form"]],
                target: "current",
            };
            this.action.doAction(action);
        }
    }

    async openArticle(articleId) {
        try {
            this.state.loading = true;
            // Use searchRead to get article with all fields including content
            // Use basic fields first, then extend if needed
            let articles = [];
            try {
                articles = await this.orm.searchRead(
                    "knowledge.article",
                    [["id", "=", articleId]],
                    ["id", "name", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token"],
                    { limit: 1 }
                );
                // Compute share_link manually
                if (articles && articles.length > 0 && articles[0].share_token) {
                    const baseUrl = window.location.origin;
                    articles[0].share_link = `${baseUrl}/knowledge/article/${articles[0].share_token}`;
                }
            } catch (error) {
                console.error("Error loading article:", error);
                // Fallback: try with basic fields only
                try {
                    articles = await this.orm.searchRead(
                        "knowledge.article",
                        [["id", "=", articleId]],
                        ["id", "name", "content", "active"],
                        { limit: 1 }
                    );
                } catch (fallbackError) {
                    console.error("Error in fallback:", fallbackError);
                }
            }
            
            let article = null;
            if (articles && articles.length > 0) {
                article = [articles[0]]; // Convert to array format like read()
            }
            
            // If still not found, try read() as fallback
            if (!article || article.length === 0) {
                article = await this.orm.read(
                    "knowledge.article",
                    [articleId],
                    ["id", "name", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token", "share_link", "tag_ids"],
                    { context: { safe_eval: true } }
                );
            }
            if (article && article.length > 0) {
                this.state.currentArticle = article[0];
                
                // Load category icon
                if (this.state.currentArticle.category_id && this.state.currentArticle.category_id.length > 0) {
                    const categories = await this.orm.read(
                        "knowledge.article.category",
                        [this.state.currentArticle.category_id[0]],
                        ["id", "icon"]
                    );
                    if (categories && categories.length > 0) {
                        this.state.currentArticle.category_icon = categories[0].icon || '📝';
                    } else {
                        this.state.currentArticle.category_icon = '📝';
                    }
                } else {
                    this.state.currentArticle.category_icon = '📝';
                }
                
                // Load tag details if tags exist
                if (this.state.currentArticle.tag_ids && this.state.currentArticle.tag_ids.length > 0) {
                    try {
                        const tags = await this.orm.read(
                            "knowledge.article.tag",
                            this.state.currentArticle.tag_ids,
                            ["id", "name", "color"]
                        );
                        if (tags && tags.length > 0) {
                            this.state.currentArticle.tag_ids = tags;
                        }
                    } catch (tagError) {
                        // If tag loading fails, keep tag_ids as is (just IDs)
                        console.error("Error loading tags:", tagError);
                    }
                }
                
                // Ensure content is a string
                if (this.state.currentArticle.content === false || this.state.currentArticle.content === null || this.state.currentArticle.content === undefined) {
                    this.state.currentArticle.content = "";
                } else if (typeof this.state.currentArticle.content !== 'string') {
                    this.state.currentArticle.content = String(this.state.currentArticle.content || "");
                }
                
                // Force trigger render after setting content
                this.state.currentArticle = { ...this.state.currentArticle }; // Trigger reactivity
                
                // Wait for DOM to be ready, then render content
                await new Promise(resolve => setTimeout(resolve, 100));
                
                // Render content using innerHTML
                if (this.contentRef.el) {
                    this.renderContent();
                }
                
                // Also trigger via useEffect by updating state
                this.state.currentArticle = { ...this.state.currentArticle };
                
                // Retry after delays to ensure content is rendered
                setTimeout(() => {
                    if (this.contentRef.el && this.state.currentArticle) {
                        this.renderContent();
                    }
                }, 100);
                
                setTimeout(() => {
                    if (this.contentRef.el && this.state.currentArticle) {
                        this.renderContent();
                    }
                }, 300);
            } else {
                // If no article found, clear content
                this.state.currentArticle = null;
                if (this.contentRef.el) {
                    this.contentRef.el.innerHTML = "";
                }
            }
        } catch (error) {
            console.error("Error loading article:", error);
            // Error loading article - show user-friendly error message
            if (this.contentRef.el) {
                this.contentRef.el.innerHTML = `
                    <div class='o_knowledge_error_content' style='text-align: center; padding: 40px; color: #dc3545;'>
                        <p style='font-size: 16px; margin-bottom: 20px;'>เกิดข้อผิดพลาดในการโหลดเนื้อหา</p>
                        <button class='btn btn-primary' onclick='location.reload()' style='padding: 10px 20px;'>
                            🔄 โหลดใหม่
                        </button>
                    </div>
                `;
            }
        } finally {
            this.state.loading = false;
            // Track view for current user
            if (this.state.currentArticle && this.state.currentArticle.id) {
                this._trackArticleView(this.state.currentArticle.id);
            }
        }
    }

    // Helpers for empty state lists
    getAllArticlesFlat() {
        const flattenWithChildren = (items = []) => {
            const acc = [];
            items.forEach((item) => {
                acc.push(item);
                if (item.children && Array.isArray(item.children) && item.children.length) {
                    acc.push(...flattenWithChildren(item.children));
                }
            });
            return acc;
        };

        if (!this.state.articles) {
            return [];
        }
        // Workspace stores categories with nested children
        if (this.state.articles.length > 0 && Object.prototype.hasOwnProperty.call(this.state.articles[0], "articles")) {
            const flat = [];
            this.state.articles.forEach(cat => {
                if (cat.articles && Array.isArray(cat.articles)) {
                    flat.push(...flattenWithChildren(cat.articles));
                }
            });
            return flat;
        }
        return flattenWithChildren(this.state.articles);
    }

    getRecentArticles(limit = 5) {
        const all = this.getAllArticlesFlat();
        const history = this._loadUserHistory();
        const recentOrder = history.recent || [];
        const byId = new Map(all.map(a => [a.id, a]));
        const result = [];
        recentOrder.forEach(id => {
            if (result.length >= limit) {
                return;
            }
            if (byId.has(id)) {
                result.push(byId.get(id));
            }
        });
        return result;
    }

    getPopularArticles(limit = 5) {
        const all = this.getAllArticlesFlat();
        const history = this._loadUserHistory();
        const counts = history.counts || {};
        const withCounts = all.map(a => ({
            article: a,
            count: counts[a.id] || 0,
        }));
        return withCounts
            .sort((a, b) => b.count - a.count)
            .filter(item => item.count > 0)
            .slice(0, limit)
            .map(item => item.article);
    }

    getTrashArticles() {
        if (this.state.activeSection !== "trash") {
            return [];
        }
        return Array.isArray(this.state.articles) ? this.state.articles : [];
    }

    async onEditArticle() {
        if (!this.state.currentArticle || !this.state.currentArticle.id) {
            return;
        }
        const action = {
            type: "ir.actions.act_window",
            res_model: "knowledge.article",
            res_id: this.state.currentArticle.id,
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        };
        await this.action.doAction(action);
    }

    async onCreateArticle() {
        const action = {
            type: "ir.actions.act_window",
            res_model: "knowledge.article",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
            context: {
                default_parent_id: this.state.selectedArticleId,
            },
        };
        await this.action.doAction(action);
    }

    async loadTags() {
        try {
            const tags = await this.orm.searchRead(
                "knowledge.article.tag",
                [["active", "=", true]],
                ["id", "name", "color"],
                { limit: 100, order: "name" }
            );
            this.state.availableTags = tags || [];
            console.log("Loaded tags:", this.state.availableTags.length, "tags");
        } catch (error) {
            console.error("Error loading tags:", error);
            this.state.availableTags = [];
        }
    }

    onSearchChange(query) {
        this.state.searchQuery = query;
        
        // Clear previous debounce timer if exists
        if (this._searchTimeout) {
            clearTimeout(this._searchTimeout);
        }
        
        // Debounce search to avoid too many API calls while typing
        this._searchTimeout = setTimeout(() => {
            if (this.state.activeSection === "trash") {
                this.loadTrashArticles();
            } else {
                this.loadArticles();
            }
        }, 300); // Wait 300ms after user stops typing
    }

    async onOpenTrash() {
        this.state.activeSection = "trash";
        this.state.selectedArticleId = null;
        this.state.currentArticle = null;
        this.state.expandedArticles = new Set();
        this.state.expandedCategories = new Set();
        await this.loadTrashArticles();
    }

    onTagClick(tagId) {
        if (this.state.selectedTagId === tagId) {
            // If clicking the same tag, clear the filter
            this.state.selectedTagId = null;
        } else {
            // Select the tag
            this.state.selectedTagId = tagId;
        }
        this.loadArticles();
    }

    async loadTrashArticles() {
        this.state.loading = true;
        try {
            const articles = await this.orm.searchRead(
                "knowledge.article",
                [["active", "=", false]],
                ["id", "name", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "write_date"],
                { context: { active_test: false }, limit: 1000 }
            );

            // Normalize category_name for display
            const normalized = (articles || []).map((a) => {
                const catName = Array.isArray(a.category_id) && a.category_id.length > 1 ? a.category_id[1] : "";
                const respName = Array.isArray(a.responsible_id) && a.responsible_id.length > 1 ? a.responsible_id[1] : "";
                return { ...a, category_name: catName, responsible_name: respName };
            });

            // Load responsible avatars
            const responsibleIds = Array.from(
                new Set(
                    (normalized || [])
                        .map(a => (Array.isArray(a.responsible_id) ? a.responsible_id[0] : null))
                        .filter(id => !!id)
                )
            );
            let responsibleMap = new Map();
            if (responsibleIds.length) {
                try {
                    const users = await this.orm.read(
                        "res.users",
                        responsibleIds,
                        ["id", "name", "image_128"]
                    );
                    responsibleMap = new Map(users.map(u => [u.id, u]));
                } catch (e) {
                    console.error("Error loading responsible avatars (trash):", e);
                }
            }

            this.state.articles = normalized.map(a => {
                const respId = Array.isArray(a.responsible_id) ? a.responsible_id[0] : null;
                const resp = respId ? responsibleMap.get(respId) : null;
                return {
                    ...a,
                    responsible_name: resp ? resp.name : a.responsible_name,
                    responsible_avatar: resp ? resp.image_128 : null,
                };
            });
        } catch (error) {
            console.error("Error loading trash articles:", error);
            this.state.articles = [];
        } finally {
            this.state.loading = false;
            // Track view set not needed in trash
        }
    }

    // ----------------------------
    // User history helpers (per user)
    // ----------------------------
    _getUserHistoryKey() {
        const uid = this.state.currentUserId || "guest";
        return `${this._userHistoryKeyPrefix}:${uid}`;
    }

    _loadUserHistory() {
        try {
            const key = this._getUserHistoryKey();
            const raw = window.localStorage.getItem(key);
            if (raw) {
                return JSON.parse(raw);
            }
        } catch (e) {
            console.warn("Cannot load user history:", e);
        }
        return { recent: [], counts: {} };
    }

    _saveUserHistory(history) {
        try {
            const key = this._getUserHistoryKey();
            window.localStorage.setItem(key, JSON.stringify(history));
        } catch (e) {
            console.warn("Cannot save user history:", e);
        }
    }

    _trackArticleView(articleId) {
        if (!articleId) {
            return;
        }
        const history = this._loadUserHistory();
        // Update counts
        history.counts = history.counts || {};
        history.counts[articleId] = (history.counts[articleId] || 0) + 1;
        // Update recent (unique, most recent first)
        history.recent = history.recent || [];
        history.recent = [articleId, ...history.recent.filter(id => id !== articleId)].slice(0, 50);
        this._saveUserHistory(history);
    }

    clearTagFilter() {
        this.state.selectedTagId = null;
        this.loadArticles();
    }

    setActiveSection(section) {
        this.state.activeSection = section;
        // Reset expanded categories when switching sections
        this.state.expandedCategories = new Set();
        this.loadArticles();
    }

    isFavorited(article) {
        if (!article || !this.state.currentUserId) {
            return false;
        }
        
        // Handle case where favorite_user_ids might be undefined or null
        if (!article.favorite_user_ids) {
            return false;
        }
        
        // favorite_user_ids can be an array of IDs or array of tuples [(id, name), ...]
        const favoriteIds = article.favorite_user_ids;
        
        if (!Array.isArray(favoriteIds) || favoriteIds.length === 0) {
            return false;
        }
        
        // Check if it's array of tuples (first element is array or tuple)
        if (Array.isArray(favoriteIds[0])) {
            // Extract IDs from tuples [(id, name), ...]
            return favoriteIds.some(tuple => {
                const id = Array.isArray(tuple) ? tuple[0] : tuple;
                return id === this.state.currentUserId;
            });
        } else {
            // Simple array of IDs [id1, id2, ...]
            return favoriteIds.includes(this.state.currentUserId);
        }
    }

    isShared(article) {
        if (!article || !article.shared_user_ids) {
            return false;
        }
        // shared_user_ids can be an array of IDs or array of tuples [(id, name), ...]
        const sharedIds = article.shared_user_ids;
        if (Array.isArray(sharedIds) && sharedIds.length > 0) {
            // Check if it's array of tuples (first element is array)
            if (Array.isArray(sharedIds[0])) {
                // Extract IDs from tuples
                return sharedIds.length > 0;
            } else {
                // Simple array of IDs
                return sharedIds.length > 0;
            }
        }
        return false;
    }

    getSharedCount(article) {
        if (!article || !article.shared_user_ids) {
            return 0;
        }
        const sharedIds = article.shared_user_ids;
        if (Array.isArray(sharedIds)) {
            return sharedIds.length;
        }
        return 0;
    }

    async toggleFavorite(articleId) {
        if (!articleId || !this.state.currentUserId) {
            return;
        }
        
        try {
            // Get current article to check favorite status
            const articles = await this.orm.searchRead(
                "knowledge.article",
                [["id", "=", articleId]],
                ["id", "favorite_user_ids"],
                { limit: 1 }
            );
            
            if (!articles || articles.length === 0) {
                return;
            }
            
            const article = articles[0];
            const currentFavoriteIds = article.favorite_user_ids || [];
            
            // Handle both array of IDs and array of tuples
            let favoriteIdsArray = [];
            if (Array.isArray(currentFavoriteIds) && currentFavoriteIds.length > 0) {
                if (Array.isArray(currentFavoriteIds[0])) {
                    // Array of tuples [(id, name), ...]
                    favoriteIdsArray = currentFavoriteIds.map(tuple => tuple[0]);
                } else {
                    // Simple array of IDs
                    favoriteIdsArray = currentFavoriteIds;
                }
            }
            
            const isCurrentlyFavorited = favoriteIdsArray.includes(this.state.currentUserId);
            
            let newFavoriteIds;
            if (isCurrentlyFavorited) {
                // Remove from favorites
                newFavoriteIds = favoriteIdsArray.filter(id => id !== this.state.currentUserId);
            } else {
                // Add to favorites
                newFavoriteIds = [...favoriteIdsArray, this.state.currentUserId];
            }
            
            // Update the article using Odoo's Many2many command format: [[6, 0, [ids]]]
            await this.orm.write(
                "knowledge.article",
                [articleId],
                { favorite_user_ids: [[6, 0, newFavoriteIds]] }
            );
            
            // Update current article state if it's the same article
            if (this.state.currentArticle && this.state.currentArticle.id === articleId) {
                this.state.currentArticle.favorite_user_ids = newFavoriteIds;
                // Trigger reactivity by creating new object
                this.state.currentArticle = { ...this.state.currentArticle };
            }
            
            // Reload articles to reflect changes in the sidebar
            await this.loadArticles();
            // Reload current article content to avoid blank body after favorite toggle
            if (this.state.currentArticle && this.state.currentArticle.id === articleId) {
                await this.openArticle(articleId);
            }
        } catch (error) {
            console.error("Error toggling favorite:", error);
        }
    }

    async toggleShare(articleId) {
        if (!articleId) {
            return;
        }
        
        try {
            // Open share link dialog
            await this.showShareLinkDialog(articleId);
        } catch (error) {
            console.error("Error toggling share:", error);
        }
    }

    async showShareLinkDialog(articleId) {
        if (!articleId) {
            return;
        }
        
        try {
            // Get current article to check if share_token exists
            const articles = await this.orm.searchRead(
                "knowledge.article",
                [["id", "=", articleId]],
                ["id", "share_token", "share_link"],
                { limit: 1 }
            );
            
            if (!articles || articles.length === 0) {
                return;
            }
            
            let article = articles[0];
            let shareLink = article.share_link;
            
            // If no share token exists, generate one
            if (!article.share_token || !shareLink) {
                // Call the server method to generate share token
                await this.orm.call(
                    "knowledge.article",
                    "generate_share_token",
                    [[articleId]]
                );
                
                // Reload article to get the new share_token and computed share_link
                const updatedArticles = await this.orm.read(
                    "knowledge.article",
                    [articleId],
                    ["id", "share_token", "share_link"]
                );
                
                if (updatedArticles && updatedArticles.length > 0) {
                    article = updatedArticles[0];
                    shareLink = article.share_link;
                }
            }
            
            // Update state to show dialog
            this.state.shareLink = shareLink;
            this.state.showShareDialog = true;
            
            // Update current article if it's the same
            if (this.state.currentArticle && this.state.currentArticle.id === articleId) {
                this.state.currentArticle.share_token = article.share_token;
                this.state.currentArticle.share_link = shareLink;
                this.state.currentArticle = { ...this.state.currentArticle };
            }
        } catch (error) {
            console.error("Error showing share dialog:", error);
        }
    }

    async copyShareLink() {
        if (!this.state.shareLink) {
            return;
        }
        
        try {
            // Use Clipboard API if available
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(this.state.shareLink);
                // Show success notification
                this.showNotification("Share link copied to clipboard!", "success");
            } else {
                // Fallback: create temporary textarea
                const textarea = document.createElement("textarea");
                textarea.value = this.state.shareLink;
                textarea.style.position = "fixed";
                textarea.style.opacity = "0";
                document.body.appendChild(textarea);
                textarea.select();
                document.execCommand("copy");
                document.body.removeChild(textarea);
                this.showNotification("Share link copied to clipboard!", "success");
            }
        } catch (error) {
            console.error("Error copying share link:", error);
            this.showNotification("Failed to copy link. Please copy manually.", "danger");
        }
    }

    closeShareDialog() {
        this.state.showShareDialog = false;
        this.state.shareLink = null;
    }

    showNotification(message, type = "info") {
        // Simple notification - could be enhanced with Odoo's notification service
        const notification = document.createElement("div");
        notification.className = `alert alert-${type} alert-dismissible fade show`;
        notification.style.cssText = "position: fixed; top: 20px; right: 20px; z-index: 9999; min-width: 300px;";
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(notification);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    generateTOCContent(tocElement) {
        if (!tocElement || !this.contentRef.el) {
            return;
        }
        
        // Find all headings in the content area (excluding the TOC element itself)
        const contentArea = this.contentRef.el;
        const headings = contentArea.querySelectorAll('h1, h2, h3, h4, h5, h6');
        
        if (headings.length === 0) {
            tocElement.innerHTML = '<p style="color: #6c757d; font-style: italic; margin: 0; padding: 8px 0;">No headings found in this article.</p>';
            return;
        }

        // Create TOC structure with improved styling
        let tocHTML = '<div class="o_toc_header"><h3>Table of Contents</h3></div><ul class="o_toc_list">';
        
        headings.forEach((heading, index) => {
            // Skip headings inside the TOC element itself
            if (tocElement.contains(heading)) {
                return;
            }

            const headingText = heading.textContent.trim();
            if (!headingText) {
                return;
            }

            // Generate a unique ID for the heading if it doesn't have one
            let headingId = heading.id;
            if (!headingId || headingId.trim() === '') {
                // Create a safe ID from heading text
                headingId = `toc-heading-${index}-${headingText.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 50)}`;
                // Ensure ID is unique
                let counter = 0;
                let finalHeadingId = headingId;
                while (contentArea.querySelector(`#${finalHeadingId}`)) {
                    counter++;
                    finalHeadingId = `${headingId}-${counter}`;
                }
                headingId = finalHeadingId;
                heading.id = headingId;
            }

            // Determine indentation level based on heading level
            const level = parseInt(heading.tagName.charAt(1));
            const indentClass = `o_toc_level_${level}`;

            // Create TOC item with improved styling and smooth scroll
            tocHTML += `
                <li class="o_toc_item ${indentClass}">
                    <a href="#${headingId}" 
                       class="o_toc_link"
                       data-heading-id="${headingId}">
                        ${headingText}
                    </a>
                </li>
            `;
        });

        tocHTML += '</ul>';
        
        // Set TOC content
        tocElement.innerHTML = tocHTML;
        
        // Store reference to contentRef for use in event listeners
        const contentRefEl = this.contentRef.el;
        
        // Function to handle TOC link clicks
        const scrollToHeading = (headingId) => {
            if (!headingId) {
                return;
            }
            
            // Try multiple methods to find the heading
            let targetHeading = null;
            
            // Method 1: Search in content area using attribute selector
            if (contentRefEl) {
                targetHeading = contentRefEl.querySelector(`[id="${headingId}"]`);
                
                // If not found, search all headings by iterating
                if (!targetHeading) {
                    const allHeadings = contentRefEl.querySelectorAll('h1, h2, h3, h4, h5, h6');
                    for (let i = 0; i < allHeadings.length; i++) {
                        if (allHeadings[i].id === headingId) {
                            targetHeading = allHeadings[i];
                            break;
                        }
                    }
                }
            }
            
            // Method 2: Fallback to document search
            if (!targetHeading) {
                targetHeading = document.getElementById(headingId);
            }
            
            if (targetHeading) {
                // Method 1: Try scrollIntoView with scroll-margin-top (modern browsers)
                try {
                    const originalScrollMargin = targetHeading.style.scrollMarginTop;
                    targetHeading.style.scrollMarginTop = '100px';
                    
                    // Check if scrollIntoView is supported
                    if (typeof targetHeading.scrollIntoView === 'function') {
                        targetHeading.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start',
                            inline: 'nearest'
                        });
                        
                        // Restore original scroll margin after scroll completes
                        setTimeout(() => {
                            if (originalScrollMargin) {
                                targetHeading.style.scrollMarginTop = originalScrollMargin;
                            } else {
                                targetHeading.style.scrollMarginTop = '';
                            }
                        }, 1000);
                    } else {
                        // Fallback: manual scroll calculation
                        throw new Error('scrollIntoView not supported');
                    }
                } catch (e) {
                    // Method 2: Fallback - manual scroll calculation
                    const offset = 100;
                    const rect = targetHeading.getBoundingClientRect();
                    const currentScroll = window.pageYOffset || 
                                        document.documentElement.scrollTop || 
                                        document.body.scrollTop || 
                                        0;
                    const targetPosition = rect.top + currentScroll - offset;
                    
                    // Smooth scroll using requestAnimationFrame for older browsers
                    if ('scrollBehavior' in document.documentElement.style) {
                        window.scrollTo({
                            top: Math.max(0, targetPosition),
                            behavior: 'smooth'
                        });
                    } else {
                        // Polyfill for smooth scroll
                        const startPosition = currentScroll;
                        const distance = targetPosition - startPosition;
                        const duration = 500;
                        let start = null;
                        
                        const animateScroll = (timestamp) => {
                            if (!start) start = timestamp;
                            const progress = timestamp - start;
                            const percentage = Math.min(progress / duration, 1);
                            
                            // Easing function (ease-in-out)
                            const ease = percentage < 0.5 
                                ? 2 * percentage * percentage 
                                : 1 - Math.pow(-2 * percentage + 2, 2) / 2;
                            
                            window.scrollTo(0, startPosition + distance * ease);
                            
                            if (progress < duration) {
                                requestAnimationFrame(animateScroll);
                            }
                        };
                        
                        requestAnimationFrame(animateScroll);
                    }
                }
            }
        };
        
        // Use event delegation on TOC element for better reliability
        tocElement.addEventListener('click', (e) => {
            const link = e.target.closest('.o_toc_link');
            if (link) {
                e.preventDefault();
                e.stopPropagation();
                const headingId = link.getAttribute('data-heading-id');
                scrollToHeading(headingId);
            }
        });
        
        // Also attach directly to each link as backup (after DOM is ready)
        setTimeout(() => {
            const tocLinks = tocElement.querySelectorAll('.o_toc_link');
            tocLinks.forEach((link) => {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const headingId = link.getAttribute('data-heading-id');
                    scrollToHeading(headingId);
                });
            });
        }, 100);
    }
}

KnowledgeDocumentController.template = "knowledge_onthisday_oca.KnowledgeDocumentView";

// Register as client action
try {
    registry.category("actions").add("knowledge_document_view", KnowledgeDocumentController);
} catch (error) {
    console.error("Error registering KnowledgeDocumentController:", error);
}
