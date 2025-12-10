/** @odoo-module **/

import { TextSelectionHandler } from './text_selection';
import { logger } from '../utils/logger';

/**
 * Comment Manager
 * 
 * Manages comments for knowledge articles including:
 * - Loading comments from server
 * - Creating new comments
 * - Updating/resolving comments
 * - Highlighting text selections
 */
export class CommentManager {
    constructor(orm, articleId, contentElement, onHighlightClickCallback = null) {
        this.orm = orm;
        this.articleId = articleId;
        this.contentElement = contentElement;
        this.textSelectionHandler = new TextSelectionHandler(contentElement);
        this.comments = [];
        this.highlights = new Map(); // Map<commentId, highlightElement>
        this.onHighlightClickCallback = onHighlightClickCallback; // Callback when highlight is clicked
        this._isRenderingHighlights = false; // Flag to prevent infinite loop
        this._highlightObserver = null; // MutationObserver to watch for removed highlights
        this._lastReRenderTime = 0; // Timestamp of last re-render to prevent too frequent re-renders
    }

    /**
     * Load comments for current article
     * @returns {Promise<Array>} Array of comment objects
     */
    async loadComments() {
        if (!this.articleId) {
            return [];
        }

        try {
            const comments = await this.orm.searchRead(
                'knowledge.article.comment',
                [['article_id', '=', this.articleId]],
                [
                    'id', 'selected_text', 'body', 'author_id', 'create_date',
                    'start_offset', 'end_offset', 'element_selector',
                    'resolved', 'resolved_by', 'resolved_date',
                    'parent_id', 'child_ids', 'mentioned_user_ids',
                    'highlight_color'
                ],
                {
                    order: 'create_date asc'
                }
            );

            // Load author images (avatar) for each comment
            // author_id is in format [id, name] - extract IDs
            try {
                const authorIds = [...new Set(comments
                    .map(c => c.author_id && Array.isArray(c.author_id) && c.author_id[0])
                    .filter(Boolean)
                )];
                
                if (authorIds.length > 0 && authorIds.every(id => typeof id === 'number' && !isNaN(id))) {
                    try {
                        // Only proceed if all IDs are valid numbers
                        const authors = await this.orm.searchRead(
                            'res.users',
                            [['id', 'in', authorIds]],
                            ['id', 'image_128', 'image_small']
                        );
                        
                        // Create a map for quick lookup
                        const authorMap = new Map();
                        if (authors && Array.isArray(authors)) {
                            authors.forEach(author => {
                                if (author && author.id) {
                                    authorMap.set(author.id, {
                                        image_128: author.image_128,
                                        image_small: author.image_small
                                    });
                                }
                            });
                        }
                        
                        // Attach author images to comments
                        comments.forEach(comment => {
                            if (comment.author_id && Array.isArray(comment.author_id) && comment.author_id[0]) {
                                const authorInfo = authorMap.get(comment.author_id[0]);
                                if (authorInfo) {
                                    comment.author_image = authorInfo.image_128 || authorInfo.image_small;
                                }
                            }
                        });
                    } catch (authorError) {
                        // If loading author images fails, log but don't fail the entire comment load
                        // Only log if it's not a permission error or empty result
                        const errorMessage = authorError?.message || String(authorError || '');
                        if (!errorMessage.includes('Access Denied') && !errorMessage.includes('permission')) {
                            logger.warn('Error loading author images (non-critical):', {
                                error: authorError,
                                authorIds: authorIds,
                                errorMessage: errorMessage
                            });
                        }
                        // Continue without author images - comments will still load
                    }
                }
            } catch (authorLoadError) {
                // If author ID extraction fails, log but don't fail the entire comment load
                logger.warn('Error extracting author IDs (non-critical):', authorLoadError);
                // Continue without author images - comments will still load
            }

            this.comments = comments;
            
            // Render highlights for unresolved comments only
            // This will automatically remove highlights for resolved comments
            // Use requestAnimationFrame to ensure DOM is ready before rendering
            await new Promise(resolve => {
                requestAnimationFrame(async () => {
                    requestAnimationFrame(async () => {
                        try {
                            await this.renderHighlights();
                            logger.log('Highlights rendered after loading comments', {
                                unresolvedCount: comments.filter(c => !c.resolved).length,
                                resolvedCount: comments.filter(c => c.resolved).length,
                                highlightsCount: this.highlights.size
                            });
                            
                            // Start watching for removed highlights after initial render
                            this.startWatchingHighlights();
                        } catch (highlightError) {
                            logger.warn('Error rendering highlights (non-critical):', highlightError);
                            // Continue even if highlight rendering fails
                        }
                        resolve();
                    });
                });
            });

            return comments;
        } catch (error) {
            logger.error('Error loading comments:', error);
            // Log detailed error information
            if (error.data && error.data.message) {
                logger.error('RPC Error details:', error.data.message);
            }
            if (error.message) {
                logger.error('Error message:', error.message);
            }
            // Return empty array instead of throwing - this prevents UI from breaking
            this.comments = [];
            return [];
        }
    }

    /**
     * Create a new comment from text selection
     * @param {Object} selectionInfo - Selection info from TextSelectionHandler
     * @param {string} commentBody - Comment body (HTML)
     * @returns {Promise<Object>} Created comment object
     */
    async createComment(selectionInfo, commentBody) {
        if (!this.articleId || !selectionInfo || !commentBody.trim()) {
            throw new Error('Missing required parameters for creating comment');
        }

        try {
            // Validate offsets - ensure end is at least equal to start
            if (selectionInfo.endOffset < selectionInfo.startOffset) {
                throw new Error('Invalid text selection: end offset must be greater than or equal to start offset');
            }
            
            // If offsets are equal, try to calculate proper end offset from selected text
            if (selectionInfo.endOffset === selectionInfo.startOffset && selectionInfo.text) {
                // Use text length to calculate proper end offset
                selectionInfo.endOffset = selectionInfo.startOffset + selectionInfo.text.length;
            }

            // Convert plain text body to HTML format
            const htmlBody = this.convertToHtml(commentBody.trim());

            const commentData = {
                article_id: this.articleId,
                selected_text: selectionInfo.text || '',
                body: htmlBody,
                start_offset: selectionInfo.startOffset,
                end_offset: selectionInfo.endOffset,
                element_selector: selectionInfo.elementSelector || '',
                highlight_color: '#ffeb3b', // Default yellow
            };

            // Log comment data before creating
            logger.log('Creating comment with data:', {
                article_id: commentData.article_id,
                selected_text: commentData.selected_text,
                selected_text_length: commentData.selected_text.length,
                start_offset: commentData.start_offset,
                end_offset: commentData.end_offset,
                offsets_delta: commentData.end_offset - commentData.start_offset,
                body_length: commentData.body.length
            });

            // Don't send mentioned_user_ids - backend will extract them automatically in create() method

            const commentId = await this.orm.create(
                'knowledge.article.comment',
                [commentData]
            );

            // Reload comments to get the new one
            await this.loadComments();

            return this.comments.find(c => c.id === commentId);
        } catch (error) {
            logger.error('Error creating comment in CommentManager:', error);
            
            // Extract and format error message
            let errorMessage = 'เกิดข้อผิดพลาดในการสร้าง comment';
            if (error && error.message) {
                errorMessage = error.message;
            } else if (error && error.data && error.data.message) {
                errorMessage = error.data.message;
            } else if (error && error.data && error.data.debug) {
                errorMessage = error.data.debug;
            }
            
            // Log detailed error information
            logger.error('Comment creation failed:', {
                error,
                articleId: this.articleId,
                selectionInfo,
                commentBodyLength: commentBody ? commentBody.length : 0,
                commentData: {
                    article_id: this.articleId,
                    selected_text: selectionInfo ? selectionInfo.text : null,
                    start_offset: selectionInfo ? selectionInfo.startOffset : null,
                    end_offset: selectionInfo ? selectionInfo.endOffset : null,
                }
            });
            
            throw error;
        }
    }

