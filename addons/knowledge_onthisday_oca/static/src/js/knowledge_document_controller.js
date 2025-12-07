/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, useState, onWillStart, useRef, useEffect, onMounted, onWillUpdateProps, onRendered, onWillUnmount, markup } from "@odoo/owl";

// Import CommentOverlay
import { CommentOverlay } from "./comment/comment_overlay";

/**
 * Logging utility for production-ready error handling
 * Only logs in development mode, silent in production
 */
const isDevelopment = typeof window !== 'undefined' && window.location.hostname === 'localhost';
const logger = {
    error: (message, error) => {
        if (isDevelopment) {
            console.error(message, error);
        }
        // In production: errors are silently handled, could integrate with error tracking service
    },
    warn: (message, data) => {
        if (isDevelopment) {
            console.warn(message, data);
        }
    },
    log: (message, data) => {
        if (isDevelopment) {
            console.log(message, data);
        }
    },
    debug: (message, data) => {
        if (isDevelopment) {
            console.debug(message, data);
        }
    }
};

export class KnowledgeDocumentController extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: Number, optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
    };
    static components = { CommentOverlay };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.contentRef = useRef("content");
        this._userHistoryKeyPrefix = "knowledge_onthisday_history";
        
        this.state = useState({
            selectedArticleId: null,
            searchQuery: "",
            searchLoading: false,
            searchResults: [],
            searchTotal: 0,
            searchPage: 1,
            searchPageSize: 10,
            searchSort: "recent", // recent, name, views
            searchFilters: {
                category_id: null,
                tag_ids: [],
                responsible_id: null,
                date_from: null,
                date_to: null,
            },
            filterOptions: {
                categories: [],
                users: [],
            },
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
            sidebarOpenMobile: false, // Mobile drawer state
            showCommentPanel: false, // Toggle comment panel visibility
            showCommentButton: false, // Show floating comment button when text is selected
            commentButtonPosition: { top: 0, left: 0 }, // Position of floating comment button
            currentTextSelection: null, // Current text selection data
            triggerCommentCreation: false, // Trigger comment creation from floating button
            newCommentBody: "", // Draft comment body
        });
        this._floatingTOCHeadings = [];
        this.inlineTOCElement = null;
        this._tocObserver = null;
        this._onScrollFloatingTOC = () => {
            if (this._floatingTOCHeadings.length === 0 || !this.floatingTOCContainer) {
                return;
            }
            window.requestAnimationFrame(() => this._updateFloatingTOCActive());
        };

        onWillStart(async () => {
            // Load tags first
            await this.loadTags();
            await this.loadFilterOptions();
            
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
                logger.error("Error getting user ID:", error);
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
        
        // Render content when article changes (useEffect already covers this)
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

        // Scroll listener for floating TOC highlight
        onMounted(() => {
            window.addEventListener('scroll', this._onScrollFloatingTOC, { passive: true });
        });
        onWillUnmount(() => {
            window.removeEventListener('scroll', this._onScrollFloatingTOC);
            if (this._tocObserver) {
                this._tocObserver.disconnect();
                this._tocObserver = null;
            }
            if (this.floatingTOCContainer && this.floatingTOCContainer.parentNode) {
                this.floatingTOCContainer.parentNode.removeChild(this.floatingTOCContainer);
            }
            this.floatingTOCContainer = null;
        });
    }

    // Mobile drawer helpers
    toggleSidebarMobile() {
        this.state.sidebarOpenMobile = !this.state.sidebarOpenMobile;
    }

    closeSidebarMobile() {
        if (this.state.sidebarOpenMobile) {
            this.state.sidebarOpenMobile = false;
        }
    }

    updateNewCommentBody(value) {
        this.state.newCommentBody = value || "";
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
                            const activeQuery = (this.state.lastSearchQuery || "").trim();
                            if (activeQuery) {
                                this._highlightQueryInContent(activeQuery);
                            }
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
                    const activeQuery = (this.state.lastSearchQuery || "").trim();
                    if (activeQuery) {
                        this._highlightQueryInContent(activeQuery);
                    }
                    this.processTOCAfterRender();
                    this.setupTextSelectionListener();
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
            this.inlineTOCElement = tocElement;
            // Check if TOC is empty and needs to be generated
            const tocInnerHTML = tocElement.innerHTML || '';
            const tocInnerHTMLTrimmed = tocInnerHTML.trim();
            const tocIsEmpty = !tocInnerHTML || tocInnerHTMLTrimmed.length === 0;
            
            if (tocIsEmpty) {
                this.generateTOCContent(tocElement);
            } else {
                this.generateTOCContent(tocElement);
            }
            this._setupFloatingTOCObserver(allHeadings);
        } else {
            // No inline TOC found; still expose floating TOC for headings
            if (allHeadings.length) {
                const tocHtml = this._buildTOCHTMLFromHeadings(allHeadings);
                this._renderFloatingTOC(tocHtml, allHeadings);
            } else {
                this._toggleFloatingTOC(false);
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
                    this.inlineTOCElement = tocElementDelayed;
                    // Check if TOC is empty and needs to be generated (delayed check)
                    const tocInnerHTMLDelayed = tocElementDelayed.innerHTML || '';
                    const tocInnerHTMLTrimmedDelayed = tocInnerHTMLDelayed.trim();
                    const tocIsEmptyDelayed = !tocInnerHTMLDelayed || tocInnerHTMLTrimmedDelayed.length === 0;
                    
                    if (tocIsEmptyDelayed) {
                        this.generateTOCContent(tocElementDelayed);
                    }
                    this._setupFloatingTOCObserver(allHeadingsDelayed);
                } else if (allHeadingsDelayed.length) {
                    const tocHtmlDelayed = this._buildTOCHTMLFromHeadings(allHeadingsDelayed);
                    this._renderFloatingTOC(tocHtmlDelayed, allHeadingsDelayed);
                } else {
                    this._toggleFloatingTOC(false);
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
                        logger.warn("Failed to parse category name as JSON:", e);
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
            const extendedFields = ["category_id", "parent_id", "responsible_id", "write_date", "create_date", "content"];
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
                logger.error("Error loading articles:", searchReadError);
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
                                logger.error("Error reading articles:", readError2);
                            }
                        }
                    } catch (fallbackError) {
                        logger.error("Error in fallback search:", fallbackError);
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
                    logger.error("Error loading responsible avatars:", e);
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
            logger.error("Error loading articles:", error);
            logger.error("Error details:", {
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
            domain.push("|");
            domain.push(["name", "ilike", this.state.searchQuery]);
            domain.push(["content", "ilike", this.state.searchQuery]);
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
        // If coming from search results, remember the query for highlight then clear for view
        if (this.state.searchQuery) {
            this.state.lastSearchQuery = this.state.searchQuery;
            this.state.searchQuery = "";
        }
        // Close mobile drawer when an article is selected
        if (this.state.sidebarOpenMobile) {
            this.state.sidebarOpenMobile = false;
        }
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
                    ["id", "name", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token", "comment_count", "unresolved_comment_count"],
                    { limit: 1 }
                );
                // Compute share_link manually
                if (articles && articles.length > 0 && articles[0].share_token) {
                    const baseUrl = window.location.origin;
                    articles[0].share_link = `${baseUrl}/knowledge/article/${articles[0].share_token}`;
                }
            } catch (error) {
                logger.error("Error loading article:", error);
                // Fallback: try with basic fields only
                try {
                    articles = await this.orm.searchRead(
                        "knowledge.article",
                        [["id", "=", articleId]],
                        ["id", "name", "content", "active"],
                        { limit: 1 }
                    );
                } catch (fallbackError) {
                    logger.error("Error in fallback:", fallbackError);
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
                    ["id", "name", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token", "share_link", "tag_ids", "comment_count", "unresolved_comment_count"],
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
                        logger.error("Error loading tags:", tagError);
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
            logger.error("Error loading article:", error);
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

    getNewestArticles(limit = 5) {
        const all = this.getAllArticlesFlat();
        return all
            .slice()
            .sort((a, b) => {
                const aDate = a.write_date || a.create_date || "";
                const bDate = b.write_date || b.create_date || "";
                return bDate.localeCompare(aDate);
            })
            .slice(0, limit);
    }

    getSearchResults() {
        return this.state.searchResults || [];
    }

    async fetchSearchResults(page = 1) {
        const query = (this.state.searchQuery || "").trim();
        if (!query) {
            this.state.searchResults = [];
            this.state.searchTotal = 0;
            return;
        }
        this.state.searchLoading = true;
        const limit = this.state.searchPageSize;
        const offset = (page - 1) * limit;
        try {
            const payload = await this.orm.call(
                "knowledge.article",
                "search_articles_server",
                [],
                {
                    query,
                    filters: this.state.searchFilters,
                    sort: this.state.searchSort,
                    limit,
                    offset,
                }
            );
            const results = (payload.results || []).map((a) => {
                // reuse snippet/highlight on client for safety
                const stripHtml = (html) => {
                    if (!html) return "";
                    const tmp = document.createElement("div");
                    tmp.innerHTML = html;
                    return (tmp.textContent || tmp.innerText || "").trim();
                };
                const cleanText = stripHtml(a.content);
                const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
                const regex = new RegExp(terms.map((t) => t.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")).join("|"), "ig");
                const makeSnippet = (text) => {
                    if (!text) return "";
                    const lower = text.toLowerCase();
                    const idx = terms
                        .map((t) => lower.indexOf(t))
                        .filter((i) => i >= 0)
                        .reduce((a, b) => (a === -1 ? b : Math.min(a, b)), -1);
                    const radius = 80;
                    let start = 0;
                    let end = Math.min(text.length, 160);
                    if (idx !== -1) {
                        start = Math.max(0, idx - radius);
                        end = Math.min(text.length, idx + terms[0].length + radius);
                    }
                    const prefixEllipsis = start > 0 ? "…" : "";
                    const suffixEllipsis = end < text.length ? "…" : "";
                    const raw = text.substring(start, end);
                    let result = "";
                    let lastIndex = 0;
                    let match;
                    regex.lastIndex = 0;
                    while ((match = regex.exec(raw)) !== null) {
                        const matchStart = match.index;
                        const matchEnd = matchStart + match[0].length;
                        if (matchStart > lastIndex) {
                            result += this._escapeHtml(raw.substring(lastIndex, matchStart));
                        }
                        result += `<mark class="o_knowledge_highlight">${this._escapeHtml(match[0])}</mark>`;
                        lastIndex = matchEnd;
                    }
                    if (lastIndex < raw.length) {
                        result += this._escapeHtml(raw.substring(lastIndex));
                    }
                    return markup(`${prefixEllipsis}${result}${suffixEllipsis}`);
                };
                return {
                    ...a,
                    search_snippet: makeSnippet(cleanText),
                    search_meta: [a.category_name, a.write_date].filter(Boolean).join(" · "),
                };
            });
            this.state.searchResults = results;
            this.state.searchTotal = payload.total || 0;
            this.state.searchPage = page;
        } catch (error) {
            logger.error("Server search failed:", error);
            this.state.searchResults = [];
            this.state.searchTotal = 0;
        } finally {
            this.state.searchLoading = false;
        }
    }

    _escapeHtml(text) {
        return (text || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
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
            logger.log("Loaded tags:", this.state.availableTags.length, "tags");
        } catch (error) {
            logger.error("Error loading tags:", error);
            this.state.availableTags = [];
        }
    }

    async loadFilterOptions() {
        try {
            const categories = await this.orm.searchRead(
                "knowledge.article.category",
                [],
                ["id", "name"],
                { limit: 200, order: "name" }
            );
            const users = await this.orm.searchRead(
                "res.users",
                [],
                ["id", "name", "image_128"],
                { limit: 200, order: "name" }
            );
            this.state.filterOptions = { categories, users };
        } catch (error) {
            logger.error("Error loading filter options:", error);
            this.state.filterOptions = { categories: [], users: [] };
        }
    }

    onSearchChange(query) {
        this.state.searchQuery = query;
        this.state.searchLoading = true;
        
        // Clear previous debounce timer if exists
        if (this._searchTimeout) {
            clearTimeout(this._searchTimeout);
        }
        
        // Debounce search to avoid too many API calls while typing
        this._searchTimeout = setTimeout(() => {
            this.fetchSearchResults();
        }, 300); // Wait 300ms after user stops typing
    }

    onCategoryChange(value) {
        const id = Number(value);
        this.state.searchFilters.category_id = isNaN(id) ? null : id;
        this.fetchSearchResults(1);
    }

    onResponsibleChange(value) {
        const id = Number(value);
        this.state.searchFilters.responsible_id = isNaN(id) ? null : id;
        this.fetchSearchResults(1);
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
                    logger.error("Error loading responsible avatars (trash):", e);
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
            logger.error("Error loading trash articles:", error);
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
            logger.warn("Cannot load user history:", e);
        }
        return { recent: [], counts: {} };
    }

    _saveUserHistory(history) {
        try {
            const key = this._getUserHistoryKey();
            window.localStorage.setItem(key, JSON.stringify(history));
        } catch (e) {
            logger.warn("Cannot save user history:", e);
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
            logger.error("Error toggling favorite:", error);
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
            logger.error("Error toggling share:", error);
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
            logger.error("Error showing share dialog:", error);
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
            logger.error("Error copying share link:", error);
            this.showNotification("Failed to copy link. Please copy manually.", "danger");
        }
    }

    closeShareDialog() {
        this.state.showShareDialog = false;
        this.state.shareLink = null;
    }

    toggleCommentPanel() {
        this.state.showCommentPanel = !this.state.showCommentPanel;
        if (!this.state.showCommentPanel) {
            this.state.showCommentButton = false;
        }
    }

    closeCommentPanel() {
        this.state.showCommentPanel = false;
        this.state.showCommentButton = false;
    }

    /**
     * Handle highlight click - open comment panel and select comment
     */
    onHighlightClick(commentId) {
        logger.log('onHighlightClick called in controller:', {
            commentId: commentId,
            currentShowCommentPanel: this.state.showCommentPanel
        });
        
        // Open comment panel if not already open
        if (!this.state.showCommentPanel) {
            this.state.showCommentPanel = true;
            logger.log('Comment panel opened via highlight click');
        }
        
        // Wait a bit for panel to open and comments to load, then select the comment
        setTimeout(() => {
            // Trigger selection in CommentOverlay by dispatching a custom event
            // CommentOverlay will listen for this event and select the comment
            const event = new CustomEvent('highlight-comment-clicked', {
                detail: { commentId: commentId }
            });
            document.dispatchEvent(event);
            
            logger.log('Highlight click event dispatched:', {
                commentId: commentId
            });
        }, 300); // Wait 300ms for panel to open and comments to load
    }

    /**
     * Setup text selection listener for comment button
     */
    setupTextSelectionListener() {
        if (!this.contentRef.el || !this.state.showCommentPanel) return;

        // Remove existing listeners
        if (this._onTextSelection) {
            this.contentRef.el.removeEventListener('mouseup', this._onTextSelection);
            this.contentRef.el.removeEventListener('keyup', this._onTextSelection);
        }
        if (this._onClickOutsideSelection) {
            this.contentRef.el.removeEventListener('click', this._onClickOutsideSelection);
        }

        // Add new listeners
        this._onTextSelection = () => {
            setTimeout(() => this.onTextSelection(), 100);
        };
        this._onClickOutsideSelection = (e) => {
            // Don't hide button or remove highlight if clicking on button or highlighted text
            if (e.target.closest('.o_knowledge_comment_button_floating') || 
                e.target.closest('.o_knowledge_comment_temp_highlight')) {
                return;
            }
            
            // Don't remove highlight when clicking outside
            // Only hide the button if there's no new selection
            const selection = window.getSelection();
            if (!selection || selection.rangeCount === 0 || selection.toString().trim().length === 0) {
                // Only hide button, keep highlight visible
                this.state.showCommentButton = false;
            }
        };

        this.contentRef.el.addEventListener('mouseup', this._onTextSelection);
        this.contentRef.el.addEventListener('keyup', this._onTextSelection);
        this.contentRef.el.addEventListener('click', this._onClickOutsideSelection);
    }

    /**
     * Handle text selection in article content
     */
    onTextSelection() {
        if (!this.contentRef.el || !this.state.showCommentPanel) {
            this.state.showCommentButton = false;
            this.removeTemporaryHighlight();
            return;
        }

        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            // Don't remove highlight - keep it visible even if selection is cleared
            // Only hide the button
            this.state.showCommentButton = false;
            return;
        }

        const range = selection.getRangeAt(0);
        if (!this.contentRef.el.contains(range.commonAncestorContainer)) {
            // Don't remove highlight - keep it visible
            this.state.showCommentButton = false;
            return;
        }

        const selectedText = range.toString().trim();
        if (selectedText.length === 0) {
            // Don't remove highlight - keep it visible
            this.state.showCommentButton = false;
            return;
        }

        // Store selection info before highlighting (range may change after highlight)
        const rect = range.getBoundingClientRect();
        const contentRect = this.contentRef.el.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;

        // Highlight the selected text (must be done before calculating position)
        this.highlightSelectedText(range);

        // Wait for DOM update after highlighting
        requestAnimationFrame(() => {
            // Recalculate position after highlight is applied
            const highlightSpan = this._tempHighlightSpan;
            if (highlightSpan) {
                const highlightRect = highlightSpan.getBoundingClientRect();
                const newContentRect = this.contentRef.el.getBoundingClientRect();
                
                // Calculate button position - align with the top of highlighted text (same line)
                this.state.commentButtonPosition = {
                    top: highlightRect.top - newContentRect.top + scrollTop, // Align with top of selection (same line)
                    left: highlightRect.right - newContentRect.left + scrollLeft + 10, // Show on the right side of selection
                };
            } else {
                // Fallback to original rect if highlight failed
                this.state.commentButtonPosition = {
                    top: rect.top - contentRect.top + scrollTop, // Align with top of selection (same line)
                    left: rect.right - contentRect.left + scrollLeft + 10, // Show on the right side of selection
                };
            }

            this.state.currentTextSelection = {
                text: selectedText,
                range: range,
            };

            this.state.showCommentButton = true;
        });
    }

    /**
     * Highlight selected text
     */
    highlightSelectedText(range) {
        logger.log('highlightSelectedText called', { range: range.toString() });
        
        // Remove existing temporary highlight only if selecting new text
        if (this._tempHighlightSpan && this._tempHighlightSpan.parentNode) {
            // Check if we're selecting the same text (don't remove if same)
            const existingText = this._tempHighlightSpan.textContent || '';
            const newText = range.toString().trim();
            if (existingText === newText) {
                // Same text, keep existing highlight
                logger.log('Same text selected, keeping existing highlight');
                return;
            }
            // Remove old highlight
            logger.log('Removing old highlight');
            this.removeTemporaryHighlight();
        }

        const selectedText = range.toString().trim();
        if (!selectedText) {
            logger.warn('No text selected');
            return;
        }

        try {
            // Use extractContents approach - more reliable and doesn't depend on browser selection
            const clonedRange = range.cloneRange();
            
            // Extract the selected content first
            const contents = clonedRange.extractContents();
            
            // Create a span to wrap the selected text
            const span = document.createElement('span');
            span.className = 'o_knowledge_comment_temp_highlight';
            span.setAttribute('data-highlight-temp', 'true');
            
            // Set inline styles to ensure visibility - use multiple methods to force visibility
            // Method 1: Background color (primary)
            span.style.setProperty('background-color', '#ffeb3b', 'important');
            span.style.setProperty('background', '#ffeb3b', 'important');
            // Method 2: Box shadow (backup for WYSIWYG editor issues)
            span.style.setProperty('box-shadow', '0 0 0 4px #ffeb3b inset', 'important');
            // Method 3: Outline (additional backup)
            span.style.setProperty('outline', '3px solid #ffeb3b', 'important');
            span.style.setProperty('outline-offset', '-3px', 'important');
            // Other styles
            span.style.setProperty('cursor', 'pointer', 'important');
            span.style.setProperty('display', 'inline', 'important');
            span.style.setProperty('padding', '2px 0', 'important');
            span.style.setProperty('border-radius', '2px', 'important');
            span.style.setProperty('position', 'relative', 'important');
            span.style.setProperty('z-index', '999', 'important');
            span.style.setProperty('color', 'inherit', 'important');
            span.style.setProperty('visibility', 'visible', 'important');
            span.style.setProperty('opacity', '1', 'important');
            
            logger.log('Created span element', { className: span.className, text: selectedText });
            
            // Put extracted contents into span, then insert span at range position
            span.appendChild(contents);
            clonedRange.insertNode(span);
            
            logger.log('extractContents approach successful', { 
                spanInDOM: span.parentNode !== null,
                spanText: span.textContent,
                hasContents: contents && contents.childNodes.length > 0
            });
            
            // Store reference for later removal
            this._tempHighlightSpan = span;
            
            // Force a reflow to ensure the highlight is rendered
            void span.offsetHeight;
            
            // Verify highlight is in DOM
            if (!span.parentNode) {
                logger.error('Highlight span not in DOM after extractContents');
                throw new Error('Highlight span not in DOM');
            }
            
            // Immediately verify and force styles to ensure visibility
            requestAnimationFrame(() => {
                if (span && span.parentNode) {
                    const computedStyle = window.getComputedStyle(span);
                    const bgColor = computedStyle.backgroundColor;
                    const rect = span.getBoundingClientRect();
                    
                    logger.log('Immediate highlight check', {
                        inDOM: span.parentNode !== null,
                        backgroundColor: bgColor,
                        width: rect.width,
                        height: rect.height,
                        display: computedStyle.display,
                        visibility: computedStyle.visibility
                    });
                    
                    // Force styles immediately if not visible
                    if (bgColor === '' || bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent' || 
                        rect.width === 0 || rect.height === 0) {
                        logger.warn('Highlight not visible immediately, forcing styles...');
                        span.style.setProperty('background-color', '#ffeb3b', 'important');
                        span.style.setProperty('background', '#ffeb3b', 'important');
                        span.style.setProperty('box-shadow', '0 0 0 4px #ffeb3b inset', 'important');
                        span.style.setProperty('outline', '3px solid #ffeb3b', 'important');
                        span.style.setProperty('display', 'inline', 'important');
                        span.style.setProperty('visibility', 'visible', 'important');
                        span.style.setProperty('opacity', '1', 'important');
                        void span.offsetHeight; // Force reflow
                        
                        // Verify again after forcing
                        setTimeout(() => {
                            const newBgColor = window.getComputedStyle(span).backgroundColor;
                            const newRect = span.getBoundingClientRect();
                            logger.log('After forcing styles', {
                                backgroundColor: newBgColor,
                                width: newRect.width,
                                height: newRect.height,
                                isVisible: newBgColor !== '' && newBgColor !== 'rgba(0, 0, 0, 0)' && newBgColor !== 'transparent'
                            });
                        }, 50);
                    }
                }
            });
            
            logger.log('Highlight created successfully', { 
                parentNode: span.parentNode.tagName,
                computedStyle: window.getComputedStyle(span).backgroundColor 
            });
            
            // Clear native selection so ::selection style won't mask our temp highlight
            requestAnimationFrame(() => {
                const sel = window.getSelection();
                if (sel && sel.removeAllRanges) {
                    sel.removeAllRanges();
                }
            });
            
            // Setup periodic check to ensure highlight stays visible
            // Check every 100ms for 2 seconds to catch any disappearing highlights
            let checkCount = 0;
            const maxChecks = 20; // 2 seconds total
            const highlightCheckInterval = setInterval(() => {
                checkCount++;
                if (span && span.parentNode) {
                    const computedStyle = window.getComputedStyle(span);
                    const bgColor = computedStyle.backgroundColor;
                    
                    // If highlight is still there and visible, continue checking
                    if (bgColor !== '' && bgColor !== 'rgba(0, 0, 0, 0)' && bgColor !== 'transparent') {
                        // Highlight is still visible, continue
                        if (checkCount >= maxChecks) {
                            clearInterval(highlightCheckInterval);
                        }
                        return;
                    }
                }
                
                // Highlight disappeared or not visible - check if it's actually removed from DOM
                if (!span || !span.parentNode) {
                    logger.warn('Highlight removed from DOM!');
                    // Highlight was actually removed - we can't restore without original range
                    clearInterval(highlightCheckInterval);
                    this._tempHighlightSpan = null;
                } else if (this._tempHighlightSpan && this._tempHighlightSpan === span) {
                    // Highlight is in DOM but not visible - force styles again
                    const computedStyle = window.getComputedStyle(span);
                    const bgColor = computedStyle.backgroundColor;
                    if (bgColor === '' || bgColor === 'rgba(0, 0, 0, 0)' || bgColor === 'transparent') {
                        logger.warn('Highlight not visible, forcing styles again...');
                        span.style.setProperty('background-color', '#ffeb3b', 'important');
                        span.style.setProperty('background', '#ffeb3b', 'important');
                        span.style.setProperty('box-shadow', '0 0 0 4px #ffeb3b inset', 'important');
                        span.style.setProperty('outline', '3px solid #ffeb3b', 'important');
                        span.style.setProperty('display', 'inline', 'important');
                        span.style.setProperty('visibility', 'visible', 'important');
                        span.style.setProperty('opacity', '1', 'important');
                        void span.offsetHeight; // Force reflow
                    }
                    
                    if (checkCount >= maxChecks) {
                        clearInterval(highlightCheckInterval);
                    }
                } else {
                    clearInterval(highlightCheckInterval);
                }
            }, 100);
        } catch (e) {
            logger.warn('surroundContents failed, trying extractContents', e);
            // If surroundContents fails (e.g., selection spans multiple elements),
            // try extractContents approach
            try {
                const clonedRange = range.cloneRange();
                const contents = clonedRange.extractContents();
                
                const span = document.createElement('span');
                span.className = 'o_knowledge_comment_temp_highlight';
                span.setAttribute('data-highlight-temp', 'true');
                
                // Set inline styles
                span.style.backgroundColor = '#ffeb3b';
                span.style.cursor = 'pointer';
                span.style.display = 'inline';
                span.style.padding = '2px 0';
                span.style.borderRadius = '2px';
                span.style.position = 'relative';
                span.style.zIndex = '1';
                
                span.appendChild(contents);
                clonedRange.insertNode(span);
                
                logger.log('extractContents approach successful', { 
                    spanInDOM: span.parentNode !== null,
                    spanText: span.textContent 
                });
                
                // Store reference
                this._tempHighlightSpan = span;
                
                // Force a reflow
                void span.offsetHeight;
                
                // Verify highlight is in DOM
                if (!span.parentNode) {
                    logger.error('Highlight span not in DOM after extractContents');
                    throw new Error('Highlight span not in DOM');
                }
                
                // Clear browser selection after a delay
                setTimeout(() => {
                    const selection = window.getSelection();
                    if (selection && selection.rangeCount > 0) {
                        selection.removeAllRanges();
                        logger.log('Browser selection cleared (extractContents)');
                    }
                }, 300);
            } catch (e2) {
                logger.error('Could not highlight selected text', e2);
                this._tempHighlightSpan = null;
            }
        }
    }

    /**
     * Remove temporary highlight
     */
    removeTemporaryHighlight() {
        if (this._tempHighlightSpan && this._tempHighlightSpan.parentNode) {
            const parent = this._tempHighlightSpan.parentNode;
            while (this._tempHighlightSpan.firstChild) {
                parent.insertBefore(this._tempHighlightSpan.firstChild, this._tempHighlightSpan);
            }
            parent.removeChild(this._tempHighlightSpan);
            this._tempHighlightSpan = null;
        }
    }

    /**
     * Create comment from selected text
     */
    async onCreateCommentFromSelection() {
        if (!this.state.currentTextSelection || !this.state.currentArticle) {
            this.showNotification('กรุณาเลือกข้อความก่อนสร้าง comment', 'warning');
            return;
        }

        // Open comment panel if not already open
        if (!this.state.showCommentPanel) {
            this.state.showCommentPanel = true;
        }

        // Hide button
        this.state.showCommentButton = false;
        
        // Trigger comment creation - will be handled by CommentOverlay via props
        // Wait a bit for panel to open before triggering
        await new Promise(resolve => setTimeout(resolve, 100));
        this.state.triggerCommentCreation = true;
        
        // Clear trigger after component reacts
        setTimeout(() => {
            this.state.triggerCommentCreation = false;
        }, 50);
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
        // Also render a floating TOC on the right side for quick navigation
        const tocHeadings = Array.from(headings);
        this._renderFloatingTOC(tocHTML, tocHeadings);
        
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

    /**
     * Mirror the TOC into a floating panel on the right so users can jump to other headings quickly.
     */
    _renderFloatingTOC(tocHTML, headings = []) {
        if (!tocHTML) {
            return;
        }
        this._floatingTOCHeadings = Array.from(headings || []);

        // Create container once
        if (!this.floatingTOCContainer) {
            this.floatingTOCContainer = document.createElement('div');
            this.floatingTOCContainer.className = 'o_knowledge_floating_toc';

            // Append inside the main view if possible; fallback to body
            const host = this.el || document.body;
            host.appendChild(this.floatingTOCContainer);
        }

        this.floatingTOCContainer.innerHTML = tocHTML;

        // Delegate clicks to reuse smooth scroll behaviour
        this.floatingTOCContainer.onclick = (e) => {
            const link = e.target.closest('.o_toc_link');
            if (!link) return;
            e.preventDefault();
            const headingId = link.getAttribute('data-heading-id');
            if (!headingId) return;
            this._scrollToHeading(headingId);
        };
        this._updateFloatingTOCActive();
        // หากมี inline TOC จะให้ observer เป็นตัวตัดสินใจเปิด/ปิด
        if (!this.inlineTOCElement) {
            this._toggleFloatingTOC(true);
        } else {
            this._toggleFloatingTOC(false);
        }
    }

    /**
     * Highlight query occurrences inside article content and scroll to the first match.
     */
    _highlightQueryInContent(query) {
        if (!query || !this.contentRef || !this.contentRef.el) {
            return;
        }
        const terms = query.split(/\s+/).filter(Boolean);
        if (!terms.length) return;

        // Remove previous highlights
        const removeMarks = () => {
            this.contentRef.el.querySelectorAll('.o_knowledge_highlight').forEach((mark) => {
                const parent = mark.parentNode;
                if (parent) {
                    parent.replaceChild(document.createTextNode(mark.textContent), mark);
                    parent.normalize();
                }
            });
        };
        removeMarks();

        const regex = new RegExp(terms.map((t) => t.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&")).join("|"), "gi");
        const walker = document.createTreeWalker(this.contentRef.el, NodeFilter.SHOW_TEXT, null);
        const textNodes = [];
        while (walker.nextNode()) {
            textNodes.push(walker.currentNode);
        }

        textNodes.forEach((node) => {
            if (!node.nodeValue) return;
            if (!regex.test(node.nodeValue)) {
                // reset lastIndex for next node
                regex.lastIndex = 0;
                return;
            }
            const frag = document.createDocumentFragment();
            let lastIndex = 0;
            let match;
            regex.lastIndex = 0;
            while ((match = regex.exec(node.nodeValue)) !== null) {
                const start = match.index;
                const end = start + match[0].length;
                if (start > lastIndex) {
                    frag.appendChild(document.createTextNode(node.nodeValue.substring(lastIndex, start)));
                }
                const mark = document.createElement("mark");
                mark.className = "o_knowledge_highlight";
                mark.textContent = node.nodeValue.substring(start, end);
                frag.appendChild(mark);
                lastIndex = end;
            }
            if (lastIndex < node.nodeValue.length) {
                frag.appendChild(document.createTextNode(node.nodeValue.substring(lastIndex)));
            }
            node.parentNode.replaceChild(frag, node);
        });

        // cache highlights
        this._highlightNodes = Array.from(this.contentRef.el.querySelectorAll('.o_knowledge_highlight'));
        this._highlightIndex = 0;
        this._scrollToHighlightIndex();
    }

    _scrollToHeading(headingId) {
        if (!headingId) return;
        let targetHeading = document.getElementById(headingId);
        if (!targetHeading && this.contentRef && this.contentRef.el) {
            targetHeading = this.contentRef.el.querySelector(`#${headingId}`);
        }
        if (!targetHeading) return;

        const offset = 110;
        // ใช้ scrollIntoView เพื่อเลื่อนไปก่อน แล้วชดเชย offset
        targetHeading.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' });
        // ชดเชย header หลัง scrollIntoView
        requestAnimationFrame(() => {
            const rect = targetHeading.getBoundingClientRect();
            const currentScroll = window.pageYOffset ||
                document.documentElement.scrollTop ||
                document.body.scrollTop || 0;
            const targetPosition = rect.top + currentScroll - offset;
            window.scrollTo({ top: Math.max(0, targetPosition), behavior: 'smooth' });
        });
    }

    _scrollToHighlightIndex() {
        if (!this._highlightNodes || !this._highlightNodes.length) return;
        const node = this._highlightNodes[this._highlightIndex];
        const rect = node.getBoundingClientRect();
        const currentScroll = window.pageYOffset ||
            document.documentElement.scrollTop ||
            document.body.scrollTop || 0;
        const offset = 120;
        const targetPos = rect.top + currentScroll - offset;
        window.scrollTo({ top: Math.max(0, targetPos), behavior: 'smooth' });
    }

    _setupFloatingTOCObserver(headings = []) {
        if (!this.inlineTOCElement) {
            this._toggleFloatingTOC(false);
            return;
        }
        // ใช้ IntersectionObserver เพื่อแสดง TOC ลอยเมื่อ inline TOC หลุดจอ
        if (this._tocObserver) {
            this._tocObserver.disconnect();
        }
        if ('IntersectionObserver' in window) {
            this._tocObserver = new IntersectionObserver((entries) => {
                const entry = entries[0];
                if (entry && entry.isIntersecting) {
                    this._toggleFloatingTOC(false);
                } else if (this._floatingTOCHeadings.length || headings.length) {
                    if (!this._floatingTOCHeadings.length) {
                        this._floatingTOCHeadings = Array.from(headings || []);
                    }
                    this._toggleFloatingTOC(true);
                    this._updateFloatingTOCActive();
                }
            }, { threshold: 0 });
            this._tocObserver.observe(this.inlineTOCElement);
        } else {
            // fallback: check on scroll
            const check = () => {
                if (!this.inlineTOCElement) return;
                const rect = this.inlineTOCElement.getBoundingClientRect();
                if (rect.bottom < 0) {
                    this._toggleFloatingTOC(true);
                    this._updateFloatingTOCActive();
                } else {
                    this._toggleFloatingTOC(false);
                }
            };
            window.addEventListener('scroll', check, { passive: true });
        }
    }

    _toggleFloatingTOC(show) {
        if (!this.floatingTOCContainer) return;
        this.floatingTOCContainer.style.display = show ? 'block' : 'none';
    }

    _buildTOCHTMLFromHeadings(headings) {
        let tocHTML = '<div class="o_toc_header"><h3>Table of Contents</h3></div><ul class="o_toc_list">';
        headings.forEach((heading, index) => {
            const level = parseInt(heading.tagName.charAt(1));
            const indentClass = `o_toc_level_${level}`;
            const text = heading.textContent.trim();
            if (!heading.id) {
                const slug = text.toLowerCase().replace(/[^a-z0-9]+/g, '-').substring(0, 50);
                heading.id = `toc-heading-${index}-${slug}`;
            }
            tocHTML += `
                <li class="o_toc_item ${indentClass}">
                    <a href="#${heading.id}" class="o_toc_link" data-heading-id="${heading.id}">
                        ${text}
                    </a>
                </li>`;
        });
        tocHTML += '</ul>';
        return tocHTML;
    }

    _updateFloatingTOCActive() {
        if (!this.floatingTOCContainer || !this._floatingTOCHeadings.length) return;
        const scrollPos = window.scrollY || document.documentElement.scrollTop || 0;
        const offset = 140;
        let activeId = null;
        this._floatingTOCHeadings.forEach((h) => {
            const rect = h.getBoundingClientRect();
            const top = rect.top + scrollPos - offset;
            if (scrollPos >= top) {
                activeId = h.id;
            }
        });
        const links = this.floatingTOCContainer.querySelectorAll('.o_toc_link');
        links.forEach((link) => {
            const id = link.getAttribute('data-heading-id');
            if (id === activeId) {
                link.classList.add('o_toc_active');
            } else {
                link.classList.remove('o_toc_active');
            }
        });
    }
}

KnowledgeDocumentController.template = "knowledge_onthisday_oca.KnowledgeDocumentView";

// Register as client action
registry.category("actions").add("knowledge_document_view", KnowledgeDocumentController);
