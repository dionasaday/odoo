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
        this._loadingArticleId = null; // Track which article ID is currently being loaded
        this._loadedArticles = [];
        this._shareInviteTimer = null;
        this._shareInviteBlurTimer = null;
        
        this.state = useState({
            selectedArticleId: null,
            searchQuery: "",
            searchLoading: false,
            searchResults: [],
            searchTotal: 0,
            searchPage: 1,
            searchPageSize: 10,
            articlePage: 1,
            articlePageSize: 200,
            hasMoreArticles: false,
            loadingMoreArticles: false,
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
            sharePublic: false, // Public share toggle
            shareDefaultPermission: "read", // Default share permission
            shareMembers: [], // Share members list
            shareCategoryName: null, // Category name for default access
            shareInviteQuery: "", // Invite input value
            shareInvitePermission: "read", // Invite permission
            shareInviteLoading: false, // Invite loading state
            shareCanManage: false, // Permission to manage sharing
            shareInviteSuggestions: [], // Invite suggestions
            shareInviteUserId: null, // Selected user id from suggestions
            selectedTagId: null, // Selected tag for filtering
            availableTags: [], // List of all available tags
            sidebarOpenMobile: false, // Mobile drawer state
            showCommentPanel: false, // Toggle comment panel visibility
            showCommentButton: false, // Show floating comment button when text is selected
            commentButtonPosition: { top: 0, left: 0 }, // Position of floating comment button
            currentTextSelection: null, // Current text selection data
            triggerCommentCreation: false, // Trigger comment creation from floating button
            newCommentBody: "", // Draft comment body
            dashboardCards: {
                recent: [],
                popular: [],
                updated: [],
                newest: [],
            },
            dashboardLoading: false,
        });
        this._floatingTOCHeadings = [];
        this.inlineTOCElement = null;
        this._tocObserver = null;
        this._tocHiddenKey = "knowledge_onthisday_toc_hidden";
        this._tocHidden = false;
        this._tocShouldShow = false;
        this.tocToggleButton = null;
        this._onScrollFloatingTOC = () => {
            if (this._floatingTOCHeadings.length === 0 || !this.floatingTOCContainer) {
                return;
            }
            window.requestAnimationFrame(() => this._updateFloatingTOCActive());
        };

        onWillStart(async () => {
            try {
                this._tocHidden = window.localStorage.getItem(this._tocHiddenKey) === "1";
            } catch (error) {
                this._tocHidden = false;
            }
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
            await this.loadArticles(1, false);
            await this.loadDashboardCards();
            const actionArticleId = this._getActionArticleId();
            if (actionArticleId) {
                this.state.selectedArticleId = actionArticleId;
                await this.openArticle(actionArticleId);
            }
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
        }, () => [this.state.currentArticle?.id, this.state.currentArticle?.content, this.state.currentArticle?.pdfAttachment]);

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
            if (this.tocToggleButton && this.tocToggleButton.parentNode) {
                this.tocToggleButton.parentNode.removeChild(this.tocToggleButton);
            }
            this.tocToggleButton = null;
        });
    }

    _getActionArticleId() {
        const action = this.props?.action || {};
        const params = action.params || {};
        const context = action.context || {};
        const rawId = params.article_id || context.knowledge_article_id || context.active_id;
        if (!rawId) {
            return null;
        }
        const parsed = parseInt(rawId, 10);
        return Number.isNaN(parsed) ? null : parsed;
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

    _normalizePdfUrl(pdfUrl) {
        if (!pdfUrl) {
            return pdfUrl;
        }
        const currentOrigin = window.location.origin || `${window.location.protocol}//${window.location.host}`;
        try {
            const parsedUrl = new URL(pdfUrl, currentOrigin);
            if (parsedUrl.origin !== currentOrigin) {
                return `${currentOrigin}${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
            }
            return parsedUrl.toString();
        } catch (error) {
            logger.warn("Failed to normalize PDF URL, using raw value", { pdfUrl, error });
            return pdfUrl;
        }
    }

    renderContent() {
        logger.log("renderContent() called", {
            hasContentRef: !!this.contentRef.el,
            hasCurrentArticle: !!this.state.currentArticle,
            currentArticleId: this.state.currentArticle?.id,
            hasPdfAttachment: !!(this.state.currentArticle?.pdfAttachment?.id)
        });
        
        if (!this.contentRef.el) {
            logger.warn("renderContent() called but contentRef.el is null");
            return;
        }
        
        if (!this.state.currentArticle) {
            logger.log("renderContent() called but currentArticle is null, clearing content");
            this.contentRef.el.innerHTML = "";
            return;
        }
        
        // Check if there's a PDF attachment - if yes, show PDF viewer instead of HTML content
        // CRITICAL: Always check currentArticle exists and has the expected ID before rendering PDF
        if (!this.state.currentArticle || !this.state.currentArticle.id) {
            logger.log("No current article, clearing content");
            // Remove any PDF viewer that might be lingering
            const existingPdfViewer = this.contentRef.el?.querySelector('.o_knowledge_pdf_viewer_container');
            if (existingPdfViewer) {
                existingPdfViewer.remove();
            }
            this.contentRef.el.innerHTML = "";
            return;
        }
        
        const currentArticleId = this.state.currentArticle.id;
        const pdfAttachment = this.state.currentArticle.pdfAttachment;
        
        logger.log("renderContent() processing article:", {
            articleId: currentArticleId,
            hasPdfAttachment: !!pdfAttachment,
            pdfAttachmentId: pdfAttachment?.id,
            pdfAttachmentName: pdfAttachment?.name
        });
        
        // CRITICAL: Always check and remove PDF viewer from different article first
        const existingPdfViewer = this.contentRef.el?.querySelector('.o_knowledge_pdf_viewer_container');
        if (existingPdfViewer) {
            const existingArticleId = existingPdfViewer.getAttribute('data-article-id');
            if (existingArticleId && parseInt(existingArticleId) !== currentArticleId) {
                logger.log("Removing PDF viewer from different article:", existingArticleId, "for current article:", currentArticleId);
                existingPdfViewer.remove();
            }
        }
        
        // CRITICAL: If no PDF attachment, remove any existing PDF viewer first
        if (!pdfAttachment || !pdfAttachment.id) {
            if (existingPdfViewer) {
                const existingArticleId = existingPdfViewer.getAttribute('data-article-id');
                logger.log("No PDF attachment for article:", currentArticleId, "- removing existing PDF viewer from article:", existingArticleId);
                existingPdfViewer.remove();
            }
            // Fall through to render HTML content
        } else if (this._loadingArticleId !== null && this._loadingArticleId !== currentArticleId) {
            // CRITICAL: Check if we're still loading the same article (prevent showing PDF from different article)
            logger.warn("Article ID mismatch in renderContent. Loading article ID:", this._loadingArticleId, "Current article ID:", currentArticleId, "- Not rendering PDF");
            // Remove PDF viewer if article ID doesn't match
            if (existingPdfViewer) {
                existingPdfViewer.remove();
            }
            // Fall through to render HTML content instead
        } else if (pdfAttachment && pdfAttachment.id) {
            logger.log("Rendering PDF viewer with attachment ID:", pdfAttachment.id, "for article:", currentArticleId, "contentRef.el exists:", !!this.contentRef.el);
            
            if (!this.contentRef.el) {
                logger.error("Cannot render PDF viewer: contentRef.el is null!");
                return;
            }
            
            // Use access_url for inline viewing (without download parameter)
            const rawPdfUrl = pdfAttachment.access_url || pdfAttachment.url;
            const rawDownloadUrl = pdfAttachment.url || pdfAttachment.access_url;
            let pdfUrl = this._normalizePdfUrl(rawPdfUrl);
            const downloadUrl = this._normalizePdfUrl(rawDownloadUrl || rawPdfUrl);
            const pdfName = pdfAttachment.name || 'PDF Document';
            
            if (!pdfUrl) {
                logger.error("Cannot render PDF viewer: PDF URL is empty!", pdfAttachment);
                return;
            }
            
            // Remove download parameter to enable inline viewing
            pdfUrl = pdfUrl.replace('?download=true', '').replace('&download=true', '');
            
            // Add unique parameter with article ID and timestamp to force browser to reload PDF
            // This prevents browser from caching and showing PDF from previous article
            const separator = pdfUrl.includes('?') ? '&' : '?';
            const uniqueParam = `article=${currentArticleId}&_t=${Date.now()}`;
            pdfUrl = `${pdfUrl}${separator}${uniqueParam}`;
            
            logger.log("PDF URL for viewer (with cache buster):", pdfUrl);
            
            // Use iframe for PDF viewer (works in modern browsers)
            // Most browsers will display PDF inline with toolbar by default
            // CRITICAL: Triple-check article ID before rendering to prevent showing wrong PDF
            if (this.state.currentArticle && 
                this.state.currentArticle.id === currentArticleId &&
                (this._loadingArticleId === null || this._loadingArticleId === currentArticleId)) {
                
                // CRITICAL: Remove any existing PDF viewer from different article before rendering new one
                // Search in entire document to catch all PDF viewers (not just in contentRef.el)
                const allPdfViewersBeforeRender = document.querySelectorAll('.o_knowledge_pdf_viewer_container');
                if (allPdfViewersBeforeRender.length > 0) {
                    logger.log("Found", allPdfViewersBeforeRender.length, "PDF viewer(s) before render, checking...");
                    let shouldSkipRender = false;
                    
                    allPdfViewersBeforeRender.forEach((viewer) => {
                        const viewerArticleId = viewer.getAttribute('data-article-id');
                        const viewerAttachmentId = viewer.getAttribute('data-attachment-id');
                        
                        if (viewerArticleId && parseInt(viewerArticleId) !== currentArticleId) {
                            // Different article - always remove
                            logger.log("Removing PDF viewer from different article:", viewerArticleId, "before rendering new article:", currentArticleId);
                            
                            // CRITICAL: Clear iframe src first to stop loading and clear browser cache
                            const iframe = viewer.querySelector('.o_knowledge_pdf_viewer');
                            if (iframe) {
                                iframe.src = 'about:blank';
                                logger.log(`Cleared iframe src for PDF viewer from article ${viewerArticleId}`);
                            }
                            
                            viewer.remove();
                        } else if (viewerArticleId && parseInt(viewerArticleId) === currentArticleId) {
                            // Same article, check if attachment ID matches
                            if (viewerAttachmentId && parseInt(viewerAttachmentId) === pdfAttachment.id) {
                                logger.log("PDF viewer already rendered for same article and attachment, will skip re-render");
                                shouldSkipRender = true;
                                // Don't remove, keep it
                            } else {
                                logger.log("PDF attachment changed for same article, removing old viewer (old attachment:", viewerAttachmentId, "new attachment:", pdfAttachment.id);
                                
                                // CRITICAL: Clear iframe src first
                                const iframe = viewer.querySelector('.o_knowledge_pdf_viewer');
                                if (iframe) {
                                    iframe.src = 'about:blank';
                                }
                                
                                viewer.remove();
                            }
                        }
                    });
                    
                    // If we found a matching viewer, skip re-render
                    if (shouldSkipRender) {
                        logger.log("Skipping PDF viewer re-render - already exists for article:", currentArticleId, "attachment:", pdfAttachment.id);
                        return;
                    }
                }
                
                try {
                    this.contentRef.el.innerHTML = `
                        <div class="o_knowledge_pdf_viewer_container" data-article-id="${currentArticleId}" data-attachment-id="${pdfAttachment.id}">
                            <iframe 
                                src="${pdfUrl}" 
                                class="o_knowledge_pdf_viewer"
                                title="${pdfName}"
                                type="application/pdf"
                                allow="fullscreen"
                                data-article-id="${currentArticleId}">
                                <p class="o_knowledge_pdf_fallback_message">
                                    เบราว์เซอร์ของคุณไม่รองรับการแสดง PDF ในหน้าเว็บ 
                                    <a href="${downloadUrl || pdfUrl}" target="_blank" download="${pdfName}" class="btn btn-primary" style="margin-top: 10px; display: inline-block;">
                                        ดาวน์โหลด PDF
                                    </a>
                                </p>
                            </iframe>
                        </div>
                    `;
                    logger.log("PDF viewer iframe created for article:", currentArticleId, "attachment ID:", pdfAttachment.id, "contentRef.el.innerHTML length:", this.contentRef.el.innerHTML.length);
                    
                    // Verify PDF viewer was actually inserted
                    const insertedViewer = this.contentRef.el.querySelector('.o_knowledge_pdf_viewer_container');
                    if (insertedViewer) {
                        logger.log("PDF viewer successfully inserted into DOM");
                    } else {
                        logger.error("PDF viewer was NOT inserted into DOM! innerHTML may have been cleared.");
                    }
                    
                    // Setup text selection listener for PDF viewer (may not work in iframe, but try anyway)
                    this.setupTextSelectionListener();
                    return;
                } catch (renderError) {
                    logger.error("Error rendering PDF viewer:", renderError);
                    // Fall through to render HTML content if PDF viewer fails
                }
            } else {
                logger.warn("Article ID mismatch - not rendering PDF viewer. Current article ID:", this.state.currentArticle?.id, "Expected:", currentArticleId, "Loading article ID:", this._loadingArticleId);
                // Fall through to render HTML content instead
            }
        }
        
        // No PDF attachment or article ID mismatch - render HTML content
        // CRITICAL: If we reached here, there's no PDF attachment or article ID mismatch
        // Check again for PDF viewer (existingPdfViewer might have been removed already)
        const remainingPdfViewer = this.contentRef.el?.querySelector('.o_knowledge_pdf_viewer_container');
        if (remainingPdfViewer) {
            const remainingArticleId = remainingPdfViewer.getAttribute('data-article-id');
            if (remainingArticleId && parseInt(remainingArticleId) !== currentArticleId) {
                logger.log("Removing remaining PDF viewer from different article:", remainingArticleId, "for current article:", currentArticleId);
                remainingPdfViewer.remove();
            } else if (remainingArticleId && parseInt(remainingArticleId) === currentArticleId) {
                // Same article but no PDF attachment - remove PDF viewer
                logger.log("No PDF attachment for article:", currentArticleId, "- removing remaining PDF viewer");
                remainingPdfViewer.remove();
            }
        }
        
        if (!pdfAttachment || !pdfAttachment.id) {
            logger.log("No PDF attachment found for article:", currentArticleId, "- rendering HTML content instead");
        }
        
        const content = this.state.currentArticle.content;
        const childArticles = this.state.currentArticle.children || [];
        const hasChildArticles = Array.isArray(childArticles) && childArticles.length > 0;
        const trimmedContent = typeof content === 'string' ? content.trim() : "";
        if (!trimmedContent && hasChildArticles) {
            this.contentRef.el.innerHTML = this._buildChildArticlesHtml(childArticles);
            this._bindChildArticleClicks();
            return;
        }
        const contentWithChildren = hasChildArticles
            ? `${content}${this._buildChildArticlesHtml(childArticles)}`
            : content;
        
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
        if (contentWithChildren && typeof contentWithChildren === 'string' && contentWithChildren.trim().length > 0) {
            // Wait for stylesheets to load to prevent FOUC and layout warnings
            if (!areStylesheetsLoaded()) {
                // Wait for stylesheets to be ready with multiple checks
                const checkAndRender = () => {
                    if (areStylesheetsLoaded()) {
                        // CRITICAL: Check if PDF viewer is already rendered - don't render HTML content if PDF viewer exists
                        const existingPdfViewer = this.contentRef.el?.querySelector('.o_knowledge_pdf_viewer_container');
                        if (existingPdfViewer) {
                            const existingArticleId = existingPdfViewer.getAttribute('data-article-id');
                            if (existingArticleId && parseInt(existingArticleId) === this.state.currentArticle?.id) {
                                logger.log("PDF viewer already rendered, skipping HTML content render in checkAndRender");
                                return;
                            }
                        }
                        if (this.contentRef.el && this.state.currentArticle) {
                            this.contentRef.el.innerHTML = contentWithChildren;
                            this._bindChildArticleClicks();
                            const activeQuery = (this.state.lastSearchQuery || "").trim();
                            if (activeQuery) {
                                this._highlightQueryInContent(activeQuery);
                            }
                            this.processTOCAfterRender();
                            // Re-initialize code block copy buttons and syntax highlighting
                            // Use a small delay to ensure DOM is fully rendered
                            setTimeout(() => {
                                this._initializeCodeBlocks();
                            }, 100);
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
                // CRITICAL: Check if PDF viewer is already rendered - don't render HTML content if PDF viewer exists
                const existingPdfViewer = this.contentRef.el?.querySelector('.o_knowledge_pdf_viewer_container');
                if (existingPdfViewer) {
                    const existingArticleId = existingPdfViewer.getAttribute('data-article-id');
                    if (existingArticleId && parseInt(existingArticleId) === this.state.currentArticle?.id) {
                        logger.log("PDF viewer already rendered, skipping HTML content render in requestAnimationFrame");
                        return;
                    }
                }
                if (this.contentRef.el && this.state.currentArticle) {
                    // CRITICAL: Preserve all whitespace and line breaks in HTML content
                    // Don't normalize or trim - preserve exact formatting from editor
                    this.contentRef.el.innerHTML = contentWithChildren;
                    this._bindChildArticleClicks();
                    const activeQuery = (this.state.lastSearchQuery || "").trim();
                    if (activeQuery) {
                        this._highlightQueryInContent(activeQuery);
                    }
                    this.processTOCAfterRender();
                    this.setupTextSelectionListener();
                    // Re-initialize code block copy buttons and syntax highlighting
                    // Use a small delay to ensure DOM is fully rendered
                    setTimeout(() => {
                        this._initializeCodeBlocks();
                    }, 100);
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

    async loadArticles(page = 1, append = false) {
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
            const limit = this.state.articlePageSize || 200;
            const offset = (page - 1) * limit;
            let totalCount = null;
            // According to Odoo 19 docs, start with minimal fields to avoid RPC errors
            // Then add more fields if successful
            const basicFields = ["id", "name", "active"];
            const extendedFields = ["icon", "category_id", "parent_id", "responsible_id", "write_date", "create_date"];
            const relationFields = ["favorite_user_ids", "shared_user_ids", "share_token", "tag_ids"];
            const order = "parent_id asc, sequence asc, name asc";
            
            try {
                try {
                    totalCount = await this.orm.searchCount("knowledge.article", domain);
                } catch (countError) {
                    logger.warn("Error counting articles:", countError);
                }
                // Step 1: Try with basic fields only first
                articles = await this.orm.searchRead(
                    "knowledge.article",
                    domain,
                    basicFields,
                    { limit, offset, order }
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
                        { limit, offset, order }
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
                            { limit, offset, order }
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

                article.article_icon = article.icon || article.category_icon || '📝';
            });

            if (append) {
                const merged = new Map(this._loadedArticles.map(a => [a.id, a]));
                articles.forEach(article => merged.set(article.id, article));
                this._loadedArticles = Array.from(merged.values());
            } else {
                this._loadedArticles = articles;
            }
            const allArticles = this._loadedArticles;
            
            // Build tree structure
            // For favorites/shared/private sections, don't group by category
            if (this.state.activeSection === "favorites" || 
                this.state.activeSection === "shared" || 
                this.state.activeSection === "private") {
                // For these sections, create a flat list without category grouping
                const flatTree = this.buildFlatTree(allArticles);
                // Set articles directly without category structure
                this.state.articles = flatTree;
                this.state.articlePage = page;
                if (totalCount !== null) {
                    this.state.hasMoreArticles = offset + articles.length < totalCount;
                } else {
                    this.state.hasMoreArticles = articles.length === limit;
                }
                return; // Early return for flat sections
            }
            
            // For workspace, use category grouping
            this.buildTree(allArticles, categoryMap);
            
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
            this.state.articlePage = page;
            if (totalCount !== null) {
                this.state.hasMoreArticles = offset + articles.length < totalCount;
            } else {
                this.state.hasMoreArticles = articles.length === limit;
            }

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
            this.state.hasMoreArticles = false;
        } finally {
            this.state.loading = false;
            this.state.loadingMoreArticles = false;
        }
    }

    async loadMoreArticles() {
        if (this.state.loadingMoreArticles || !this.state.hasMoreArticles) {
            return;
        }
        this.state.loadingMoreArticles = true;
        const nextPage = (this.state.articlePage || 1) + 1;
        await this.loadArticles(nextPage, true);
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
            if (article.article_icon) {
                articleNode.article_icon = article.article_icon;
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

    _findArticleNodeInState(articleId) {
        const findInArticles = (articles = []) => {
            for (const article of articles) {
                if (article.id === articleId) {
                    return article;
                }
                const found = findInArticles(article.children || []);
                if (found) {
                    return found;
                }
            }
            return null;
        };

        const stateArticles = this.state.articles || [];
        if (!stateArticles.length) {
            return null;
        }

        if (this.state.activeSection === "workspace" || !this.state.activeSection) {
            for (const category of stateArticles) {
                const found = findInArticles(category.articles || []);
                if (found) {
                    return found;
                }
            }
            return null;
        }

        return findInArticles(stateArticles);
    }

    _formatArticleDate(dateString) {
        if (!dateString) {
            return "";
        }
        const normalized = String(dateString).replace(" ", "T");
        const date = new Date(normalized);
        if (Number.isNaN(date.getTime())) {
            return dateString;
        }
        try {
            return new Intl.DateTimeFormat("th-TH", {
                day: "2-digit",
                month: "short",
                year: "numeric",
            }).format(date);
        } catch (error) {
            return date.toLocaleDateString();
        }
    }

    async _loadChildArticles(articleId) {
        const stateNode = this._findArticleNodeInState(articleId);
        const stateChildren = stateNode?.children || [];
        if (stateChildren.length) {
            return stateChildren.map((child) => ({
                id: child.id,
                name: child.name,
                article_icon: child.article_icon || child.category_icon || '📝',
                create_date: child.create_date || null,
            }));
        }

        try {
            const children = await this.orm.searchRead(
                "knowledge.article",
                [["parent_id", "=", articleId], ["active", "=", true]],
                ["id", "name", "icon", "category_id", "create_date"],
                { order: "sequence, name" }
            );
            if (!children || !children.length) {
                return [];
            }
            const categoryIds = Array.from(new Set(
                children
                    .map((child) => Array.isArray(child.category_id) ? child.category_id[0] : null)
                    .filter((id) => !!id)
            ));
            let categoryIconMap = new Map();
            if (categoryIds.length) {
                const categories = await this.orm.read(
                    "knowledge.article.category",
                    categoryIds,
                    ["id", "icon"]
                );
                categoryIconMap = new Map(categories.map(cat => [cat.id, cat.icon || '📝']));
            }
            return children.map((child) => ({
                id: child.id,
                name: child.name,
                article_icon: child.icon || categoryIconMap.get(child.category_id?.[0]) || '📝',
                create_date: child.create_date || null,
            }));
        } catch (error) {
            logger.error("Error loading child articles:", error);
            return [];
        }
    }

    _buildChildArticlesHtml(childArticles) {
        const items = childArticles.map((child) => {
            const formattedDate = this._formatArticleDate(child.create_date);
            const dateHtml = formattedDate
                ? `<span class="o_knowledge_children_date">เพิ่มเมื่อ ${formattedDate}</span>`
                : "";
            return `
            <li class="o_knowledge_children_item" data-article-id="${child.id}" tabindex="0">
                <span class="o_knowledge_children_icon">${child.article_icon || '📝'}</span>
                <span class="o_knowledge_children_name">${child.name}</span>
                ${dateHtml}
            </li>
        `;
        }).join("");

        return `
            <div class="o_knowledge_children_block">
                <div class="o_knowledge_children_title">บทความในหมวดนี้</div>
                <ul class="o_knowledge_children_list">
                    ${items}
                </ul>
            </div>
        `;
    }

    _bindChildArticleClicks() {
        if (!this.contentRef.el) {
            return;
        }
        const items = this.contentRef.el.querySelectorAll('.o_knowledge_children_item[data-article-id]');
        if (!items.length) {
            return;
        }
        items.forEach((item) => {
            item.addEventListener('click', (ev) => {
                ev.preventDefault();
                ev.stopPropagation();
                const articleId = parseInt(item.getAttribute('data-article-id'));
                if (articleId) {
                    this.onArticleClick(articleId, ev);
                }
            });
            item.addEventListener('keydown', (ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault();
                    ev.stopPropagation();
                    const articleId = parseInt(item.getAttribute('data-article-id'));
                    if (articleId) {
                        this.onArticleClick(articleId, ev);
                    }
                }
            });
        });
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
        
        // CRITICAL: Log article click for debugging
        const currentArticleId = this.state.currentArticle?.id;
        logger.log("Article clicked. Current article ID:", currentArticleId, "New article ID:", articleId);
        
        // CRITICAL: If clicking the same article, don't reload
        if (currentArticleId === articleId) {
            logger.log("Same article clicked, skipping reload");
            return;
        }
        
        // CRITICAL: Remove any existing PDF viewer BEFORE calling openArticle
        // This ensures PDF viewer is removed even if openArticle fails or is async
        const allPdfViewersBeforeClick = document.querySelectorAll('.o_knowledge_pdf_viewer_container');
        if (allPdfViewersBeforeClick.length > 0) {
            logger.log("Found", allPdfViewersBeforeClick.length, "PDF viewer(s) before article click, removing all");
            allPdfViewersBeforeClick.forEach((viewer, index) => {
                const viewerArticleId = viewer.getAttribute('data-article-id');
                logger.log(`Removing PDF viewer ${index + 1} (article: ${viewerArticleId}) before opening article: ${articleId}`);
                
                // CRITICAL: Clear iframe src first to stop loading and clear browser cache
                const iframe = viewer.querySelector('.o_knowledge_pdf_viewer');
                if (iframe) {
                    iframe.src = 'about:blank';
                    logger.log(`Cleared iframe src for PDF viewer ${index + 1}`);
                }
                
                // Remove the viewer container
                viewer.remove();
                logger.log(`Removed PDF viewer ${index + 1}`);
            });
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
            
            // CRITICAL: Track which article ID we're loading to prevent race conditions
            this._loadingArticleId = articleId;
            
            // CRITICAL: Set currentArticle to null first to completely clear previous state
            // This ensures PDF attachment and all previous article data is cleared
            const previousArticleId = this.state.currentArticle?.id;
            this.state.currentArticle = null;
            
            // Clear content area immediately to prevent showing old content
            // Also remove any existing PDF viewer to prevent showing cached PDF
            if (this.contentRef.el) {
                // CRITICAL: Remove any existing PDF viewer container (includes iframe) FIRST
                // Search in the entire document, not just contentRef.el, to catch PDF viewers that might be outside
                const allPdfViewers = document.querySelectorAll('.o_knowledge_pdf_viewer_container');
                if (allPdfViewers.length > 0) {
                    logger.log("Found", allPdfViewers.length, "PDF viewer(s) in document, removing all");
                    allPdfViewers.forEach((viewer, index) => {
                        const viewerArticleId = viewer.getAttribute('data-article-id');
                        logger.log(`Removing PDF viewer ${index + 1} (article: ${viewerArticleId}) before loading new article: ${articleId}`);
                        
                        // CRITICAL: Clear iframe src first to stop loading and clear browser cache
                        const iframe = viewer.querySelector('.o_knowledge_pdf_viewer');
                        if (iframe) {
                            iframe.src = 'about:blank';
                            logger.log(`Cleared iframe src for PDF viewer ${index + 1}`);
                        }
                        
                        // Remove the viewer container
                        viewer.remove();
                        logger.log(`Removed PDF viewer ${index + 1}`);
                    });
                }
                
                // Also remove any orphaned iframe (fallback) - search in entire document
                const allOrphanedIframes = document.querySelectorAll('.o_knowledge_pdf_viewer:not(.o_knowledge_pdf_viewer_container .o_knowledge_pdf_viewer)');
                if (allOrphanedIframes.length > 0) {
                    logger.log("Found", allOrphanedIframes.length, "orphaned PDF iframe(s), removing");
                    allOrphanedIframes.forEach((iframe, index) => {
                        logger.log(`Clearing and removing orphaned PDF iframe ${index + 1}`);
                        iframe.src = 'about:blank';
                        iframe.remove();
                    });
                }
                
                // CRITICAL: Clear all content to ensure no PDF viewer remains
                this.contentRef.el.innerHTML = "";
                
                // Double-check: Remove any remaining PDF viewer elements (search in entire document)
                const remainingPdfViewers = document.querySelectorAll('.o_knowledge_pdf_viewer_container');
                if (remainingPdfViewers.length > 0) {
                    logger.warn("PDF viewer(s) still exist after innerHTML clear, force removing", remainingPdfViewers.length, "viewer(s)");
                    remainingPdfViewers.forEach((viewer) => {
                        const iframe = viewer.querySelector('.o_knowledge_pdf_viewer');
                        if (iframe) {
                            iframe.src = 'about:blank';
                        }
                        viewer.remove();
                    });
                }
            }
            
            logger.log("Cleared previous article state. Previous article ID:", previousArticleId, "Loading new article ID:", articleId);
            
            // Small delay to ensure state is cleared and UI updates
            await new Promise(resolve => setTimeout(resolve, 10));
            
            // CRITICAL: Check if article ID changed during delay (user clicked another article)
            if (this._loadingArticleId !== articleId) {
                logger.log("Article ID changed during clear delay, aborting load. Expected:", articleId, "Current:", this._loadingArticleId);
                return;
            }
            
            // Use searchRead to get article with all fields including content
            // Use basic fields first, then extend if needed
            let articles = [];
            try {
                articles = await this.orm.searchRead(
                    "knowledge.article",
                    [["id", "=", articleId]],
                    ["id", "name", "icon", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token", "share_public", "comment_count", "unresolved_comment_count"],
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
                        ["id", "name", "icon", "content", "category_id", "parent_id", "responsible_id", "active", "favorite_user_ids", "shared_user_ids", "share_token", "share_public", "share_link", "tag_ids", "comment_count", "unresolved_comment_count"],
                    { context: { safe_eval: true } }
                );
            }
            // CRITICAL: Check if article ID changed (user clicked another article)
            if (this._loadingArticleId !== articleId) {
                logger.log("Article ID changed before setting currentArticle, aborting. Expected:", articleId, "Current:", this._loadingArticleId);
                return;
            }
            
            if (article && article.length > 0) {
                // Create new article object and explicitly set pdfAttachment to null first
                this.state.currentArticle = {
                    ...article[0],
                    pdfAttachment: null, // Explicitly clear PDF attachment when loading new article
                };
                
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
                this.state.currentArticle.article_icon = this.state.currentArticle.icon || this.state.currentArticle.category_icon || '📝';
                
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
                
                // Load child articles for parent display (from state first, then fallback RPC)
                try {
                    const childArticles = await this._loadChildArticles(articleId);
                    if (this._loadingArticleId === articleId &&
                        this.state.currentArticle &&
                        this.state.currentArticle.id === articleId) {
                        this.state.currentArticle.children = childArticles;
                        this.state.currentArticle.hasChildren = childArticles.length > 0;
                    }
                } catch (childError) {
                    logger.error("Error setting child articles:", childError);
                    if (this._loadingArticleId === articleId &&
                        this.state.currentArticle &&
                        this.state.currentArticle.id === articleId) {
                        this.state.currentArticle.children = [];
                        this.state.currentArticle.hasChildren = false;
                    }
                }
                
                // Load PDF attachment if available
                // CRITICAL: Store article ID and loading article ID before async call to prevent race condition
                const currentArticleIdForPdf = this.state.currentArticle.id;
                const loadingArticleIdForPdf = this._loadingArticleId;
                
                // CRITICAL: Verify we're still loading the same article
                if (loadingArticleIdForPdf !== articleId || currentArticleIdForPdf !== articleId) {
                    logger.warn("Article ID mismatch before loading PDF attachment. Aborting. Expected:", articleId, "Current article:", currentArticleIdForPdf, "Loading:", loadingArticleIdForPdf);
                    return;
                }
                
                try {
                    logger.log("Calling get_pdf_attachment for article:", currentArticleIdForPdf);
                    const pdfAttachment = await this.orm.call(
                        "knowledge.article",
                        "get_pdf_attachment",
                        [currentArticleIdForPdf]
                    );
                    logger.log("PDF attachment loaded for article:", currentArticleIdForPdf, "Result:", pdfAttachment, "Type:", typeof pdfAttachment, "Has id:", !!pdfAttachment?.id, "Keys:", pdfAttachment ? Object.keys(pdfAttachment) : []);
                    
                    // CRITICAL: Triple-check that we're still loading the same article before setting PDF attachment
                    // Check both state article ID and loading article ID
                    if (this._loadingArticleId === articleId && 
                        this.state.currentArticle && 
                        this.state.currentArticle.id === currentArticleIdForPdf &&
                        this.state.currentArticle.id === articleId) {
                        // Check if pdfAttachment is not empty (has id property)
                        if (pdfAttachment && pdfAttachment.id) {
                            this.state.currentArticle.pdfAttachment = pdfAttachment;
                            logger.log("PDF attachment set in state for article:", currentArticleIdForPdf, "attachment ID:", pdfAttachment.id);
                        } else {
                            this.state.currentArticle.pdfAttachment = null;
                            logger.log("No PDF attachment found (empty result or no id) for article:", currentArticleIdForPdf);
                        }
                    } else {
                        logger.warn("Article ID changed during PDF attachment load. Ignoring PDF attachment. Expected:", articleId, "Current article ID:", this.state.currentArticle?.id, "Loading article ID:", this._loadingArticleId);
                    }
                } catch (pdfError) {
                    logger.error("Error loading PDF attachment for article:", currentArticleIdForPdf, pdfError);
                    // Only clear PDF attachment if we're still on the same article
                    if (this._loadingArticleId === articleId && 
                        this.state.currentArticle && 
                        this.state.currentArticle.id === currentArticleIdForPdf) {
                        this.state.currentArticle.pdfAttachment = null;
                    }
                }
                
                // Force trigger render after setting content and PDF attachment
                // Store article ID to prevent race condition when switching articles
                const currentArticleIdForRender = this.state.currentArticle.id;
                this.state.currentArticle = { ...this.state.currentArticle }; // Trigger reactivity
                
                // Wait for DOM to be ready, then render content
                await new Promise(resolve => setTimeout(resolve, 100));
                
                // Render content using innerHTML (this will check for PDF attachment)
                // Only render if article ID still matches (prevent race condition)
                if (this.contentRef.el && this.state.currentArticle && this.state.currentArticle.id === currentArticleIdForRender) {
                    this.renderContent();
                }
                
                // Also trigger via useEffect by updating state (only if article ID matches)
                if (this.state.currentArticle && this.state.currentArticle.id === currentArticleIdForRender) {
                    this.state.currentArticle = { ...this.state.currentArticle };
                }
                
                // Retry after delays to ensure content is rendered (including PDF)
                // Check article ID to prevent showing wrong article's content
                setTimeout(() => {
                    if (this.contentRef.el && this.state.currentArticle && this.state.currentArticle.id === currentArticleIdForRender) {
                        this.renderContent();
                    }
                }, 100);
                
                setTimeout(() => {
                    if (this.contentRef.el && this.state.currentArticle && this.state.currentArticle.id === currentArticleIdForRender) {
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
            // Clear loading article ID if we finished loading the expected article
            if (this._loadingArticleId === articleId) {
                this._loadingArticleId = null;
            }
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
        const recent = this.state.dashboardCards?.recent || [];
        if (recent.length) {
            return recent.slice(0, limit);
        }
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
        const popular = this.state.dashboardCards?.popular || [];
        if (popular.length) {
            return popular.slice(0, limit);
        }
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
        const newest = this.state.dashboardCards?.newest || [];
        if (newest.length) {
            return newest.slice(0, limit);
        }
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

    getRecentlyUpdatedArticles(limit = 5) {
        const updated = this.state.dashboardCards?.updated || [];
        if (updated.length) {
            return updated.slice(0, limit);
        }
        return [];
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
                const cleanText = a.clean_content || stripHtml(a.content);
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

    async onOpenRevisionHistory() {
        if (!this.state.currentArticle || !this.state.currentArticle.id) {
            return;
        }
        const action = {
            type: "ir.actions.act_window",
            name: "Revision History",
            res_model: "knowledge.article.revision",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: [["article_id", "=", this.state.currentArticle.id]],
            context: {
                default_article_id: this.state.currentArticle.id,
                search_default_article_id: this.state.currentArticle.id,
            },
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

    async loadDashboardCards(limit = 5) {
        this.state.dashboardLoading = true;
        try {
            const payload = await this.orm.call(
                "knowledge.article",
                "get_dashboard_cards",
                [],
                { limit }
            );
            const decorateUpdated = (items = []) => {
                return items.map((item) => ({
                    ...item,
                    change_before: item.change_before ? markup(item.change_before) : "",
                    change_after: item.change_after ? markup(item.change_after) : "",
                }));
            };
            this.state.dashboardCards = {
                recent: payload?.recent || [],
                popular: payload?.popular || [],
                updated: decorateUpdated(payload?.updated || []),
                newest: payload?.newest || [],
            };
        } catch (error) {
            logger.error("Error loading dashboard cards:", error);
            this.state.dashboardCards = { recent: [], popular: [], updated: [], newest: [] };
        } finally {
            this.state.dashboardLoading = false;
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

        this.orm.call("knowledge.article", "track_article_view", [[articleId]])
            .catch((error) => {
                logger.warn("Error tracking article view:", error);
            });
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
        if (!article) {
            return false;
        }
        if (article.share_public) {
            return true;
        }
        if (!article.shared_user_ids) {
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
            // Open share dialog
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
            await this.loadShareInfo(articleId);
            this.state.showShareDialog = true;
        } catch (error) {
            logger.error("Error showing share dialog:", error);
        }
    }

    async loadShareInfo(articleId) {
        const info = await this.orm.call(
            "knowledge.article",
            "get_share_info",
            [[articleId]]
        );
        this.state.sharePublic = !!info.share_public;
        this.state.shareLink = info.share_link || null;
        this.state.shareDefaultPermission = info.default_permission || "read";
        this.state.shareInvitePermission = info.default_permission || "read";
        this.state.shareMembers = info.members || [];
        this.state.shareCategoryName = info.category_name || null;
        this.state.shareCanManage = !!info.can_manage;
        if (info.shared_user_ids && this.state.currentArticle && this.state.currentArticle.id === articleId) {
            this.state.currentArticle.shared_user_ids = info.shared_user_ids;
            this.state.currentArticle.share_public = !!info.share_public;
            this.state.currentArticle.share_link = info.share_link || null;
            this.state.currentArticle = { ...this.state.currentArticle };
        }
        if (this.state.sharePublic && !this.state.shareLink && this.state.shareCanManage) {
            const result = await this.orm.call(
                "knowledge.article",
                "set_share_public",
                [[articleId], true]
            );
            this.state.sharePublic = !!result.share_public;
            this.state.shareLink = result.share_link || null;
            if (this.state.currentArticle && this.state.currentArticle.id === articleId) {
                this.state.currentArticle.share_public = this.state.sharePublic;
                this.state.currentArticle = { ...this.state.currentArticle };
            }
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
        this.state.sharePublic = false;
        this.state.shareDefaultPermission = "read";
        this.state.shareMembers = [];
        this.state.shareCategoryName = null;
        this.state.shareInviteQuery = "";
        this.state.shareInviteSuggestions = [];
        this.state.shareInviteUserId = null;
        this.state.shareInvitePermission = "read";
        this.state.shareInviteLoading = false;
        this.state.shareCanManage = false;
    }

    async toggleSharePublic() {
        if (!this.state.currentArticle || !this.state.shareCanManage) {
            return;
        }
        try {
            const result = await this.orm.call(
                "knowledge.article",
                "set_share_public",
                [[this.state.currentArticle.id], !this.state.sharePublic]
            );
            this.state.sharePublic = !!result.share_public;
            this.state.shareLink = result.share_link || null;
            if (this.state.currentArticle) {
                this.state.currentArticle.share_public = this.state.sharePublic;
                this.state.currentArticle.share_link = this.state.shareLink;
                this.state.currentArticle = { ...this.state.currentArticle };
            }
        } catch (error) {
            logger.error("Error toggling share public:", error);
            this.showNotification("Unable to update public sharing.", "danger");
        }
    }

    async updateDefaultSharePermission(ev) {
        if (!this.state.currentArticle || !this.state.shareCanManage) {
            return;
        }
        const permission = ev.target.value;
        try {
            await this.orm.call(
                "knowledge.article",
                "set_default_share_permission",
                [[this.state.currentArticle.id], permission]
            );
            this.state.shareDefaultPermission = permission;
        } catch (error) {
            logger.error("Error updating default share permission:", error);
            this.showNotification("Unable to update default access.", "danger");
        }
    }

    onShareInviteInput(ev) {
        const value = ev.target.value;
        this.state.shareInviteQuery = value;
        this.state.shareInviteUserId = null;
        if (this._shareInviteTimer) {
            clearTimeout(this._shareInviteTimer);
        }
        this._shareInviteTimer = setTimeout(() => {
            this.loadShareInviteSuggestions(value, false);
        }, 200);
    }

    onShareInvitePermissionChange(ev) {
        this.state.shareInvitePermission = ev.target.value;
    }

    async onShareInviteFocus() {
        if (this._shareInviteBlurTimer) {
            clearTimeout(this._shareInviteBlurTimer);
        }
        await this.loadShareInviteSuggestions(this.state.shareInviteQuery, true);
    }

    onShareInviteBlur() {
        if (this._shareInviteBlurTimer) {
            clearTimeout(this._shareInviteBlurTimer);
        }
        this._shareInviteBlurTimer = setTimeout(() => {
            this.state.shareInviteSuggestions = [];
        }, 200);
    }

    async loadShareInviteSuggestions(query, force) {
        const term = (query || "").trim();
        if (!force && term.length < 2) {
            this.state.shareInviteSuggestions = [];
            return;
        }
        const domain = force && !term
            ? [["share", "=", false], ["active", "=", true]]
            : ["&", "&", ["share", "=", false], ["active", "=", true], "|", "|", ["name", "ilike", term], ["email", "ilike", term], ["login", "ilike", term]];
        try {
            const users = await this.orm.searchRead(
                "res.users",
                domain,
                ["id", "name", "email", "login"],
                { limit: 8, order: "name asc" }
            );
            this.state.shareInviteSuggestions = (users || []).map(user => ({
                id: user.id,
                name: user.name,
                email: user.email || user.login || "",
            }));
        } catch (error) {
            logger.error("Error loading invite suggestions:", error);
            this.state.shareInviteSuggestions = [];
        }
    }

    selectShareInviteSuggestion(suggestion) {
        if (!suggestion) {
            return;
        }
        this.state.shareInviteQuery = suggestion.email || suggestion.name;
        this.state.shareInviteUserId = suggestion.id;
        this.state.shareInviteSuggestions = [];
    }

    async inviteShareMember() {
        if (!this.state.currentArticle || !this.state.shareCanManage) {
            return;
        }
        const query = (this.state.shareInviteQuery || "").trim();
        const identifier = this.state.shareInviteUserId || query;
        if (!identifier) {
            this.showNotification("Please enter a user email.", "warning");
            return;
        }
        this.state.shareInviteLoading = true;
        try {
            await this.orm.call(
                "knowledge.article",
                "add_share_member",
                [[this.state.currentArticle.id], identifier, this.state.shareInvitePermission]
            );
            this.state.shareInviteQuery = "";
            this.state.shareInviteUserId = null;
            await this.loadShareInfo(this.state.currentArticle.id);
            this.showNotification("User invited successfully.", "success");
        } catch (error) {
            logger.error("Error inviting share member:", error);
            const message = (error && error.data && error.data.arguments && error.data.arguments[0])
                || (error && error.data && error.data.message)
                || (error && error.message)
                || "Unable to invite user.";
            this.showNotification(message, "danger");
        } finally {
            this.state.shareInviteLoading = false;
        }
    }

    async updateShareMemberPermission(memberId, permission) {
        if (!this.state.currentArticle || !this.state.shareCanManage || !memberId) {
            return;
        }
        try {
            await this.orm.call(
                "knowledge.article",
                "update_share_member_permission",
                [[this.state.currentArticle.id], memberId, permission]
            );
            await this.loadShareInfo(this.state.currentArticle.id);
        } catch (error) {
            logger.error("Error updating share member permission:", error);
            this.showNotification("Unable to update access rights.", "danger");
        }
    }

    async removeShareMember(memberId) {
        if (!this.state.currentArticle || !this.state.shareCanManage || !memberId) {
            return;
        }
        try {
            await this.orm.call(
                "knowledge.article",
                "remove_share_member",
                [[this.state.currentArticle.id], memberId]
            );
            await this.loadShareInfo(this.state.currentArticle.id);
            this.showNotification("Access removed.", "success");
        } catch (error) {
            logger.error("Error removing share member:", error);
            this.showNotification("Unable to remove access.", "danger");
        }
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
        // CRITICAL: Don't show notification here - the comment overlay component handles its own validation
        // This method is called from comment_overlay.js after it has already validated the selection
        // If we show notification here, it will appear even when selection is valid
        // The comment overlay component will show notification if needed
        
        // Just ensure comment panel is open and trigger creation
        // The comment overlay will handle all validation and error messages

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

        const header = this.floatingTOCContainer.querySelector('.o_toc_header');
        if (header && !header.querySelector('.o_toc_close')) {
            const closeButton = document.createElement('button');
            closeButton.type = 'button';
            closeButton.className = 'o_toc_close';
            closeButton.setAttribute('title', 'Hide Table of Contents');
            closeButton.setAttribute('aria-label', 'Hide Table of Contents');
            closeButton.innerHTML = '<span class="fa fa-times" aria-hidden="true"></span>';
            header.appendChild(closeButton);
        }

        this._ensureTOCToggleButton();

        // Delegate clicks to reuse smooth scroll behaviour
        this.floatingTOCContainer.onclick = (e) => {
            const closeButton = e.target.closest('.o_toc_close');
            if (closeButton) {
                e.preventDefault();
                this._setTOCHidden(true);
                return;
            }
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
        this._setTOCHidden(this._tocHidden);
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
        this._tocShouldShow = show;
        const shouldShow = show && !this._tocHidden;
        this.floatingTOCContainer.style.display = shouldShow ? 'block' : 'none';
        this._updateTOCToggleButtonVisibility();
    }

    _ensureTOCToggleButton() {
        if (this.tocToggleButton) {
            return;
        }
        const toggleButton = document.createElement('button');
        toggleButton.type = 'button';
        toggleButton.className = 'o_knowledge_toc_toggle';
        toggleButton.setAttribute('title', 'Show Table of Contents');
        toggleButton.setAttribute('aria-label', 'Show Table of Contents');
        toggleButton.innerHTML = '<span class="fa fa-list" aria-hidden="true"></span><span>TOC</span>';
        toggleButton.addEventListener('click', () => {
            this._setTOCHidden(false);
        });
        const host = this.el || document.body;
        host.appendChild(toggleButton);
        this.tocToggleButton = toggleButton;
        this._updateTOCToggleButtonVisibility();
    }

    _setTOCHidden(hidden) {
        this._tocHidden = hidden;
        try {
            window.localStorage.setItem(this._tocHiddenKey, hidden ? "1" : "0");
        } catch (error) {
            // ignore localStorage errors
        }
        if (this.el) {
            this.el.classList.toggle('o_knowledge_toc_hidden', hidden);
            const articleContent = this.el.querySelector('.o_knowledge_article_content');
            if (articleContent) {
                articleContent.classList.toggle('o_knowledge_toc_hidden_content', hidden);
            }
        }
        this._toggleFloatingTOC(this._tocShouldShow);
    }

    _updateTOCToggleButtonVisibility() {
        if (!this.tocToggleButton) return;
        const shouldShow = this._tocHidden && this._floatingTOCHeadings.length > 0;
        this.tocToggleButton.style.display = shouldShow ? 'flex' : 'none';
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

    /**
     * Load highlight.js library dynamically if not already loaded
     * @returns {Promise} Promise that resolves when hljs is loaded
     */
    async _loadHighlightJS() {
        // Check if already loaded
        if (typeof window.hljs !== 'undefined') {
            return Promise.resolve();
        }

        // Check if already loading
        if (this._hljsLoading) {
            return this._hljsLoading;
        }

        // Start loading
        this._hljsLoading = new Promise((resolve, reject) => {
            // Load CSS
            const cssLink = document.createElement('link');
            cssLink.rel = 'stylesheet';
            cssLink.href = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css';
            cssLink.onerror = () => {
                logger.warn('Failed to load highlight.js CSS');
            };
            document.head.appendChild(cssLink);

            // Load JS
            const script = document.createElement('script');
            script.src = 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js';
            script.async = true;
            script.onload = () => {
                // Wait a bit for hljs to initialize
                setTimeout(() => {
                    if (typeof window.hljs !== 'undefined') {
                        logger.log('highlight.js loaded successfully');
                        resolve();
                    } else {
                        logger.warn('highlight.js script loaded but window.hljs not available');
                        resolve(); // Resolve anyway to continue
                    }
                }, 100);
            };
            script.onerror = () => {
                logger.warn('Failed to load highlight.js, will use fallback highlighting');
                resolve(); // Resolve anyway to continue without hljs
            };
            document.head.appendChild(script);
        });

        return this._hljsLoading;
    }

    /**
     * Wait for highlight.js to be loaded
     * @returns {Promise} Promise that resolves when hljs is available
     */
    async _waitForHighlightJS(maxWait = 5000) {
        if (typeof window.hljs !== 'undefined') {
            return Promise.resolve();
        }

        // Try to load it first
        await this._loadHighlightJS();

        // Wait for it to be available
        return new Promise((resolve) => {
            const startTime = Date.now();
            const checkInterval = setInterval(() => {
                if (typeof window.hljs !== 'undefined') {
                    clearInterval(checkInterval);
                    resolve();
                } else if (Date.now() - startTime > maxWait) {
                    clearInterval(checkInterval);
                    logger.warn('highlight.js not loaded after timeout, continuing without it');
                    resolve();
                }
            }, 100);
        });
    }

    /**
     * Initialize code blocks: add syntax highlighting styles and copy buttons
     */
    async _initializeCodeBlocks() {
        if (!this.contentRef || !this.contentRef.el) {
            return;
        }

        const contentElement = this.contentRef.el;

        // Wait for highlight.js to be loaded
        await this._waitForHighlightJS();

        // Find all code blocks - Odoo editor typically uses <pre><code> structure
        // or divs with specific classes for code blocks (e.g., .o-knowledge-quick-reply)
        // Use more specific selector to avoid duplicates
        const allCodeBlocks = contentElement.querySelectorAll('pre, .o-knowledge-quick-reply, [data-code-block]');
        
        // Also find code elements that might not be inside pre
        const standaloneCode = contentElement.querySelectorAll('code.hljs, .hljs:not(pre):not(.o-knowledge-quick-reply)');
        
        // Combine and deduplicate
        const codeBlocksSet = new Set();
        allCodeBlocks.forEach(block => codeBlocksSet.add(block));
        standaloneCode.forEach(block => {
            // Only add if not already in a pre container
            if (!block.closest('pre') && !block.classList.contains('o-knowledge-quick-reply')) {
                codeBlocksSet.add(block);
            }
        });
        const codeBlocks = Array.from(codeBlocksSet);
        
        logger.log('Initializing code blocks', { 
            count: codeBlocks.length,
            codeBlocksInfo: Array.from(codeBlocks).map(block => ({
                tagName: block.tagName,
                className: block.className,
                hasBrTags: (block.innerHTML || '').includes('<br'),
                textLength: (block.textContent || block.innerText || '').length,
                htmlLength: (block.innerHTML || '').length,
                innerHTMLPreview: (block.innerHTML || '').substring(0, 200)
            }))
        });
        
        codeBlocks.forEach((codeBlock) => {
            // Get the container (pre, code, or div element itself)
            let container = codeBlock;
            if (codeBlock.tagName === 'CODE' && codeBlock.parentElement && codeBlock.parentElement.tagName === 'PRE') {
                container = codeBlock.parentElement;
            }
            // Handle .o-knowledge-quick-reply divs (Odoo editor code blocks)
            else if (codeBlock.classList && codeBlock.classList.contains('o-knowledge-quick-reply')) {
                container = codeBlock;
            }

            // Skip if already initialized (has copy button)
            if (container.dataset.hasCopyButton === '1') {
                return;
            }

            // Mark as initialized
            container.dataset.hasCopyButton = '1';

            // Ensure code block has proper styling
            // Handle both <pre> and <div class="o-knowledge-quick-reply">
            if (container.tagName === 'PRE' || (container.classList && container.classList.contains('o-knowledge-quick-reply'))) {
                container.style.position = 'relative';
                container.style.backgroundColor = '#f8f9fa';
                container.style.border = '1px solid #dee2e6';
                container.style.borderRadius = '6px';
                container.style.padding = '16px';
                container.style.margin = '16px 0';
                // Match edit mode: preserve formatting exactly, show scrollbar for long lines
                // CRITICAL: preserve all whitespace, line breaks, and indentation
                container.style.whiteSpace = 'pre';
                container.style.overflowX = 'auto';
                container.style.overflowY = 'visible';
                container.style.wordWrap = 'normal';
                container.style.wordBreak = 'normal';
                container.style.maxWidth = '100%';
                container.style.width = '100%';
                container.style.boxSizing = 'border-box';
                container.style.fontFamily = "'Courier New', 'Consolas', 'Monaco', monospace";
                container.style.fontSize = '14px';
                container.style.lineHeight = '1.5'; // Match edit mode line height
                container.style.tabSize = '4'; // Match edit mode tab size
                container.style.MozTabSize = '4'; // Firefox
                container.style.OTabSize = '4'; // Opera
                container.style.textAlign = 'left';
                container.style.unicodeBidi = 'embed';
                // Ensure container doesn't wrap its children
                container.style.display = 'block';
            }
                
            // For .o-knowledge-quick-reply, ensure content preserves line breaks and indentation
            if (container.classList && container.classList.contains('o-knowledge-quick-reply')) {
                // CRITICAL: Normalize br tags to newlines IMMEDIATELY
                // This must happen BEFORE styling and highlighting
                const htmlContent = container.innerHTML || '';
                const textContent = container.textContent || container.innerText || '';
                const hasLineBreaks = textContent.includes('\n') || textContent.includes('\r\n');
                const hasBrTags = htmlContent.includes('<br') || htmlContent.includes('<BR');
                
                // CRITICAL: ALWAYS normalize br tags to newlines if they exist
                // This must happen BEFORE any styling or highlighting to preserve line breaks
                if (hasBrTags) {
                    // Method 1: Direct DOM manipulation - replace ALL br elements with text nodes (most reliable)
                    // Use querySelectorAll which works recursively to find ALL br tags
                    const brElements = container.querySelectorAll('br, BR');
                    if (brElements.length > 0) {
                        // Replace each br element with a text node containing newline
                        brElements.forEach((br) => {
                            const newlineNode = document.createTextNode('\n');
                            if (br.parentNode) {
                                br.parentNode.replaceChild(newlineNode, br);
                            }
                        });
                        
                        // Get text after DOM manipulation
                        const normalizedText = container.textContent || container.innerText || '';
                        
                        // Verify newlines are present
                        if (normalizedText.includes('\n') || normalizedText.includes('\r\n')) {
                            logger.log('Normalized .o-knowledge-quick-reply: replaced br elements with newlines (DOM method)', {
                                brElementsReplaced: brElements.length,
                                originalTextLength: textContent.length,
                                normalizedTextLength: normalizedText.length,
                                hasNewlinesNow: true,
                                newlineCount: (normalizedText.match(/\n/g) || []).length
                            });
                        } else {
                            // Fallback: String replacement method
                            logger.warn('DOM method did not preserve newlines, using string replacement fallback');
                            let processedHTML = htmlContent;
                            // Replace all br variants with newline character - comprehensive patterns
                            processedHTML = processedHTML.replace(/<br\s*\/?>/gi, '\n');
                            processedHTML = processedHTML.replace(/<BR\s*\/?>/gi, '\n');
                            processedHTML = processedHTML.replace(/<br\s+[^>]*\/?>/gi, '\n');
                            processedHTML = processedHTML.replace(/<BR\s+[^>]*\/?>/gi, '\n');
                            processedHTML = processedHTML.replace(/<br[^>]*>/gi, '\n');
                            processedHTML = processedHTML.replace(/<BR[^>]*>/gi, '\n');
                            
                            // Use DOM manipulation to ensure conversion
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = processedHTML;
                            const allBrTags = tempDiv.querySelectorAll('br, BR');
                            allBrTags.forEach(br => {
                                const newlineNode = document.createTextNode('\n');
                                if (br.parentNode) {
                                    br.parentNode.replaceChild(newlineNode, br);
                                }
                            });
                            
                            // Get normalized text with newlines
                            const normalizedText = tempDiv.textContent || tempDiv.innerText || textContent;
                            
                            // Set as plain text with newlines preserved
                            container.textContent = normalizedText;
                            
                            logger.log('Normalized .o-knowledge-quick-reply: converted br tags to newlines (string replacement method)', {
                                originalTextLength: textContent.length,
                                normalizedTextLength: normalizedText.length,
                                hasNewlinesNow: normalizedText.includes('\n'),
                                brTagsFound: htmlContent.match(/<br[^>]*>/gi)?.length || 0
                            });
                        }
                    } else {
                        // No br elements found but HTML has br tags - use string replacement
                        let processedHTML = htmlContent;
                        processedHTML = processedHTML.replace(/<br[^>]*>/gi, '\n');
                        processedHTML = processedHTML.replace(/<BR[^>]*>/gi, '\n');
                        
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = processedHTML;
                        const normalizedText = tempDiv.textContent || tempDiv.innerText || textContent;
                        container.textContent = normalizedText;
                        
                        logger.log('Normalized .o-knowledge-quick-reply: converted br tags via string replacement (no DOM br elements)', {
                            hasNewlinesNow: normalizedText.includes('\n')
                        });
                    }
                }
                
                // CRITICAL: Ensure all whitespace, line breaks are preserved
                // Match edit mode exactly: use pre (no wrapping, horizontal scrollbar)
                container.style.whiteSpace = 'pre'; // Preserve ALL whitespace and line breaks, no wrapping
                container.style.overflowX = 'auto';
                container.style.overflowY = 'visible';
                container.style.wordWrap = 'normal'; // Don't wrap words (match edit mode)
                container.style.wordBreak = 'normal'; // Don't break words (match edit mode)
                container.style.tabSize = '4';
                container.style.MozTabSize = '4';
                container.style.OTabSize = '4';
                container.style.lineHeight = '1.5';
                container.style.fontSize = '14px';
                container.style.fontFamily = "'Courier New', 'Consolas', 'Monaco', monospace";
                container.style.textAlign = 'left';
                container.style.unicodeBidi = 'embed';
                
                // Ensure all child elements also preserve whitespace
                const allChildren = container.querySelectorAll('*');
                allChildren.forEach((child) => {
                    // Skip buttons and absolute positioned elements
                    if (child.tagName === 'BUTTON' || child.closest('[style*="position: absolute"]')) {
                        return;
                    }
                    // Force preserve whitespace for all code content elements
                    child.style.whiteSpace = 'pre'; // Preserve ALL whitespace and line breaks
                    child.style.tabSize = '4';
                    child.style.MozTabSize = '4';
                    child.style.OTabSize = '4';
                });
            }
            
            // Ensure all child elements also preserve whitespace (for pre containers)
            if (container.tagName === 'PRE') {
                const allChildren = container.querySelectorAll('*');
                allChildren.forEach((child) => {
                    if (child.tagName !== 'BUTTON' && !child.closest('[style*="position: absolute"]')) {
                        // Force preserve whitespace for code content
                        if (child.classList.contains('hljs') || child.tagName === 'CODE') {
                            child.style.whiteSpace = 'pre';
                            child.style.tabSize = '4';
                            child.style.MozTabSize = '4';
                            child.style.OTabSize = '4';
                        }
                    }
                });
            }

            // Get the actual code element
            let codeElement;
            if (container.tagName === 'PRE') {
                codeElement = container.querySelector('code') || container;
                // CRITICAL: Normalize br tags in code element (may be inside <code> within <pre>)
                if (codeElement) {
                    const codeHtml = codeElement.innerHTML || '';
                    const codeText = codeElement.textContent || codeElement.innerText || '';
                    const codeHasBrTags = codeHtml.includes('<br') || codeHtml.includes('<BR');
                    
                    // ALWAYS normalize if br tags exist
                    if (codeHasBrTags) {
                        // Method 1: Direct DOM manipulation
                        const brElements = codeElement.querySelectorAll('br, BR');
                        if (brElements.length > 0) {
                            brElements.forEach((br) => {
                                const newlineNode = document.createTextNode('\n');
                                if (br.parentNode) {
                                    br.parentNode.replaceChild(newlineNode, br);
                                }
                            });
                            const normalizedText = codeElement.textContent || codeElement.innerText || '';
                            
                            logger.log('Normalized code element in PRE: replaced br elements with newlines (DOM method)', {
                                brElementsReplaced: brElements.length,
                                hasNewlinesNow: normalizedText.includes('\n')
                            });
                        } else {
                            // Method 2: String replacement fallback
                            let processedHTML = codeHtml.replace(/<br[^>]*>/gi, '\n');
                            const tempDiv = document.createElement('div');
                            tempDiv.innerHTML = processedHTML;
                            const allBrTags = tempDiv.querySelectorAll('br, BR');
                            allBrTags.forEach(br => {
                                const newlineNode = document.createTextNode('\n');
                                if (br.parentNode) {
                                    br.parentNode.replaceChild(newlineNode, br);
                                }
                            });
                            const normalizedText = tempDiv.textContent || tempDiv.innerText || codeText;
                            codeElement.textContent = normalizedText;
                            
                            logger.log('Normalized code element in PRE: converted br tags to newlines (string replacement)', {
                                hasNewlinesNow: normalizedText.includes('\n')
                            });
                        }
                    }
                }
            } else if (container.classList && container.classList.contains('o-knowledge-quick-reply')) {
                // For .o-knowledge-quick-reply divs, use the container itself as code element
                // Normalization already done above
                codeElement = container;
            } else {
                codeElement = codeBlock;
                // Also normalize br tags in standalone code elements
                if (codeElement) {
                    const codeHtml = codeElement.innerHTML || '';
                    const codeHasBrTags = codeHtml.includes('<br') || codeHtml.includes('<BR');
                    if (codeHasBrTags) {
                        const brElements = codeElement.querySelectorAll('br, BR');
                        if (brElements.length > 0) {
                            brElements.forEach((br) => {
                                const newlineNode = document.createTextNode('\n');
                                if (br.parentNode) {
                                    br.parentNode.replaceChild(newlineNode, br);
                                }
                            });
                            logger.log('Normalized standalone code element: replaced br elements with newlines');
                        }
                    }
                }
            }

            // Ensure code element has hljs class for styling
            if (codeElement && !codeElement.classList.contains('hljs')) {
                codeElement.classList.add('hljs');
            }
            
            // Apply styles to code element to match edit mode
            // CRITICAL: preserve all whitespace, line breaks, and indentation
            if (codeElement) {
                codeElement.style.whiteSpace = 'pre';
                codeElement.style.overflowX = 'auto';
                codeElement.style.overflowY = 'visible';
                codeElement.style.wordWrap = 'normal';
                codeElement.style.wordBreak = 'normal';
                codeElement.style.display = 'block';
                codeElement.style.margin = '0';
                codeElement.style.padding = '0';
                codeElement.style.backgroundColor = 'transparent';
                // Match edit mode: tab size and line height for proper indentation
                codeElement.style.tabSize = '4';
                codeElement.style.MozTabSize = '4'; // Firefox
                codeElement.style.OTabSize = '4'; // Opera
                codeElement.style.lineHeight = '1.5';
                codeElement.style.fontSize = '14px';
                codeElement.style.fontFamily = "'Courier New', 'Consolas', 'Monaco', monospace";
                codeElement.style.textAlign = 'left';
                codeElement.style.unicodeBidi = 'embed';
                
                // Ensure all child spans (from syntax highlighting) also preserve whitespace
                const highlightSpans = codeElement.querySelectorAll('span');
                highlightSpans.forEach((span) => {
                    span.style.whiteSpace = 'pre';
                });
            }

            // Try to re-highlight using highlight.js if available
            if (typeof window.hljs !== 'undefined' && codeElement) {
                try {
                    // Detect language from class (language-js, language-javascript, etc.)
                    let detectedLanguage = null;
                    const classList = codeElement.classList;
                    for (let cls of classList) {
                        if (cls.startsWith('language-')) {
                            detectedLanguage = cls.replace('language-', '');
                            break;
                        }
                        if (cls.startsWith('hljs-')) {
                            // Extract language from hljs-lang or hljs language
                            const match = cls.match(/^hljs-([a-z]+)$/);
                            if (match) {
                                detectedLanguage = match[1];
                                break;
                            }
                        }
                    }
                    
                    // CRITICAL: Preserve line breaks and formatting from editor
                    // Get original HTML first to check structure
                    const originalHTML = codeElement.innerHTML || '';
                    const originalTextContent = codeElement.textContent || codeElement.innerText || '';
                    
                    // Check if HTML contains br tags or newlines
                    const hasBrTags = originalHTML.includes('<br') || originalHTML.includes('<BR');
                    const hasNewlines = originalTextContent.includes('\n') || originalTextContent.includes('\r\n');
                    
                    logger.log('Code block content analysis:', {
                        hasBrTags,
                        hasNewlines,
                        textLength: originalTextContent.length,
                        htmlLength: originalHTML.length,
                        firstChars: originalTextContent.substring(0, 200)
                    });
                    
                    // If no language detected, try to detect from content
                    if (!detectedLanguage) {
                        // More comprehensive language detection
                        if (originalTextContent.includes('@odoo-module') || originalTextContent.includes('import {') || 
                            originalTextContent.includes('export') || originalTextContent.includes('function') ||
                            originalTextContent.includes('const {') || originalTextContent.includes('class ') ||
                            originalTextContent.includes('extends')) {
                            detectedLanguage = 'javascript';
                        } else if (originalTextContent.includes('def ') || originalTextContent.match(/^import\s+\w+/m)) {
                            detectedLanguage = 'python';
                        } else if (originalTextContent.includes('<?xml') || originalTextContent.includes('<!DOCTYPE')) {
                            detectedLanguage = 'xml';
                        } else if (originalTextContent.includes('SELECT') || originalTextContent.includes('FROM')) {
                            detectedLanguage = 'sql';
                        }
                    }
                    
                    // SECURITY & FORMATTING: Normalize code content before highlighting
                    // CRITICAL: Convert br tags to newlines and ensure plain text
                    // This must be done ALWAYS if we have br tags, not just when hasHtmlChildren
                    let textToHighlight = originalTextContent;
                    
                    // CRITICAL: If HTML has br tags but textContent doesn't have newlines,
                    // we MUST convert br tags to newlines to preserve line breaks
                    if (hasBrTags && !hasNewlines) {
                        // Convert br tags to newlines by processing HTML
                        // Use a more robust method to preserve line breaks
                        // Method 1: Replace br tags directly in HTML string
                        let processedHTML = originalHTML;
                        // Replace all br variants with newline character - more comprehensive patterns
                        processedHTML = processedHTML.replace(/<br\s*\/?>/gi, '\n');
                        processedHTML = processedHTML.replace(/<BR\s*\/?>/gi, '\n');
                        processedHTML = processedHTML.replace(/<br\s+[^>]*\/?>/gi, '\n');
                        processedHTML = processedHTML.replace(/<BR\s+[^>]*\/?>/gi, '\n');
                        
                        // Method 2: Use DOM manipulation to preserve structure better
                        const tempDiv = document.createElement('div');
                        tempDiv.innerHTML = processedHTML;
                        
                        // Method 3: Also manually process br tags in DOM
                        const allBrTags = tempDiv.querySelectorAll('br, BR');
                        allBrTags.forEach(br => {
                            // Replace br with text node containing newline
                            const newlineNode = document.createTextNode('\n');
                            br.parentNode.replaceChild(newlineNode, br);
                        });
                        
                        // Get text content which should now have newlines
                        textToHighlight = tempDiv.textContent || tempDiv.innerText || originalTextContent;
                        
                        // Method 4: Fallback - manually process if still no newlines
                        if (!textToHighlight.includes('\n')) {
                            // Directly replace br tags in HTML string more aggressively
                            processedHTML = originalHTML.replace(/<br[^>]*>/gi, '\n');
                            tempDiv.innerHTML = processedHTML;
                            textToHighlight = tempDiv.textContent || tempDiv.innerText || originalTextContent;
                        }
                        
                        logger.log('Converted br tags to newlines', {
                            originalTextLength: originalTextContent.length,
                            convertedTextLength: textToHighlight.length,
                            hasNewlinesNow: textToHighlight.includes('\n'),
                            brTagsFound: originalHTML.match(/<br[^>]*>/gi)?.length || 0,
                            originalFirstChars: originalTextContent.substring(0, 100),
                            convertedFirstChars: textToHighlight.substring(0, 150)
                        });
                    }
                    
                    // SECURITY: Always normalize to plain text before highlighting
                    // Check if element has HTML children (spans, etc. from previous highlighting)
                    // OR if we have br tags that need to be converted
                    const hasHtmlChildren = codeElement.querySelector('span, div, p') !== null;
                    if ((hasHtmlChildren || hasBrTags) && textToHighlight) {
                        // Clear and set as plain text (with newlines preserved) to prevent security warning
                        codeElement.textContent = textToHighlight;
                        
                        logger.log('Code element normalized for highlighting', {
                            hadHtmlChildren: hasHtmlChildren,
                            hadBrTags: hasBrTags,
                            finalTextLength: textToHighlight.length,
                            hasNewlines: textToHighlight.includes('\n'),
                            firstChars: textToHighlight.substring(0, 200)
                        });
                    }
                    
                    // Add language class if detected
                    if (detectedLanguage) {
                        codeElement.classList.add(`language-${detectedLanguage}`);
                        // Also add hljs class if not present
                        if (!codeElement.classList.contains('hljs')) {
                            codeElement.classList.add('hljs');
                        }
                    }
                    
                    // Re-highlight the code block
                    // highlight.js will safely escape HTML and apply syntax highlighting
                    if (detectedLanguage) {
                        window.hljs.highlightElement(codeElement);
                        logger.log('Code block re-highlighted with hljs', {
                            language: detectedLanguage,
                            element: codeElement.tagName
                        });
                    } else {
                        // Try highlighting without language (auto-detect)
                        window.hljs.highlightElement(codeElement);
                        logger.log('Code block re-highlighted with hljs (auto-detect)');
                    }
                    
                    // CRITICAL: After highlighting, verify and preserve line breaks
                    // highlight.js might process content, so ensure newlines are still present
                    // Use setTimeout to check after highlight.js finishes processing
                    setTimeout(() => {
                        const afterHighlightText = codeElement.textContent || codeElement.innerText || '';
                        const afterHighlightHasNewlines = afterHighlightText.includes('\n') || afterHighlightText.includes('\r\n');
                        const afterHighlightHTML = codeElement.innerHTML || '';
                        const stillHasBrTags = afterHighlightHTML.includes('<br') || afterHighlightHTML.includes('<BR');
                        
                        // If newlines are missing but we had them before, or br tags still exist, restore them
                        if ((textToHighlight && textToHighlight.includes('\n') && !afterHighlightHasNewlines) || stillHasBrTags) {
                            // If br tags still exist, normalize them again
                            if (stillHasBrTags) {
                                const brElements = codeElement.querySelectorAll('br, BR');
                                if (brElements.length > 0) {
                                    brElements.forEach((br) => {
                                        const newlineNode = document.createTextNode('\n');
                                        if (br.parentNode) {
                                            br.parentNode.replaceChild(newlineNode, br);
                                        }
                                    });
                                    logger.log('Normalized br tags after highlight.js processing', {
                                        brElementsReplaced: brElements.length
                                    });
                                }
                            } else if (textToHighlight && textToHighlight.includes('\n')) {
                                // Restore normalized text with newlines
                                codeElement.textContent = textToHighlight;
                                // Re-highlight with the correct text
                                if (detectedLanguage) {
                                    window.hljs.highlightElement(codeElement);
                                } else {
                                    window.hljs.highlightElement(codeElement);
                                }
                                
                                logger.log('Restored newlines after highlight.js processing', {
                                    hasNewlinesRestored: codeElement.textContent.includes('\n')
                                });
                            }
                            
                            // Final verification
                            const finalText = codeElement.textContent || codeElement.innerText || '';
                            const finalHasNewlines = finalText.includes('\n') || finalText.includes('\r\n');
                            logger.log('Final code block verification', {
                                hasNewlines: finalHasNewlines,
                                textLength: finalText.length,
                                firstChars: finalText.substring(0, 200)
                            });
                        }
                    }, 100);
                } catch (error) {
                    logger.warn('Failed to re-highlight with hljs:', error);
                    // Fallback to manual highlighting
                    if (codeElement.tagName === 'CODE') {
                        this._applyManualSyntaxHighlighting(codeElement);
                    }
                }
            } else {
                // highlight.js not available, use manual highlighting
                if (codeElement && codeElement.tagName === 'CODE') {
                    const codeText = codeElement.textContent || codeElement.innerText;
                    // Only apply if it looks like code (contains typical code characters)
                    if (codeText && (codeText.includes('{') || codeText.includes('function') || 
                        codeText.includes('=') || codeText.includes('()') || codeText.includes('import'))) {
                        // Apply manual syntax highlighting
                        this._applyManualSyntaxHighlighting(codeElement);
                    }
                }
            }

            // Create copy button wrapper - position absolutely in top right
            const buttonWrapper = document.createElement('div');
            buttonWrapper.style.position = 'absolute';
            buttonWrapper.style.top = '8px';
            buttonWrapper.style.right = '8px';
            buttonWrapper.style.zIndex = '100';
            buttonWrapper.style.pointerEvents = 'auto';

            // Create copy button
            const copyButton = document.createElement('button');
            copyButton.type = 'button';
            copyButton.className = 'btn btn-secondary btn-sm';
            copyButton.innerHTML = '<i class="fa fa-copy"></i> Copy';
            copyButton.style.fontSize = '12px';
            copyButton.style.padding = '4px 12px';
            copyButton.style.backgroundColor = '#ffffff';
            copyButton.style.border = '1px solid #dee2e6';
            copyButton.style.borderRadius = '4px';
            copyButton.style.cursor = 'pointer';
            copyButton.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
            copyButton.style.transition = 'all 0.2s ease';

            // Hover effect
            copyButton.addEventListener('mouseenter', () => {
                copyButton.style.backgroundColor = '#e9ecef';
                copyButton.style.transform = 'scale(1.05)';
            });
            copyButton.addEventListener('mouseleave', () => {
                copyButton.style.backgroundColor = '#ffffff';
                copyButton.style.transform = 'scale(1)';
            });

            // Copy functionality
            copyButton.addEventListener('click', async (e) => {
                e.stopPropagation();
                e.preventDefault();

                // Get text to copy
                const codeNode = container.querySelector('code') || codeBlock || container;
                // Clone to strip out buttons/icons that live in the container
                const clone = codeNode.cloneNode(true);
                clone.querySelectorAll('button, i, .o_knowledge_copy_button_wrapper').forEach((n) => n.remove());
                const textToCopy = clone.textContent || codeNode.textContent || '';

                try {
                    // Try Clipboard API first
                    if (navigator.clipboard && navigator.clipboard.writeText) {
                        await navigator.clipboard.writeText(textToCopy);
                    } else {
                        // Fallback method
                        const textArea = document.createElement('textarea');
                        textArea.value = textToCopy;
                        textArea.style.position = 'fixed';
                        textArea.style.left = '-999999px';
                        document.body.appendChild(textArea);
                        textArea.select();
                        document.execCommand('copy');
                        document.body.removeChild(textArea);
                    }

                    // Visual feedback
                    const originalText = copyButton.innerHTML;
                    copyButton.innerHTML = '<i class="fa fa-check"></i> Copied!';
                    copyButton.style.backgroundColor = '#28a745';
                    copyButton.style.color = '#ffffff';
                    
                    setTimeout(() => {
                        copyButton.innerHTML = originalText;
                        copyButton.style.backgroundColor = '#ffffff';
                        copyButton.style.color = '';
                    }, 2000);

                    logger.log('Code copied to clipboard', { textLength: textToCopy.length });
                } catch (error) {
                    logger.error('Failed to copy code:', error);
                    copyButton.innerHTML = '<i class="fa fa-exclamation"></i> Error';
                    setTimeout(() => {
                        copyButton.innerHTML = '<i class="fa fa-copy"></i> Copy';
                    }, 2000);
                }
            });

            buttonWrapper.appendChild(copyButton);
            
            // Insert button into container
            if (container.style.position !== 'relative') {
                container.style.position = 'relative';
            }
            container.appendChild(buttonWrapper);
        }); // End of codeBlocks.forEach

        logger.log('Code blocks initialized', { count: codeBlocks.length, hljsAvailable: typeof window.hljs !== 'undefined' });
        
        // Try to trigger highlight.js globally if available (for code blocks that may be added later)
        if (typeof window.hljs !== 'undefined') {
            try {
                // Wait a bit for DOM to be fully ready
                setTimeout(() => {
                    const allCodeBlocks = contentElement.querySelectorAll('pre code, code.hljs, .hljs');
                    allCodeBlocks.forEach((block) => {
                        try {
                            // Only highlight if not already highlighted
                            if (!block.classList.contains('hljs-processed')) {
                                window.hljs.highlightElement(block);
                                block.classList.add('hljs-processed');
                            }
                        } catch (e) {
                            // Ignore errors for individual blocks
                            logger.warn('Failed to highlight individual block:', e);
                        }
                    });
                    logger.log('Global hljs.highlightAll triggered', { count: allCodeBlocks.length });
                }, 200);
            } catch (error) {
                logger.warn('Failed to trigger global hljs highlighting:', error);
            }
        }
    }

    /**
     * Apply manual syntax highlighting to code block (fallback if no highlighting library)
     * @param {HTMLElement} codeElement - Code element to highlight
     */
    _applyManualSyntaxHighlighting(codeElement) {
        if (!codeElement || codeElement.tagName !== 'CODE') {
            return;
        }

        const codeText = codeElement.textContent || codeElement.innerText;
        if (!codeText) return;

        // Simple regex-based syntax highlighting for JavaScript
        let highlightedHTML = codeText
            // Strings (single and double quotes)
            .replace(/(["'])(?:(?=(\\?))\2.)*?\1/g, '<span class="hljs-string">$&</span>')
            // Comments (single line)
            .replace(/(\/\/.*$)/gm, '<span class="hljs-comment">$1</span>')
            // Comments (multi-line)
            .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="hljs-comment">$1</span>')
            // Keywords
            .replace(/\b(const|let|var|function|async|await|import|export|from|return|if|else|for|while|class|extends|new|this|typeof|instanceof)\b/g, '<span class="hljs-keyword">$1</span>')
            // Numbers
            .replace(/\b(\d+\.?\d*)\b/g, '<span class="hljs-number">$1</span>')
            // Functions
            .replace(/\b([a-zA-Z_$][a-zA-Z0-9_$]*)\s*(?=\()/g, '<span class="hljs-function">$1</span>');

        // Only update if we actually made changes
        if (highlightedHTML !== codeText) {
            codeElement.innerHTML = highlightedHTML;
            logger.log('Manual syntax highlighting applied');
        }
    }
}

KnowledgeDocumentController.template = "knowledge_onthisday_oca.KnowledgeDocumentView";

// Register as client action
registry.category("actions").add("knowledge_document_view", KnowledgeDocumentController);