    /**
     * Update an existing comment
     * @param {number} commentId - Comment ID
     * @param {Object} updates - Fields to update
     * @returns {Promise<Object>} Updated comment object
     */
    async updateComment(commentId, updates) {
        try {
            // Ensure commentId is a number, not an object or array
            const id = typeof commentId === 'number' ? commentId : 
                       (typeof commentId === 'object' && commentId !== null && commentId.id ? commentId.id : 
                        (Array.isArray(commentId) ? commentId[0] : parseInt(commentId)));
            
            if (!id || isNaN(id)) {
                throw new Error(`Invalid comment ID: ${commentId}`);
            }

            logger.log('Updating comment:', {
                commentId: id,
                updates,
                idType: typeof id
            });

            // Odoo 19 orm.write format: orm.write(model, ids, values)
            // NOT: orm.write(model, [[ids], values])
            await this.orm.write(
                'knowledge.article.comment',
                [id],  // ids as array of numbers
                updates  // values as object
            );

            // Reload comments
            await this.loadComments();

            return this.comments.find(c => c.id === id);
        } catch (error) {
            logger.error('Error updating comment:', error);
            logger.error('Error details:', {
                commentId,
                commentIdType: typeof commentId,
                updates,
                errorMessage: error.message
            });
            throw error;
        }
    }

    /**
     * Reply to a comment
     * @param {number} parentCommentId - Parent comment ID
     * @param {string} replyBody - Reply body (HTML)
     * @returns {Promise<Object>} Created reply comment
     */
    async replyToComment(parentCommentId, replyBody) {
        if (!replyBody.trim()) {
            throw new Error('Reply body cannot be empty');
        }

        const parentComment = this.comments.find(c => c.id === parentCommentId);
        if (!parentComment) {
            throw new Error('Parent comment not found');
        }

        try {
            // Convert plain text body to HTML format
            const htmlBody = this.convertToHtml(replyBody.trim());

            const replyData = {
                article_id: this.articleId,
                parent_id: parentCommentId,
                body: htmlBody,
                selected_text: parentComment.selected_text || '',
                start_offset: parentComment.start_offset || 0,
                end_offset: parentComment.end_offset || 0,
                element_selector: parentComment.element_selector || '',
            };

            // Don't send mentioned_user_ids - backend will extract them automatically

            const replyId = await this.orm.create(
                'knowledge.article.comment',
                [replyData]
            );

            await this.loadComments();

            return this.comments.find(c => c.id === replyId);
        } catch (error) {
            logger.error('Error replying to comment:', error);
            throw error;
        }
    }

    /**
     * Resolve/unresolve a comment
     * @param {number} commentId - Comment ID
     * @param {boolean} resolved - Whether to resolve or unresolve
     * @returns {Promise<Object>} Updated comment object
     */
    async toggleResolve(commentId, resolved = true) {
        // Ensure commentId is a number
        const id = typeof commentId === 'number' ? commentId : 
                   (typeof commentId === 'object' && commentId !== null && commentId.id ? commentId.id : 
                    (Array.isArray(commentId) ? commentId[0] : parseInt(commentId)));
        
        if (!id || isNaN(id)) {
            throw new Error(`Invalid comment ID for toggleResolve: ${commentId}`);
        }

        // Step 1: If resolving (resolved = true), force remove highlight from DOM IMMEDIATELY
        if (resolved && this.contentElement) {
            // Remove from highlights map first
            if (this.highlights.has(id)) {
                this.removeHighlight(id);
            }
            
            // Force remove from DOM with synchronous operations
            const highlightInDOM = this.contentElement.querySelector(
                `.o_knowledge_comment_highlight[data-comment-id="${id}"]`
            );
            if (highlightInDOM) {
                const parent = highlightInDOM.parentNode;
                if (parent) {
                    const text = highlightInDOM.textContent || highlightInDOM.innerText;
                    // Replace with text node
                    const textNode = document.createTextNode(text);
                    parent.replaceChild(textNode, highlightInDOM);
                    parent.normalize();
                    
                    // Double-check: Remove any remaining references
                    const stillExists = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${id}"]`
                    );
                    if (stillExists) {
                        const parent2 = stillExists.parentNode;
                        if (parent2) {
                            const text2 = stillExists.textContent || stillExists.innerText;
                            parent2.replaceChild(document.createTextNode(text2), stillExists);
                            parent2.normalize();
                        }
                    }
                }
                // Ensure removed from map
                this.highlights.delete(id);
            }
        }

        // Step 2: Update comment in backend
        const result = await this.updateComment(id, { resolved });

        // Step 3: Wait for DOM to be ready, then re-render highlights
        // Use double requestAnimationFrame to ensure DOM updates are complete
        await new Promise(resolve => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    resolve();
                });
            });
        });

        // Step 4: Re-render highlights with updated comment data
        await this.renderHighlights();

        return result;
    }

    /**
     * Delete a comment
     * @param {number} commentId - Comment ID
     * @returns {Promise<void>}
     */
    async deleteComment(commentId) {
        try {
            await this.orm.unlink(
                'knowledge.article.comment',
                [[commentId]]
            );

            // Remove highlight
            this.removeHighlight(commentId);

            // Reload comments
            await this.loadComments();
        } catch (error) {
            logger.error('Error deleting comment:', error);
            throw error;
        }
    }

    /**
     * Render highlights for all comments
     */
    async renderHighlights() {
        if (!this.contentElement) return;
        
        // CRITICAL: Prevent infinite loop - if already rendering, skip
        if (this._isRenderingHighlights) {
            logger.log('Skipping renderHighlights(): already rendering (preventing infinite loop)');
            return;
        }
        
        // Temporarily stop watching to prevent observer from interfering
        const wasWatching = !!this._highlightObserver;
        if (wasWatching) {
            this.stopWatchingHighlights();
        }
        
        // Set flag to prevent recursive calls
        this._isRenderingHighlights = true;

        try {
            // Step 1: Check if temp highlight exists and should be replaced
        let tempHighlight = null;
        let tempHighlightText = null;
        if (this.textSelectionHandler && this.textSelectionHandler.tempHighlight) {
            tempHighlight = this.textSelectionHandler.tempHighlight;
            if (tempHighlight && tempHighlight.parentNode) {
                tempHighlightText = (tempHighlight.textContent || tempHighlight.innerText || '').trim();
            }
        }

        // CRITICAL: Filter comments - only render highlights for comments that are NOT resolved
        // Even if a resolved comment has unresolved replies, we should NOT show its highlight
        // This matches the behavior of getDisplayComments() in comment_overlay.js
        const resolvedComments = this.comments.filter(c => c.resolved);
        const unresolvedComments = this.comments.filter(c => !c.resolved);
        const resolvedIds = new Set(resolvedComments.map(c => c.id));
        const unresolvedIds = new Set(unresolvedComments.map(c => c.id));
        
        // Also collect all resolved comment IDs including those that might have unresolved replies
        // We need to ensure highlights for resolved comments are removed even if they have unresolved replies
        const allResolvedCommentIds = new Set();
        resolvedComments.forEach(c => allResolvedCommentIds.add(c.id));
        
        // Helper to recursively find all resolved comment IDs (including parent comments of unresolved replies)
        const findResolvedParentIds = (comments) => {
            comments.forEach(comment => {
                if (comment.resolved) {
                    allResolvedCommentIds.add(comment.id);
                }
                if (comment.replies && comment.replies.length > 0) {
                    findResolvedParentIds(comment.replies);
                }
            });
        };
        findResolvedParentIds(this.comments);

        // Step 3: If temp highlight exists, try to find matching comment to replace it
        // IMPORTANT: Don't skip rendering if we have unresolved comments - always render them
        // Only skip if we have temp highlight AND no unresolved comments (user is still creating)
        let shouldSkipRendering = false;
        let matchingComment = null;
        
        if (tempHighlight && tempHighlightText) {
            // Check if any unresolved comment matches the temp highlight text
            matchingComment = unresolvedComments.find(comment => {
                if (!comment.selected_text) return false;
                const commentText = comment.selected_text.trim();
                const tempTextNormalized = tempHighlightText.replace(/\s+/g, ' ').trim();
                const commentTextNormalized = commentText.replace(/\s+/g, ' ').trim();
                
                // Check if texts match (either exact match or one contains the other)
                return tempTextNormalized === commentTextNormalized ||
                       tempTextNormalized.includes(commentTextNormalized) ||
                       commentTextNormalized.includes(tempTextNormalized);
            });
            
            if (!matchingComment && unresolvedComments.length > 0) {
                // We have unresolved comments but no match - still render them
                // This can happen if text matching fails but comment exists
                logger.log('Temp highlight exists but no exact match found, but we have unresolved comments - rendering them anyway', {
                    tempHighlightInDOM: !!tempHighlight.parentNode,
                    tempHighlightText: tempHighlightText.substring(0, 50),
                    totalUnresolvedComments: unresolvedComments.length
                });
                shouldSkipRendering = false;
            } else if (!matchingComment && unresolvedComments.length === 0) {
                // No matching comment AND no unresolved comments - user is still creating, skip rendering
                logger.log('Skipping highlight re-render: temp highlight exists but no matching comment found and no unresolved comments (user is creating comment)', {
                    tempHighlightInDOM: !!tempHighlight.parentNode,
                    tempHighlightText: tempHighlightText.substring(0, 50),
                    totalUnresolvedComments: 0
                });
                shouldSkipRendering = true;
            } else if (matchingComment) {
                // Matching comment found - proceed with rendering to replace temp highlight
                logger.log('Temp highlight will be replaced by permanent highlight', {
                    tempHighlightText: tempHighlightText.substring(0, 50),
                    matchingCommentId: matchingComment.id,
                    matchingCommentText: matchingComment.selected_text ? matchingComment.selected_text.substring(0, 50) : null
                });
                shouldSkipRendering = false;
            }
        }
        
        // Skip rendering only if user is still creating (no unresolved comments)
        if (shouldSkipRendering) {
            return;
        }

        // Step 4: Force remove ALL resolved highlights from DOM SYNCHRONOUSLY first
        // CRITICAL: Remove highlights for ALL resolved comments, even if they have unresolved replies
        const allHighlightsInDOM = this.contentElement.querySelectorAll(
            '.o_knowledge_comment_highlight'
        );
        allHighlightsInDOM.forEach(highlightEl => {
            const commentIdAttr = highlightEl.getAttribute('data-comment-id');
            if (commentIdAttr) {
                const commentId = parseInt(commentIdAttr, 10);
                // Remove if resolved (use allResolvedCommentIds to catch all resolved comments)
                if (allResolvedCommentIds.has(commentId)) {
                    logger.log(`Removing highlight for resolved comment ${commentId}`);
                    const parent = highlightEl.parentNode;
                    if (parent) {
                        const text = highlightEl.textContent || highlightEl.innerText;
                        parent.replaceChild(document.createTextNode(text), highlightEl);
                        parent.normalize();
                    }
                    // Remove from map
                    this.highlights.delete(commentId);
                }
                // Also remove if not in unresolved list (orphaned highlights)
                else if (!unresolvedIds.has(commentId)) {
                    logger.log(`Removing orphaned highlight for comment ${commentId}`);
                    const parent = highlightEl.parentNode;
                    if (parent) {
                        const text = highlightEl.textContent || highlightEl.innerText;
                        parent.replaceChild(document.createTextNode(text), highlightEl);
                        parent.normalize();
                    }
                    // Remove from map
                    this.highlights.delete(commentId);
                }
            }
        });

        // Step 5: Wait for DOM updates to complete using double requestAnimationFrame
        await new Promise(resolve => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    resolve();
                });
            });
        });

        // Step 6: Double-check and remove any remaining resolved highlights
        // Use allResolvedCommentIds to catch all resolved comments
        const remainingHighlights = this.contentElement.querySelectorAll(
            '.o_knowledge_comment_highlight'
        );
        remainingHighlights.forEach(highlightEl => {
            const commentIdAttr = highlightEl.getAttribute('data-comment-id');
            if (commentIdAttr) {
                const commentId = parseInt(commentIdAttr, 10);
                if (allResolvedCommentIds.has(commentId)) {
                    logger.log(`Double-check: Removing remaining highlight for resolved comment ${commentId}`);
                    const parent = highlightEl.parentNode;
                    if (parent) {
                        const text = highlightEl.textContent || highlightEl.innerText;
                        parent.replaceChild(document.createTextNode(text), highlightEl);
                        parent.normalize();
                    }
                    // Remove from map
                    this.highlights.delete(commentId);
                }
            }
        });

        // Step 7: Clear highlights map (only for resolved/orphaned ones, keep unresolved)
        // We've already removed resolved ones above, so this is just a cleanup

        // Step 8: DON'T remove temp highlight yet - render permanent highlights first
        // We'll remove temp highlight only after permanent highlights are successfully created
        
        // Step 9: Render highlights for unresolved comments only
        // These will be permanent highlights that remain visible until resolved
        // IMPORTANT: Render in sequence (not parallel) to avoid DOM conflicts
        // CRITICAL: Double-check that comment is not in allResolvedCommentIds before rendering
        for (const comment of unresolvedComments) {
            // Triple-check: Don't render if resolved (check both resolvedIds and allResolvedCommentIds)
            if (!comment.resolved && !resolvedIds.has(comment.id) && !allResolvedCommentIds.has(comment.id)) {
                await this.renderHighlight(comment);
                
                // Small delay between renders to prevent DOM conflicts
                await new Promise(resolve => {
                    requestAnimationFrame(() => {
                        resolve();
                    });
                });
            } else {
                // Comment is resolved - ensure highlight is removed
                if (allResolvedCommentIds.has(comment.id) || resolvedIds.has(comment.id)) {
                    logger.log(`Skipping render for resolved comment ${comment.id}, ensuring highlight is removed`);
                    // Remove highlight if it exists
                    const existingHighlight = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                    );
                    if (existingHighlight) {
                        const parent = existingHighlight.parentNode;
                        if (parent) {
                            const text = existingHighlight.textContent || existingHighlight.innerText;
                            parent.replaceChild(document.createTextNode(text), existingHighlight);
                            parent.normalize();
                        }
                        this.highlights.delete(comment.id);
                        logger.log(`Removed highlight for resolved comment ${comment.id}`);
                    }
                }
            }
        }
        
        // Step 10: Wait for DOM to update after rendering permanent highlights
        await new Promise(resolve => {
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    resolve();
                });
            });
        });
        
        // Step 11: NOW remove temp highlight only if permanent highlights were successfully created
        if (tempHighlight && tempHighlight.parentNode && tempHighlightText) {
            // Check if we have matching permanent highlights in DOM
            const matchingComment = unresolvedComments.find(comment => {
                if (!comment.selected_text) return false;
                const commentText = comment.selected_text.trim();
                const tempTextNormalized = tempHighlightText.replace(/\s+/g, ' ').trim();
                const commentTextNormalized = commentText.replace(/\s+/g, ' ').trim();
                
                return tempTextNormalized === commentTextNormalized ||
                       tempTextNormalized.includes(commentTextNormalized) ||
                       commentTextNormalized.includes(tempTextNormalized);
            });
            
            if (matchingComment) {
                // Verify that permanent highlight exists in DOM before removing temp highlight
                const permanentHighlight = this.contentElement.querySelector(
                    `.o_knowledge_comment_highlight[data-comment-id="${matchingComment.id}"]`
                );
                
                if (permanentHighlight && permanentHighlight.parentNode) {
                    // Permanent highlight exists - safe to remove temp highlight
                    logger.log('Permanent highlight created successfully, removing temp highlight', {
                        tempHighlightText: tempHighlightText.substring(0, 50),
                        permanentHighlightId: matchingComment.id,
                        permanentHighlightInDOM: true
                    });
                    
                    // Remove temp highlight from DOM
                    const tempParent = tempHighlight.parentNode;
                    const tempText = tempHighlight.textContent || tempHighlight.innerText;
                    if (tempParent) {
                        // Replace temp highlight with text node
                        const textNode = document.createTextNode(tempText);
                        tempParent.replaceChild(textNode, tempHighlight);
                        tempParent.normalize();
                    }
                    
                    // Clear reference in textSelectionHandler
                    if (this.textSelectionHandler) {
                        this.textSelectionHandler.tempHighlight = null;
                    }
                } else {
                    // Permanent highlight not found - keep temp highlight for now
                    logger.warn('Permanent highlight not found in DOM, keeping temp highlight', {
                        tempHighlightText: tempHighlightText.substring(0, 50),
                        matchingCommentId: matchingComment.id,
                        permanentHighlightInDOM: false
                    });
                }
            }
        }

        // Step 10: Verify all unresolved comments have highlights in DOM
        const highlightsInDOM = this.contentElement.querySelectorAll('.o_knowledge_comment_highlight').length;
        const missingHighlights = unresolvedComments.filter(comment => {
            const highlightInDOM = this.contentElement.querySelector(
                `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
            );
            return !highlightInDOM;
        });
        
        // Only attempt to render missing highlights if we have any
        // But don't do it if we already tried (to prevent infinite loop)
        if (missingHighlights.length > 0) {
            logger.warn('Some highlights are missing in DOM after rendering, attempting to render them', {
                missingCount: missingHighlights.length,
                missingCommentIds: missingHighlights.map(c => c.id)
            });
            
            // Wait for DOM to settle before attempting to render missing highlights
            await new Promise(resolve => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        resolve();
                    });
                });
            });
            
            // Attempt to render missing highlights (but only once per renderHighlights call)
            // CRITICAL: Use for...of loop with await to render sequentially
            for (const comment of missingHighlights) {
                if (!comment.resolved) {
                    try {
                        // Double-check it's still missing before rendering
                        const stillMissing = !this.contentElement.querySelector(
                            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                        );
                        if (stillMissing) {
                            logger.log(`Attempting to render missing highlight for comment ${comment.id}`);
                            await this.renderHighlight(comment);
                            
                            // Verify it was actually rendered
                            const verifyHighlight = this.contentElement.querySelector(
                                `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                            );
                            if (verifyHighlight && verifyHighlight.parentNode) {
                                logger.log(`Successfully rendered missing highlight for comment ${comment.id}`);
                                // Add to map if not already there
                                if (!this.highlights.has(comment.id)) {
                                    this.highlights.set(comment.id, verifyHighlight);
                                }
                            } else {
                                logger.warn(`Failed to render missing highlight for comment ${comment.id} - not found in DOM after render`);
                            }
                            
                            // Small delay between renders to prevent DOM conflicts
                            await new Promise(resolve => {
                                requestAnimationFrame(() => {
                                    resolve();
                                });
                            });
                        } else {
                            logger.log(`Missing highlight for comment ${comment.id} was already rendered (found in DOM)`);
                        }
                    } catch (error) {
                        logger.error(`Error rendering missing highlight for comment ${comment.id}:`, error);
                    }
                }
            }
            
            // Final verification: Check if all highlights are now in DOM
            const finalHighlightsInDOM = this.contentElement.querySelectorAll('.o_knowledge_comment_highlight').length;
            const finalMissing = unresolvedComments.filter(comment => {
                const highlightInDOM = this.contentElement.querySelector(
                    `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                );
                return !highlightInDOM;
            });
            
            if (finalMissing.length > 0) {
                logger.warn('Some highlights are still missing after retry:', {
                    stillMissingCount: finalMissing.length,
                    stillMissingIds: finalMissing.map(c => c.id),
                    totalHighlightsInDOM: finalHighlightsInDOM,
                    expectedCount: unresolvedComments.length
                });
            } else {
                logger.log('All highlights successfully rendered after retry:', {
                    totalHighlightsInDOM: finalHighlightsInDOM,
                    expectedCount: unresolvedComments.length
                });
            }
        }
        
        logger.log('Highlights rendered:', {
            unresolvedCount: unresolvedComments.length,
            resolvedCount: resolvedComments.length,
            totalHighlights: this.highlights.size,
            highlightsInDOM: highlightsInDOM,
            resolvedCommentIds: resolvedComments.map(c => c.id),
            unresolvedCommentIds: unresolvedComments.map(c => c.id),
            tempHighlightWasReplaced: tempHighlight && tempHighlight.parentNode ? tempHighlight.hasAttribute('data-comment-id') : false,
            missingHighlightsCount: missingHighlights.length
        });
        } finally {
            // Always clear flag when done (even if error occurred)
            // Add a small delay before clearing to prevent rapid re-renders
            setTimeout(() => {
                this._isRenderingHighlights = false;
                
                // Re-start watching after rendering completes
                if (wasWatching) {
                    setTimeout(() => {
                        this.startWatchingHighlights();
                    }, 1000);
                }
            }, 100);
        }
    }

    /**
     * Render highlight for a single comment
     * @param {Object} comment - Comment object
     * @returns {Promise<boolean>} Returns true if highlight was successfully rendered, false otherwise
     */
    async renderHighlight(comment) {
        if (!this.contentElement) {
            logger.warn(`Cannot render highlight for comment ${comment.id}: contentElement is null`);
            return false;
        }

        // Don't render highlight for resolved comments
        if (comment.resolved) {
            // Ensure highlight is removed if comment is resolved
            if (this.highlights.has(comment.id)) {
                this.removeHighlight(comment.id);
            }
            return false;
        }

        // CRITICAL: Always check DOM directly first, not just the reference
        // This prevents skipping when highlight was removed between checks
        const highlightInDOM = this.contentElement.querySelector(
            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
        );
        
        if (highlightInDOM) {
            // CRITICAL: Check if comment is actually resolved - if so, remove the highlight
            if (comment.resolved) {
                logger.log(`Highlight for comment ${comment.id} exists in DOM but comment is resolved - removing highlight`);
                const parent = highlightInDOM.parentNode;
                if (parent) {
                    const text = highlightInDOM.textContent || highlightInDOM.innerText;
                    parent.replaceChild(document.createTextNode(text), highlightInDOM);
                    parent.normalize();
                }
                this.highlights.delete(comment.id);
                return false; // Don't render, highlight was removed
            }
            
            // Highlight exists in DOM - update reference if needed and skip rendering
            if (this.highlights.has(comment.id)) {
                const existingHighlight = this.highlights.get(comment.id);
                if (highlightInDOM === existingHighlight) {
                    // Reference matches - skip
                    logger.log(`Highlight for comment ${comment.id} already exists in DOM (reference matches), skipping`);
                    return true; // Already exists
                } else {
                    // Reference doesn't match - update it
                    logger.log(`Highlight for comment ${comment.id} exists in DOM but reference mismatch, updating reference`);
                    this.highlights.set(comment.id, highlightInDOM);
                    return true; // Already exists
                }
            } else {
                // Not in map but exists in DOM - add to map and skip rendering
                logger.log(`Highlight for comment ${comment.id} exists in DOM but not in map, adding to map`);
                this.highlights.set(comment.id, highlightInDOM);
                return true; // Already exists
            }
        } else {
            // Highlight not in DOM - remove from map if exists and continue to render
            if (this.highlights.has(comment.id)) {
                const existingHighlight = this.highlights.get(comment.id);
                logger.log(`Highlight for comment ${comment.id} not in DOM but exists in map, removing stale reference`, {
                    hasParentNode: existingHighlight && existingHighlight.parentNode ? true : false
                });
                this.highlights.delete(comment.id);
            }
            // Continue to render new highlight
        }

        try {
            // CRITICAL: Check if temp highlight exists - if so, skip DOM normalization
            // Normalizing the DOM while a temp highlight is active will cause it to disappear or become incomplete
            const hasTempHighlight = this.textSelectionHandler && 
                                     this.textSelectionHandler.tempHighlight && 
                                     this.textSelectionHandler.tempHighlight.parentNode;
            
            // Declare existingHighlights in outer scope so it's available in finally block
            let existingHighlights = [];
            
            if (hasTempHighlight) {
                logger.log(`Skipping DOM normalization for comment ${comment.id}: temp highlight is active`, {
                    commentId: comment.id,
                    tempHighlightText: this.textSelectionHandler.tempHighlight.textContent ? 
                        this.textSelectionHandler.tempHighlight.textContent.substring(0, 50) : null
                });
                // Don't normalize DOM - calculate offsets with existing highlights in place
                // This preserves the temp highlight integrity
            } else {
                // No temp highlight - safe to normalize DOM for accurate offset calculation
                // Store existing highlights to restore later
                const allHighlights = this.contentElement.querySelectorAll('.o_knowledge_comment_highlight');
                
                allHighlights.forEach(highlightEl => {
                    const highlightCommentId = highlightEl.getAttribute('data-comment-id');
                    // Don't remove the highlight we're trying to render
                    if (highlightCommentId && parseInt(highlightCommentId, 10) !== comment.id) {
                        const parent = highlightEl.parentNode;
                        if (parent) {
                            const text = highlightEl.textContent || highlightEl.innerText;
                            const textNode = document.createTextNode(text);
                            parent.replaceChild(textNode, highlightEl);
                            existingHighlights.push({
                                element: highlightEl,
                                parent: parent,
                                textNode: textNode
                            });
                        }
                    }
                });
                
                // Normalize DOM only if no temp highlight exists
                this.contentElement.normalize();
            }
            
            try {
                // Now calculate offsets with normalized DOM (no highlight elements)
                const textNodes = this.getTextNodes(this.contentElement);
                const totalLength = textNodes.reduce((sum, node) => sum + node.textContent.length, 0);
                
                // Get plain text to verify offsets
                const plainText = this.getPlainText(this.contentElement);
                
                let startNode = null;
                let startOffset = 0;
                let endNode = null;
                let endOffset = 0;
                
                // Strategy 1: Try to find by text search first (most reliable)
                let textSearchSuccess = false;
                if (comment.selected_text) {
                    const searchText = comment.selected_text.trim();
                    if (searchText.length > 0) {
                        // Find all occurrences of the text
                        const textIndex = plainText.indexOf(searchText);
                        
                        if (textIndex !== -1) {
                            // Use text search to find position
                            let currentOffset = 0;
                            
                            for (const node of textNodes) {
                                const nodeLength = node.textContent.length;
                                
                                if (!startNode && currentOffset + nodeLength > textIndex) {
                                    startNode = node;
                                    startOffset = textIndex - currentOffset;
                                }
                                
                                if (!endNode && currentOffset + nodeLength >= textIndex + searchText.length) {
                                    endNode = node;
                                    endOffset = (textIndex + searchText.length) - currentOffset;
                                    textSearchSuccess = true;
                                    break;
                                }
                                
                                currentOffset += nodeLength;
                            }
                        }
                    }
                }
                
                // Strategy 2: If text search failed, try using stored offsets
                if (!textSearchSuccess) {
                    let currentOffset = 0;
                    
                    // Validate and adjust offsets if they're out of bounds
                    let adjustedStartOffset = Math.max(0, Math.min(comment.start_offset, totalLength));
                    let adjustedEndOffset = Math.max(adjustedStartOffset, Math.min(comment.end_offset, totalLength));
                    
                    // If end_offset is less than start_offset, adjust it
                    if (adjustedEndOffset < adjustedStartOffset) {
                        adjustedEndOffset = Math.min(adjustedStartOffset + (comment.selected_text?.length || 0), totalLength);
                    }
                    
                    // Find start and end nodes using adjusted offsets
                    for (const node of textNodes) {
                        const nodeLength = node.textContent.length;
                        
                        if (!startNode && currentOffset + nodeLength >= adjustedStartOffset) {
                            startNode = node;
                            startOffset = Math.min(adjustedStartOffset - currentOffset, nodeLength);
                        }
                        
                        if (!endNode && currentOffset + nodeLength >= adjustedEndOffset) {
                            endNode = node;
                            endOffset = Math.min(adjustedEndOffset - currentOffset, nodeLength);
                            break;
                        }
                        
                        currentOffset += nodeLength;
                    }
                    
                    if (adjustedStartOffset !== comment.start_offset || adjustedEndOffset !== comment.end_offset) {
                        logger.warn(`Offsets adjusted for comment ${comment.id}`, {
                            originalStart: comment.start_offset,
                            originalEnd: comment.end_offset,
                            adjustedStart: adjustedStartOffset,
                            adjustedEnd: adjustedEndOffset,
                            totalLength: totalLength,
                            selectedText: comment.selected_text
                        });
                    }
                }

                if (!startNode || !endNode) {
                    logger.warn(`Could not find nodes for comment ${comment.id}`, {
                        startOffset: comment.start_offset,
                        endOffset: comment.end_offset,
                        totalTextNodes: textNodes.length,
                        totalLength: totalLength,
                        selectedText: comment.selected_text,
                        textSearchUsed: textSearchSuccess
                    });
                    
                    // Restore existing highlights before returning (only if we normalized)
                    if (!hasTempHighlight && existingHighlights.length > 0) {
                        existingHighlights.forEach(({element, parent, textNode}) => {
                            if (textNode.parentNode === parent) {
                                parent.replaceChild(element, textNode);
                            }
                        });
                        this.contentElement.normalize();
                    }
                    return;
                }

                // Create range and highlight
                const range = document.createRange();
                range.setStart(startNode, startOffset);
                range.setEnd(endNode, endOffset);

                const highlight = document.createElement('span');
                highlight.className = 'o_knowledge_comment_highlight';
                highlight.setAttribute('data-comment-id', comment.id);
                highlight.style.backgroundColor = comment.highlight_color || '#ffeb3b';
                highlight.style.cursor = 'pointer';
                highlight.style.borderRadius = '2px';
                highlight.title = `Comment by ${comment.author_id && Array.isArray(comment.author_id) ? comment.author_id[1] : 'Unknown'}`;

                // Add click handler to open comment panel and scroll to comment in sidebar
                // Use capture phase to ensure event fires before other handlers
                let clickHandled = false;
                
                highlight.addEventListener('click', (e) => {
                    // CRITICAL: Only handle left-click (button 0), allow right-click for context menu
                    // Right-click (button 2) and middle-click (button 1) should work normally
                    if (e.button !== 0) {
                        // Allow right-click and middle-click to work normally (for context menu, etc.)
                        return;
                    }
                    
                    // Prevent multiple clicks from firing
                    if (clickHandled) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    
                    clickHandled = true;
                    
                    // Reset flag after a short delay
                    setTimeout(() => {
                        clickHandled = false;
                    }, 300);
                    
                    e.stopPropagation(); // Prevent event bubbling
                    e.preventDefault(); // Prevent default behavior (only for left-click)
                    
                    logger.log('Highlight clicked:', {
                        commentId: comment.id,
                        hasCallback: !!this.onHighlightClickCallback
                    });
                    
                    // If callback is provided, use it to open panel and select comment
                    if (this.onHighlightClickCallback) {
                        // Use setTimeout to ensure DOM is stable
                        setTimeout(() => {
                            this.onHighlightClickCallback(comment.id);
                        }, 50);
                    } else {
                        // Fallback: Just scroll to comment in sidebar (old behavior)
                        const commentElement = document.querySelector(`.o_knowledge_comment_item[data-comment-id="${comment.id}"]`);
                        if (commentElement) {
                            commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                            // Highlight the comment briefly
                            commentElement.classList.add('o_knowledge_comment_highlighted');
                            setTimeout(() => {
                                commentElement.classList.remove('o_knowledge_comment_highlighted');
                            }, 2000);
                        }
                    }
                }, true); // Use capture phase

                try {
                    range.surroundContents(highlight);
                    this.highlights.set(comment.id, highlight);
                    
                    // CRITICAL: Wait for DOM to stabilize before adding profile picture
                    // Sometimes DOM manipulation needs time to settle
                    await new Promise(resolve => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => {
                                resolve();
                            });
                        });
                    });
                    
                    // Verify highlight is actually in DOM before proceeding
                    const highlightInDOM = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                    );
                    
                    if (!highlightInDOM || !highlightInDOM.parentNode) {
                        logger.warn(`Highlight for comment ${comment.id} not in DOM immediately after render, attempting fallback`);
                        // Try fallback insertion method
                        try {
                            const clonedRange = range.cloneRange();
                            const contents = clonedRange.extractContents();
                            highlight.appendChild(contents);
                            clonedRange.insertNode(highlight);
                            this.highlights.set(comment.id, highlight);
                        } catch (fallbackError) {
                            logger.error(`Fallback insertion failed for comment ${comment.id}:`, fallbackError);
                            return false;
                        }
                    }
                    
                    // Add profile picture to the right of highlight
                    this.addProfilePictureToHighlight(comment, highlight);
                    
                    // Final verification after all operations
                    await new Promise(resolve => requestAnimationFrame(resolve));
                    
                    const finalCheck = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                    );
                    
                    if (!finalCheck || !finalCheck.parentNode) {
                        logger.warn(`Highlight for comment ${comment.id} disappeared from DOM after operations`, {
                            hasParentNode: finalCheck && finalCheck.parentNode !== null,
                            highlightInMap: this.highlights.has(comment.id)
                        });
                        // Remove stale reference from map
                        if (this.highlights.has(comment.id)) {
                            this.highlights.delete(comment.id);
                        }
                        return false;
                    }
                    
                    // Update map with verified reference
                    this.highlights.set(comment.id, finalCheck);
                    
                    logger.log(`Highlight rendered for comment ${comment.id}`, {
                        commentId: comment.id,
                        selectedText: comment.selected_text,
                        textSearchUsed: textSearchSuccess,
                        tempHighlightActive: hasTempHighlight,
                        highlightInDOM: !!finalCheck.parentNode
                    });
                    
                    return true; // Success
                } catch (e) {
                    // If surroundContents fails (e.g., range spans multiple elements),
                    // use extractContents and insert
                    logger.log(`surroundContents failed for comment ${comment.id}, using fallback method:`, e.message);
                    
                    try {
                        const contents = range.extractContents();
                        highlight.appendChild(contents);
                        range.insertNode(highlight);
                        this.highlights.set(comment.id, highlight);
                        
                        // Wait for DOM to stabilize
                        await new Promise(resolve => {
                            requestAnimationFrame(() => {
                                requestAnimationFrame(() => {
                                    resolve();
                                });
                            });
                        });
                        
                        // Verify highlight is in DOM
                        const highlightInDOM = this.contentElement.querySelector(
                            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                        );
                        
                        if (!highlightInDOM || !highlightInDOM.parentNode) {
                            logger.warn(`Highlight for comment ${comment.id} not in DOM after fallback insertion`);
                            if (this.highlights.has(comment.id)) {
                                this.highlights.delete(comment.id);
                            }
                            return false;
                        }
                        
                        // Add profile picture to the right of highlight
                        this.addProfilePictureToHighlight(comment, highlight);
                        
                        // Final verification
                        await new Promise(resolve => requestAnimationFrame(resolve));
                        
                        const finalCheck = this.contentElement.querySelector(
                            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                        );
                        
                        if (!finalCheck || !finalCheck.parentNode) {
                            logger.warn(`Highlight for comment ${comment.id} disappeared after fallback operations`, {
                                hasParentNode: finalCheck && finalCheck.parentNode !== null,
                                highlightInMap: this.highlights.has(comment.id)
                            });
                            if (this.highlights.has(comment.id)) {
                                this.highlights.delete(comment.id);
                            }
                            return false;
                        }
                        
                        // Update map with verified reference
                        this.highlights.set(comment.id, finalCheck);
                        
                        logger.log(`Highlight rendered for comment ${comment.id} (using extractContents)`, {
                            commentId: comment.id,
                            selectedText: comment.selected_text,
                            textSearchUsed: textSearchSuccess,
                            tempHighlightActive: hasTempHighlight,
                            highlightInDOM: !!finalCheck.parentNode
                        });
                        
                        return true; // Success
                    } catch (fallbackError) {
                        logger.error(`Fallback insertion also failed for comment ${comment.id}:`, fallbackError);
                        if (this.highlights.has(comment.id)) {
                            this.highlights.delete(comment.id);
                        }
                        return false;
                    }
                }
            } finally {
                // Restore existing highlights that we temporarily removed (only if we normalized)
                if (!hasTempHighlight && existingHighlights.length > 0) {
                    existingHighlights.forEach(({element, parent, textNode}) => {
                        if (textNode.parentNode === parent) {
                            parent.replaceChild(element, textNode);
                        }
                    });
                    this.contentElement.normalize();
                }
            }
        } catch (error) {
            logger.error(`Error rendering highlight for comment ${comment.id}:`, error);
            return false; // Failed
        }
        
        // If we reach here, rendering was not successful
        return false;
    }

    /**
     * Get plain text content from an element (excluding script/style tags)
     * @param {HTMLElement} element 
     * @returns {string} Plain text content
     */
    getPlainText(element) {
        if (!element) return '';
        
        const textNodes = this.getTextNodes(element);
        return textNodes.map(node => node.textContent || '').join('');
    }

    /**
     * Get all text nodes within an element
     * @param {HTMLElement} element 
     * @returns {Array<Node>} Array of text nodes
     */
    getTextNodes(element) {
        const textNodes = [];
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    // Skip nodes inside script, style, and comment highlights
                    const parent = node.parentElement;
                    if (!parent) return NodeFilter.FILTER_REJECT;
                    if (parent.tagName === 'SCRIPT' || parent.tagName === 'STYLE') {
                        return NodeFilter.FILTER_REJECT;
                    }
                    if (parent.classList.contains('o_knowledge_comment_highlight')) {
                        return NodeFilter.FILTER_REJECT;
                    }
                    return NodeFilter.FILTER_ACCEPT;
                }
            },
            false
        );

        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }

        return textNodes;
    }

    /**
     * Add profile picture to the right of a highlight
     * @param {Object} comment - Comment object with author info
     * @param {HTMLElement} highlightEl - Highlight element
     */
    addProfilePictureToHighlight(comment, highlightEl) {
        if (!highlightEl || !highlightEl.parentNode) return;
        
        // Check if profile picture already exists
        const existingPic = highlightEl.parentNode.querySelector(
            `.o_knowledge_comment_avatar_inline[data-comment-id="${comment.id}"]`
        );
        if (existingPic) {
            return; // Already has profile picture
        }
        
        try {
            // Get avatar URL
            let avatarUrl = '/web/static/img/avatar.png'; // Default avatar
            if (comment.author_id && Array.isArray(comment.author_id) && comment.author_id[0]) {
                if (comment.author_image) {
                    if (typeof comment.author_image === 'string' && comment.author_image.startsWith('data:')) {
                        avatarUrl = comment.author_image;
                    } else if (typeof comment.author_image === 'string') {
                        avatarUrl = `data:image/png;base64,${comment.author_image}`;
                    }
                } else {
                    avatarUrl = `/web/image/res.users/${comment.author_id[0]}/image_128`;
                }
            }
            
            // Create avatar image element
            const avatarImg = document.createElement('img');
            avatarImg.className = 'o_knowledge_comment_avatar_inline';
            avatarImg.setAttribute('data-comment-id', comment.id);
            avatarImg.src = avatarUrl;
            avatarImg.alt = comment.author_id && Array.isArray(comment.author_id) ? comment.author_id[1] : 'Author';
            avatarImg.title = `Comment by ${comment.author_id && Array.isArray(comment.author_id) ? comment.author_id[1] : 'Unknown'}`;
            
            // Style the avatar
            avatarImg.style.width = '20px';
            avatarImg.style.height = '20px';
            avatarImg.style.borderRadius = '50%';
            avatarImg.style.marginLeft = '6px';
            avatarImg.style.verticalAlign = 'middle';
            avatarImg.style.display = 'inline-block';
            avatarImg.style.objectFit = 'cover';
            avatarImg.style.border = '1px solid rgba(0, 0, 0, 0.1)';
            avatarImg.style.cursor = 'pointer';
            avatarImg.style.flexShrink = '0';
            
            // Add click handler to scroll to comment
            avatarImg.addEventListener('click', (e) => {
                e.stopPropagation();
                const commentElement = document.querySelector(
                    `.o_knowledge_comment_item[data-comment-id="${comment.id}"]`
                );
                if (commentElement) {
                    commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    commentElement.classList.add('o_knowledge_comment_highlighted');
                    setTimeout(() => {
                        commentElement.classList.remove('o_knowledge_comment_highlighted');
                    }, 2000);
                }
            });
            
            // Insert avatar after the highlight element
            const parent = highlightEl.parentNode;
            if (parent) {
                // Insert as next sibling
                if (highlightEl.nextSibling) {
                    parent.insertBefore(avatarImg, highlightEl.nextSibling);
                } else {
                    parent.appendChild(avatarImg);
                }
            }
        } catch (error) {
            logger.warn('Error adding profile picture to highlight:', error);
        }
    }

    /**
     * Remove highlight for a comment
     * @param {number} commentId - Comment ID
     */
    removeHighlight(commentId) {
        const highlight = this.highlights.get(commentId);
        if (highlight && highlight.parentNode) {
            const parent = highlight.parentNode;
            const text = highlight.textContent || highlight.innerText;
            parent.replaceChild(document.createTextNode(text), highlight);
            parent.normalize();
            
            // Also remove profile picture if exists
            if (this.contentElement) {
                const avatarImg = this.contentElement.querySelector(
                    `.o_knowledge_comment_avatar_inline[data-comment-id="${commentId}"]`
                );
                if (avatarImg && avatarImg.parentNode) {
                    avatarImg.parentNode.removeChild(avatarImg);
                }
            }
            
            this.highlights.delete(commentId);
        }
    }

    /**
     * Clear all highlights
     */
    clearAllHighlights() {
        this.highlights.forEach((highlight, commentId) => {
            this.removeHighlight(commentId);
        });
        this.highlights.clear();
    }

    /**
     * Extract @mentions from HTML body
     * @param {string} htmlBody - HTML body text
     * @returns {Array<number>} Array of user IDs
     */
    extractMentions(htmlBody) {
        // Remove HTML tags
        const textOnly = htmlBody.replace(/<[^>]+>/g, '');
        
        // Find @mentions (pattern: @username)
        const mentions = textOnly.match(/@(\w+)/g);
        if (!mentions) {
            return [];
        }

        // Extract usernames (remove @)
        const usernames = mentions.map(m => m.substring(1));
        
        // Return array of usernames (will need to resolve to user IDs on server)
        return usernames;
    }

    /**
     * Convert plain text to HTML format
     * @param {string} text - Plain text
     * @returns {string} HTML formatted text
     */
    convertToHtml(text) {
        if (!text) {
            return '';
        }
        
        // Escape HTML entities
        const escapeHtml = (str) => {
            const map = {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#039;'
            };
            return str.replace(/[&<>"']/g, m => map[m]);
        };
        
        // Split by newlines and wrap each line in <p> tags
        const lines = text.split(/\n/);
        return lines.map(line => {
            const escaped = escapeHtml(line.trim());
            return escaped ? `<p>${escaped}</p>` : '<p><br/></p>';
        }).join('');
    }

    /**
     * Get comment by ID
     * @param {number} commentId - Comment ID
     * @returns {Object|null} Comment object
     */
    getComment(commentId) {
        return this.comments.find(c => c.id === commentId) || null;
    }

    /**
     * Get comments with their replies (threaded structure)
     * @returns {Array} Array of top-level comments with nested replies
     */
    getThreadedComments() {
        const topLevel = this.comments.filter(c => !c.parent_id || !c.parent_id[0]);
        const byId = {};
        
        this.comments.forEach(c => {
            byId[c.id] = { ...c, replies: [] };
        });

        this.comments.forEach(c => {
            if (c.parent_id && c.parent_id[0]) {
                const parentId = c.parent_id[0];
                if (byId[parentId]) {
                    byId[parentId].replies.push(byId[c.id]);
                }
            }
        });

        return topLevel.map(c => byId[c.id]).filter(Boolean);
    }

    /**
     * Get unresolved comments count
     * @returns {number} Count of unresolved comments
     */
    getUnresolvedCount() {
        return this.comments.filter(c => !c.resolved).length;
    }

    /**
     * Start watching for highlights being removed from DOM
     * This will automatically re-render highlights if they're removed by Owl/framework
     */
    startWatchingHighlights() {
        if (!this.contentElement) return;
        
        // Stop existing observer if any
        if (this._highlightObserver) {
            this._highlightObserver.disconnect();
            this._highlightObserver = null;
        }
        
        let reRenderTimeout = null;
        const scheduleReRender = () => {
            // Clear existing timeout
            if (reRenderTimeout) {
                clearTimeout(reRenderTimeout);
            }
            
            // Debounce re-rendering (wait 3 seconds after last mutation to allow DOM to stabilize)
            reRenderTimeout = setTimeout(async () => {
                // Prevent re-render if already rendering
                if (this._isRenderingHighlights) {
                    logger.log('Skipping highlight re-render: already rendering');
                    return;
                }
                
                // Cooldown period - don't re-render if we just rendered recently (within 8 seconds)
                const now = Date.now();
                const timeSinceLastRender = now - (this._lastReRenderTime || 0);
                if (timeSinceLastRender < 8000) {
                    logger.log('Skipping highlight re-render: cooldown period active', {
                        timeSinceLastRender: timeSinceLastRender,
                        cooldownRemaining: 8000 - timeSinceLastRender
                    });
                    return;
                }
                
                // CRITICAL: Double-check that highlights are actually missing before re-rendering
                // Wait for DOM to stabilize before checking
                await new Promise(resolve => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            resolve();
                        });
                    });
                });
                
                // Check which highlights are missing from DOM
                const unresolvedComments = this.comments.filter(c => !c.resolved);
                const missingHighlights = [];
                
                for (const comment of unresolvedComments) {
                    const highlightInDOM = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                    );
                    
                    if (!highlightInDOM) {
                        // Highlight should exist but doesn't - mark as missing
                        if (this.highlights.has(comment.id)) {
                            // Remove stale reference from map
                            this.highlights.delete(comment.id);
                        }
                        missingHighlights.push(comment);
                    } else {
                        // Highlight exists - update map reference if needed
                        if (!this.highlights.has(comment.id) || this.highlights.get(comment.id) !== highlightInDOM) {
                            this.highlights.set(comment.id, highlightInDOM);
                        }
                    }
                }
                
                // If we have missing highlights, verify they're really missing before re-rendering
                if (missingHighlights.length > 0) {
                    // Wait a bit more and verify again to avoid false positives
                    await new Promise(resolve => setTimeout(resolve, 500));
                    
                    // Re-check to confirm they're still missing
                    const stillMissing = unresolvedComments.filter(comment => {
                        const highlightInDOM = this.contentElement.querySelector(
                            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                        );
                        return !highlightInDOM;
                    });
                    
                    if (stillMissing.length === 0) {
                        logger.log('Highlights reappeared in DOM - false alarm, skipping re-render');
                        return;
                    }
                    
                    logger.warn('Highlights were removed from DOM, re-rendering missing highlights', {
                        missingCount: stillMissing.length,
                        missingCommentIds: stillMissing.map(c => c.id),
                        originallyMissingCount: missingHighlights.length
                    });
                    
                    // Temporarily disconnect observer to prevent loop
                    if (this._highlightObserver) {
                        this._highlightObserver.disconnect();
                    }
                    
                    try {
                        this._lastReRenderTime = Date.now();
                        
                        // Re-render missing highlights only (use stillMissing which was verified above)
                        for (const comment of stillMissing) {
                            await this.renderHighlight(comment);
                            // Small delay between renders
                            await new Promise(resolve => requestAnimationFrame(resolve));
                        }
                        
                        logger.log('Missing highlights re-rendered', {
                            reRenderedCount: stillMissing.length
                        });
                    } catch (error) {
                        logger.error('Error re-rendering missing highlights:', error);
                    } finally {
                        // Reconnect observer after a delay
                        setTimeout(() => {
                            if (this.contentElement && !this._highlightObserver) {
                                this.startWatchingHighlights();
                            }
                        }, 2000);
                    }
                }
            }, 3000); // Wait 3 seconds after last mutation before checking (increased from 2s)
        };
        
        // Watch for removed nodes (highlights being deleted)
        this._highlightObserver = new MutationObserver((mutations) => {
            // Skip if we're currently rendering (highlights may be temporarily removed during rendering)
            if (this._isRenderingHighlights) {
                return;
            }
            
            let shouldCheck = false;
            let removedHighlightIds = new Set();
            
            for (const mutation of mutations) {
                // Check if any highlights were removed
                if (mutation.type === 'childList' && mutation.removedNodes.length > 0) {
                    for (const node of mutation.removedNodes) {
                        // Check if removed node is a highlight or contains highlights
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            if (node.classList && node.classList.contains('o_knowledge_comment_highlight')) {
                                const commentId = node.getAttribute('data-comment-id');
                                if (commentId) {
                                    removedHighlightIds.add(parseInt(commentId, 10));
                                }
                                shouldCheck = true;
                            }
                            // Also check if it's a parent that might contain highlights
                            if (node.querySelector && node.querySelector('.o_knowledge_comment_highlight')) {
                                const highlightsInNode = node.querySelectorAll('.o_knowledge_comment_highlight');
                                highlightsInNode.forEach(hl => {
                                    const commentId = hl.getAttribute('data-comment-id');
                                    if (commentId) {
                                        removedHighlightIds.add(parseInt(commentId, 10));
                                    }
                                });
                                shouldCheck = true;
                            }
                        }
                    }
                    
                    if (shouldCheck) break;
                }
                
                // Also check if attributes changed (e.g., highlights were replaced)
                // But skip this check if we're rendering to avoid false positives
                if (mutation.type === 'attributes' && mutation.target.classList && 
                    mutation.target.classList.contains('o_knowledge_comment_highlight')) {
                    const commentId = mutation.target.getAttribute('data-comment-id');
                    if (commentId) {
                        removedHighlightIds.add(parseInt(commentId, 10));
                    }
                    shouldCheck = true;
                }
            }
            
            // Verify that highlights are actually missing (not just temporarily during rendering)
            if (shouldCheck && removedHighlightIds.size > 0) {
                // Double-check by querying DOM directly
                let actuallyMissing = false;
                for (const commentId of removedHighlightIds) {
                    const stillInDOM = this.contentElement.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${commentId}"]`
                    );
                    if (!stillInDOM) {
                        actuallyMissing = true;
                        break;
                    }
                }
                
                if (!actuallyMissing) {
                    // Highlights are still in DOM - false alarm, skip re-render
                    logger.log('Highlights detected as removed but still in DOM - false alarm, skipping re-render');
                    return;
                }
            }
            
            if (shouldCheck) {
                scheduleReRender();
            }
        });
        
        // Observe content element for changes
        this._highlightObserver.observe(this.contentElement, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['class', 'data-comment-id']
        });
        
        logger.log('Started watching for removed highlights');
    }

    /**
     * Stop watching for highlights being removed
     */
    stopWatchingHighlights() {
        if (this._highlightObserver) {
            this._highlightObserver.disconnect();
            this._highlightObserver = null;
            logger.log('Stopped watching for removed highlights');
        }
    }
}
