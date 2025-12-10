/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount, onWillUpdateProps, onRendered, onPatched, useEffect, markup } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { CommentManager } from './comment_manager';
import { TextSelectionHandler } from './text_selection';
import { logger } from '../utils/logger';

/**
 * Comment Overlay Component
 * 
 * Displays comment overlay UI similar to Google Docs, allowing users to:
 * - Select text and create comments
 * - View existing comments
 * - Reply to comments
 * - Resolve/unresolve comments
 */
export class CommentOverlay extends Component {
    static template = "knowledge_onthisday_oca.CommentOverlay";
    static props = {
        articleId: { type: Number },
        contentElement: { type: Object, optional: true },
        // Selection data from parent component
        selectionData: { type: Object, optional: true },
        // Trigger to create comment from parent's floating button
        triggerCreation: { type: Boolean, optional: true },
        // Optional callback to trigger when user clicks "เพิ่ม Comment" from floating button
        onCreateCommentFromSelection: { type: Function, optional: true },
        // Lifted state for comment body
        newCommentBody: { type: String, optional: true },
        onUpdateNewCommentBody: { type: Function, optional: true },
        onClearNewCommentBody: { type: Function, optional: true },
        // Callback to close comment panel
        onClose: { type: Function, optional: true },
        // Show comment panel flag - used to trigger re-load when panel opens
        showCommentPanel: { type: Boolean, optional: true },
        // Callback to open comment panel and select comment (called when clicking on highlight)
        onHighlightClick: { type: Function, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.overlayRef = useRef("overlay");
        this.commentListRef = useRef("commentList");
        this.commentInputRef = useRef("newCommentInput");
        
        this.commentManager = null;
        this.textSelectionHandler = null;
        this.currentSelection = null;
        this.overlayVisible = false;
        this._textareaHasFocus = false; // Track if textarea has focus to prevent unnecessary updates
        this._hideButtonTimer = null; // Timer for delayed hide
        this._preventHide = false; // Flag to prevent hiding button temporarily
        this._highlightObserver = null; // MutationObserver to watch for highlight removal
        this._highlightCheckInterval = null; // Interval to periodically check highlight visibility
        this._isSelecting = false; // Flag to track if user is currently selecting text
        this._selectionProcessTimer = null; // Timer to delay processing selection until user finishes dragging
        this._selectionStabilityCheckInterval = null; // Interval to check if selection has stabilized
        this._mousedownListener = null; // Listener for mousedown to detect start of selection
        this._mousemoveListener = null; // Listener for mousemove to detect active selection dragging
        this._lastHighlightRenderTime = 0; // Timestamp of last highlight render to prevent rapid re-renders

        this.state = useState({
            comments: [],
            selectedComment: null,
            isCreating: false,
            replyBody: "",
            replyingTo: null,
            showResolved: false,
            // Use state for textarea value - this is the Odoo 19/Owl best practice
            newCommentBody: "",
            currentUser: null, // Store current user info
        });
        
        // Keep minimal instance variables for cleanup
        this._textareaObserver = null;
        this._propagateDebounceTimer = null;

        onMounted(async () => {
            // Load current user info
            await this.loadCurrentUser();
            
            // Try to initialize with retry mechanism
            // This will wait for contentElement to be ready
            if (this.props.articleId) {
                this.initializeCommentSystemWithRetry();
            }
        });

        // Preserve textarea value before props update
        // This ensures textarea value is not lost when parent component re-renders
        onWillUpdateProps((nextProps) => {
            if (this.commentInputRef.el && this.state.isCreating) {
                const textarea = this.commentInputRef.el;
                
                // Check if textarea has focus (user is actively typing)
                const hasFocus = this._textareaHasFocus || (document.activeElement === textarea);
                
                // Store current value before update - CRITICAL: Always preserve DOM value
                if (textarea && textarea.value !== undefined && textarea.value !== null) {
                    const currentValue = textarea.value || '';
                    const currentStateValue = this.state.newCommentBody || '';
                    
                    // Only log if values differ significantly or if we're preserving non-empty value
                    if (currentValue !== currentStateValue || (currentValue.length > 0 && hasFocus)) {
                        logger.log('onWillUpdateProps: Preserving textarea value', {
                            domValue: currentValue,
                            stateValue: currentStateValue,
                            domLength: currentValue.length,
                            stateLength: currentStateValue.length,
                            hasFocus: hasFocus,
                            willUpdate: currentValue !== currentStateValue
                        });
                    }
                    
                    // CRITICAL: Always sync from DOM to state if DOM has value OR if user has focus
                    // This prevents state from being reset to empty while user is typing
                    if (hasFocus || currentValue.length > 0) {
                        // Preserve DOM value - don't let state override it
                        if (currentValue !== currentStateValue) {
                            this.state.newCommentBody = currentValue;
                        }
                    }
                    // If textarea is empty and doesn't have focus, allow state to be empty
                    // (but don't force it - preserve state if it has value)
                    else if (currentValue.length === 0 && currentStateValue.length > 0 && !hasFocus) {
                        // Don't override state with empty DOM value if state has value
                        // This happens when component re-renders before user types
                        logger.log('onWillUpdateProps: DOM is empty but state has value, preserving state', {
                            domValue: currentValue,
                            stateValue: currentStateValue
                        });
                    }
                }
            }
        });

        // Sync state from DOM after DOM patch (uncontrolled component pattern)
        // This ensures state stays in sync with DOM value when user is typing
        // CRITICAL: If DOM was reset to empty but state has value, restore DOM immediately
        // Use debounce to prevent excessive calls
        let _onPatchedTimeout = null;
        onPatched(() => {
            if (this.commentInputRef.el && this.state.isCreating) {
                const textarea = this.commentInputRef.el;
                const domValue = textarea.value || '';
                const stateValue = this.state.newCommentBody || '';
                
                // Clear any pending timeout
                if (_onPatchedTimeout) {
                    clearTimeout(_onPatchedTimeout);
                    _onPatchedTimeout = null;
                }
                
                // CRITICAL: If textarea has focus and DOM is empty but state has value,
                // this means DOM was reset during patch - restore it immediately!
                if ((this._textareaHasFocus || document.activeElement === textarea) && 
                    stateValue.length > 0 && domValue.length === 0) {
                    const cursorPos = textarea.selectionStart || stateValue.length;
                    logger.warn('onPatched: DOM was reset to empty while user is typing! Restoring from state', {
                        domValue: domValue,
                        stateValue: stateValue,
                        cursorPos: cursorPos
                    });
                    
                    // Strategy 1: Immediate restore (try first)
                    if (textarea && textarea.value !== stateValue) {
                        textarea.value = stateValue;
                        if (cursorPos >= 0 && cursorPos <= stateValue.length) {
                            textarea.setSelectionRange(cursorPos, cursorPos);
                        }
                    }
                    
                    // Strategy 2: requestAnimationFrame restore (after browser render)
                    requestAnimationFrame(() => {
                        if (this.commentInputRef.el && this.commentInputRef.el.value !== stateValue) {
                            this.commentInputRef.el.value = stateValue;
                            const currentCursorPos = this.commentInputRef.el.selectionStart || stateValue.length;
                            if (currentCursorPos >= 0 && currentCursorPos <= stateValue.length) {
                                this.commentInputRef.el.setSelectionRange(currentCursorPos, currentCursorPos);
                            }
                        }
                    });
                    
                    // Strategy 3: setTimeout restore (final backup)
                    setTimeout(() => {
                        if (this.commentInputRef.el && this.commentInputRef.el.value !== stateValue) {
                            this.commentInputRef.el.value = stateValue;
                            const currentCursorPos = this.commentInputRef.el.selectionStart || stateValue.length;
                            if (currentCursorPos >= 0 && currentCursorPos <= stateValue.length) {
                                this.commentInputRef.el.setSelectionRange(currentCursorPos, currentCursorPos);
                            }
                        }
                    }, 0);
                    
                    // Also sync state back from restored DOM
                    this.state.newCommentBody = stateValue;
                    return; // Don't sync state from empty DOM
                }
                
                // If textarea has focus, sync state from DOM (uncontrolled pattern)
                // DOM is the source of truth when user is actively typing OR deleting
                if (this._textareaHasFocus || document.activeElement === textarea) {
                    if (domValue !== stateValue) {
                        // Check if this looks like deletion (DOM shorter than state)
                        const isDeletion = domValue.length < stateValue.length;
                        
                        // Always trust DOM when user has focus - sync to state
                        // This includes both typing (DOM longer) and deleting (DOM shorter)
                        if (isDeletion) {
                            logger.log('onPatched: User is deleting, syncing DOM to state', {
                                domValue: domValue,
                                stateValue: stateValue,
                                domLength: domValue.length,
                                stateLength: stateValue.length
                            });
                        } else {
                            // Only log occasionally to reduce noise for typing
                            if (Math.random() < 0.1) { // Log only 10% of the time
                                logger.log('onPatched: User is typing, syncing state from DOM (uncontrolled)', {
                                    domValue: domValue,
                                    stateValue: stateValue,
                                    domLength: domValue.length,
                                    stateLength: stateValue.length
                                });
                            }
                        }
                        this.state.newCommentBody = domValue;
                    }
                    return; // Don't modify DOM when user is typing or deleting
                }
                
                // Only restore DOM from state if textarea doesn't have focus
                // and state has value but DOM is empty (unexpected reset)
                if (stateValue.length > 0 && domValue.length === 0) {
                    const cursorPos = textarea.selectionStart || stateValue.length;
                    logger.log('onPatched: State has value but DOM is empty (unexpected reset), restoring', {
                        domValue: domValue,
                        stateValue: stateValue,
                        cursorPos: cursorPos
                    });
                    requestAnimationFrame(() => {
                        if (this.commentInputRef.el && this.commentInputRef.el.value !== stateValue) {
                            this.commentInputRef.el.value = stateValue;
                            if (cursorPos >= 0 && cursorPos <= stateValue.length) {
                                this.commentInputRef.el.setSelectionRange(cursorPos, cursorPos);
                            }
                        }
                    });
                }
            }
        });

        onWillUnmount(() => {
            this.cleanup();
        });

        // Watch for articleId and contentElement changes - initialize comment system when both are ready
        useEffect(() => {
            const initializeWithRetry = async () => {
                if (!this.props.articleId) {
                    // Clear highlights if articleId is removed
                    if (this.commentManager) {
                        this.commentManager.clearAllHighlights();
                        this.commentManager = null;
                    }
                    return;
                }
                
                // Clear existing highlights before switching articles
                if (this.commentManager) {
                    this.commentManager.clearAllHighlights();
                    this.commentManager = null;
                }
                
                // Try to find content element with retry mechanism
                let contentElement = this.props.contentElement || 
                    document.querySelector('.o_knowledge_article_body');
                
                if (!contentElement) {
                    // Retry finding content element (DOM might not be ready yet)
                    logger.log('Content element not found, retrying...', {
                        articleId: this.props.articleId,
                        hasContentElementProp: !!this.props.contentElement
                    });
                    
                    // Retry up to 5 times with increasing delays
                    for (let attempt = 0; attempt < 5; attempt++) {
                        await new Promise(resolve => setTimeout(resolve, (attempt + 1) * 300));
                        contentElement = this.props.contentElement || 
                            document.querySelector('.o_knowledge_article_body');
                        
                        if (contentElement) {
                            logger.log(`Content element found on attempt ${attempt + 1}`, {
                                articleId: this.props.articleId
                            });
                            break;
                        }
                    }
                }
                
                if (contentElement && this.props.articleId) {
                    // Initialize comment system now that we have content element
                    await this.initializeCommentSystem();
                } else {
                    logger.warn('Cannot initialize comment system: content element not found after retries', {
                        articleId: this.props.articleId,
                        hasContentElementProp: !!this.props.contentElement
                    });
                }
            };
            
            initializeWithRetry();
        }, () => [this.props.articleId, this.props.contentElement]);

        // Watch for selection data from parent component
        useEffect(() => {
            if (this.props.selectionData && this.props.selectionData.text) {
                this.processParentSelection(this.props.selectionData);
            }
        }, () => [this.props.selectionData]);

        // Watch for trigger to create comment
        useEffect(() => {
            if (this.props.triggerCreation && this.currentSelection) {
                this.onCreateComment();
            }
        }, () => [this.props.triggerCreation]);

        // Listen for highlight click events to select comment
        useEffect(() => {
            const handleHighlightClick = (event) => {
                const commentId = event.detail && event.detail.commentId;
                if (commentId) {
                    logger.log('Received highlight click event, selecting comment:', {
                        commentId: commentId,
                        showCommentPanel: this.props.showCommentPanel
                    });
                    
                    // Wait a bit for comments to be loaded and panel to be visible
                    setTimeout(() => {
                        this.onSelectComment(commentId);
                    }, 300);
                }
            };
            
            document.addEventListener('highlight-comment-clicked', handleHighlightClick);
            
            return () => {
                document.removeEventListener('highlight-comment-clicked', handleHighlightClick);
            };
        }, () => [this.props.showCommentPanel, this.state.comments]);

        // Watch for comment panel visibility - re-load comments when panel opens
        useEffect(() => {
            const showPanel = this.props.showCommentPanel;
            logger.log('Comment panel visibility effect triggered:', {
                showCommentPanel: showPanel,
                showCommentPanelType: typeof showPanel,
                articleId: this.props.articleId,
                commentManagerExists: !!this.commentManager,
                currentCommentsCount: this.state.comments && this.state.comments.length ? this.state.comments.length : 0,
                wrapperElement: !!document.querySelector('.o_knowledge_comment_overlay_wrapper'),
                hiddenClassApplied: (() => {
                    const wrapper = document.querySelector('.o_knowledge_comment_overlay_wrapper');
                    return wrapper && wrapper.classList ? wrapper.classList.contains('o_knowledge_comment_overlay_hidden') : false;
                })()
            });
            
            // Always ensure comments are loaded when panel becomes visible
            if (showPanel) {
                logger.log('Comment panel opened - ensuring comments are loaded:', {
                    showCommentPanel: showPanel,
                    articleId: this.props.articleId,
                    commentManagerExists: !!this.commentManager,
                    currentCommentsCount: this.state.comments && this.state.comments.length ? this.state.comments.length : 0
                });
                
                // If comment manager exists, load comments
                if (this.commentManager) {
                    // Use setTimeout to ensure DOM is ready
                    setTimeout(() => {
                        this.loadComments().catch(error => {
                            logger.warn('Error re-loading comments when panel opened:', error);
                        });
                    }, 100);
                } else if (this.props.articleId) {
                    // If comment manager doesn't exist but we have articleId, initialize first
                    logger.warn('Comment manager not found, initializing comment system');
                    this.initializeCommentSystem().then(() => {
                        if (this.commentManager) {
                            setTimeout(() => {
                                this.loadComments().catch(error => {
                                    logger.warn('Error loading comments after initialization:', error);
                                });
                            }, 200);
                        }
                    }).catch(error => {
                        logger.error('Error initializing comment system when panel opened:', error);
                    });
                }
                
                // Force a render to ensure CSS classes are updated
                setTimeout(() => {
                    this.render();
                    
                    // Also manually remove the hidden class if it's still applied
                    const wrapper = document.querySelector('.o_knowledge_comment_overlay_wrapper');
                    if (wrapper && wrapper.classList.contains('o_knowledge_comment_overlay_hidden')) {
                        logger.warn('Hidden class still applied after render, removing manually');
                        wrapper.classList.remove('o_knowledge_comment_overlay_hidden');
                    }
                    
                    logger.log('Forced re-render after panel opened', {
                        showCommentPanel: this.props.showCommentPanel,
                        hiddenClassRemoved: wrapper && !wrapper.classList.contains('o_knowledge_comment_overlay_hidden')
                    });
                }, 150);
            }
        }, () => [this.props.showCommentPanel, this.props.articleId]);

        // Setup textarea monitoring to track value changes
        // This helps us debug why text disappears
        useEffect(() => {
            if (this.commentInputRef.el && this.state.isCreating) {
                const textarea = this.commentInputRef.el;
                
                // Monitor input events and sync to state
                // CRITICAL: This must run BEFORE any other code that might reset the value
                const handleInput = (e) => {
                    const newValue = e.target.value || '';
                    const oldStateValue = this.state.newCommentBody || '';
                    
                    logger.log('Textarea input event (handleInput):', {
                        value: newValue,
                        valueLength: newValue.length,
                        stateValue: oldStateValue,
                        stateLength: oldStateValue.length,
                        cursorPos: e.target.selectionStart,
                        willSync: newValue !== oldStateValue
                    });
                    
                    // CRITICAL: Sync immediately (don't wait)
                    if (newValue.length > 0 || oldStateValue.length > 0) {
                        logger.log('Syncing DOM value to state (handleInput - immediate):', {
                            domValue: newValue,
                            oldStateValue: oldStateValue,
                            domLength: newValue.length,
                            stateLength: oldStateValue.length
                        });
                        this.state.newCommentBody = newValue;
                    }
                    
                    // Also use requestAnimationFrame to ensure sync happens before re-render
                    requestAnimationFrame(() => {
                        // Double-check DOM value hasn't been reset
                        if (e.target && e.target.value !== undefined) {
                            const currentDomValue = e.target.value || '';
                            if (currentDomValue !== this.state.newCommentBody) {
                                // Check if this looks like user deletion vs unexpected reset
                                // User deletion: DOM value is a prefix of state value OR shorter
                                // Unexpected reset: DOM value is completely different or empty when state has value
                                const isLikelyDeletion = currentDomValue.length <= this.state.newCommentBody.length &&
                                                         (currentDomValue === '' || 
                                                          this.state.newCommentBody.startsWith(currentDomValue) ||
                                                          currentDomValue.length < this.state.newCommentBody.length - 1);
                                
                                if (this.state.newCommentBody.length > 0 && currentDomValue.length < this.state.newCommentBody.length) {
                                    if (isLikelyDeletion) {
                                        // User is deleting - trust DOM and sync to state
                                        logger.log('handleInput (RAF): User deletion detected, syncing DOM to state', {
                                            domValue: currentDomValue,
                                            stateValue: this.state.newCommentBody,
                                            domLength: currentDomValue.length,
                                            stateLength: this.state.newCommentBody.length
                                        });
                                        this.state.newCommentBody = currentDomValue;
                                    } else {
                                        // Unexpected reset - restore from state
                                        logger.warn('handleInput (RAF): DOM value was reset (not deletion), restoring from state', {
                                            domValue: currentDomValue,
                                            stateValue: this.state.newCommentBody,
                                            isLikelyDeletion: isLikelyDeletion
                                        });
                                        e.target.value = this.state.newCommentBody;
                                        const cursorPos = e.target.selectionStart || this.state.newCommentBody.length;
                                        if (cursorPos >= 0 && cursorPos <= this.state.newCommentBody.length) {
                                            e.target.setSelectionRange(cursorPos, cursorPos);
                                        }
                                    }
                                } else {
                                    // DOM value increased or stayed same (user typed more), sync to state
                                    logger.log('handleInput (RAF): DOM value changed (typing), syncing to state', {
                                        domValue: currentDomValue,
                                        stateValue: this.state.newCommentBody
                                    });
                                    this.state.newCommentBody = currentDomValue;
                                }
                            }
                        }
                    });
                };
                
                // Track last input type to detect deletions
                let lastInputType = null;
                
                // Monitor beforeinput to catch value resets
                const handleBeforeInput = (e) => {
                    // Store input type to help detect if user is deleting
                    lastInputType = e.inputType;
                    logger.log('Textarea beforeinput event:', {
                        inputType: e.inputType,
                        data: e.data,
                        currentValue: e.target.value,
                        currentLength: e.target.value.length
                    });
                    // CRITICAL: Never preventDefault() - allow all input operations including delete
                };
                
                // Monitor property changes (if textarea.value is set directly)
                let lastValue = textarea.value;
                const valueObserver = new MutationObserver(() => {
                    if (textarea.value !== lastValue) {
                        const newValue = textarea.value || '';
                        const oldValue = lastValue || '';
                        
                        // Check if this looks like user deletion
                        const isDeletion = newValue.length < oldValue.length && 
                                          (newValue === '' || oldValue.startsWith(newValue) || 
                                           newValue.length < oldValue.length - 1);
                        
                        // Check if textarea has focus (user is actively editing)
                        const hasFocus = this._textareaHasFocus || (document.activeElement === textarea);
                        
                        logger.warn('Textarea value changed via DOM mutation:', {
                            oldValue: oldValue,
                            newValue: newValue,
                            oldLength: oldValue.length,
                            newLength: newValue.length,
                            stateValue: this.state.newCommentBody,
                            stateLength: this.state.newCommentBody && this.state.newCommentBody.length ? this.state.newCommentBody.length : 0,
                            isDeletion: isDeletion,
                            hasFocus: hasFocus,
                            lastInputType: lastInputType
                        });
                        
                        lastValue = newValue;
                        
                        // Only restore if:
                        // 1. This doesn't look like user deletion AND
                        // 2. Value doesn't match state AND
                        // 3. User doesn't have focus (not actively editing) OR value is completely wrong
                        if (this.state.newCommentBody && newValue !== this.state.newCommentBody) {
                            if (isDeletion && hasFocus) {
                                // User is deleting - trust DOM and sync to state
                                logger.log('MutationObserver: User deletion detected, syncing DOM to state', {
                                    domValue: newValue,
                                    stateValue: this.state.newCommentBody
                                });
                                this.state.newCommentBody = newValue;
                            } else if (!hasFocus || (newValue === '' && this.state.newCommentBody.length > 0 && !isDeletion)) {
                                // Unexpected reset (not deletion) - restore it
                                logger.warn('Restoring textarea value after unexpected reset (not deletion)');
                                const cursorPos = textarea.selectionStart || this.state.newCommentBody.length;
                                textarea.value = this.state.newCommentBody;
                                if (cursorPos >= 0 && cursorPos <= this.state.newCommentBody.length) {
                                    textarea.setSelectionRange(cursorPos, cursorPos);
                                }
                            }
                        }
                    }
                });
                
                // Observe value attribute changes
                valueObserver.observe(textarea, {
                    attributes: true,
                    attributeFilter: ['value'],
                    childList: false,
                    characterData: true,
                    subtree: true
                });
                
                // Also check value periodically as fallback (VERY aggressive)
                // This is our last line of defense against value resets
                let lastKnownValue = textarea.value || '';
                const valueCheckInterval = setInterval(() => {
                    if (!textarea || !this.state.isCreating) {
                        clearInterval(valueCheckInterval);
                        return;
                    }
                    
                    const domValue = textarea.value || '';
                    const stateValue = this.state.newCommentBody || '';
                    
                    // If user is typing and DOM is empty but state has value, restore immediately
                    if ((this._textareaHasFocus || document.activeElement === textarea) &&
                        stateValue.length > 0 && domValue.length === 0) {
                        logger.warn('Periodic check: DOM was reset to empty, restoring from state', {
                            domValue: domValue,
                            stateValue: stateValue,
                            lastKnownValue: lastKnownValue
                        });
                        const cursorPos = textarea.selectionStart || stateValue.length;
                        textarea.value = stateValue;
                        if (cursorPos >= 0 && cursorPos <= stateValue.length) {
                            textarea.setSelectionRange(cursorPos, cursorPos);
                        }
                        lastKnownValue = stateValue;
                    }
                    // If DOM value decreased, check if it's user deletion vs unexpected reset
                    else if (lastKnownValue.length > 0 && domValue.length < lastKnownValue.length) {
                        const hasFocus = this._textareaHasFocus || (document.activeElement === textarea);
                        
                        // Check if this looks like user deletion
                        // User deletion: DOM value is a prefix of lastKnownValue OR shorter by a few chars
                        const isLikelyDeletion = hasFocus && 
                                                 (domValue === '' || 
                                                  lastKnownValue.startsWith(domValue) ||
                                                  (lastKnownValue.length - domValue.length <= 5)); // Allow up to 5 chars deleted
                        
                        // Also check if lastInputType indicates deletion
                        const isDeletionInput = lastInputType === 'deleteContentBackward' || 
                                               lastInputType === 'deleteContentForward' ||
                                               lastInputType === 'deleteWordBackward' ||
                                               lastInputType === 'deleteWordForward';
                        
                        if (isLikelyDeletion || isDeletionInput) {
                            // User is deleting - trust DOM and sync to state
                            logger.log('Periodic check: User deletion detected, syncing DOM to state', {
                                domValue: domValue,
                                stateValue: stateValue,
                                lastKnownValue: lastKnownValue,
                                hasFocus: hasFocus,
                                isLikelyDeletion: isLikelyDeletion,
                                isDeletionInput: isDeletionInput,
                                lastInputType: lastInputType
                            });
                            // Sync DOM to state
                            this.state.newCommentBody = domValue;
                            lastKnownValue = domValue; // Update lastKnownValue to current DOM
                        } else if (!hasFocus) {
                            // No focus - might be unexpected reset, restore it
                            logger.warn('Periodic check: DOM value decreased (no focus), restoring from last known', {
                                domValue: domValue,
                                lastKnownValue: lastKnownValue,
                                stateValue: stateValue,
                                hasFocus: hasFocus
                            });
                            const cursorPos = textarea.selectionStart || lastKnownValue.length;
                            textarea.value = lastKnownValue;
                            this.state.newCommentBody = lastKnownValue;
                            if (cursorPos >= 0 && cursorPos <= lastKnownValue.length) {
                                textarea.setSelectionRange(cursorPos, cursorPos);
                            }
                        } else {
                            // Has focus but doesn't look like deletion - trust DOM anyway (user might be doing something)
                            logger.log('Periodic check: DOM value decreased but user has focus, syncing DOM to state', {
                                domValue: domValue,
                                stateValue: stateValue,
                                lastKnownValue: lastKnownValue,
                                hasFocus: hasFocus
                            });
                            this.state.newCommentBody = domValue;
                            lastKnownValue = domValue;
                        }
                    }
                    // If values don't match, sync to state (prefer DOM when user is typing)
                    else if (domValue !== stateValue) {
                        if (this._textareaHasFocus || document.activeElement === textarea) {
                            // User is typing - DOM is source of truth
                            if (domValue.length > 0) {
                                this.state.newCommentBody = domValue;
                                lastKnownValue = domValue; // Update last known value
                            }
                        } else if (stateValue.length > 0 && domValue.length === 0) {
                            // DOM was reset - restore from state
                            const cursorPos = textarea.selectionStart || stateValue.length;
                            textarea.value = stateValue;
                            lastKnownValue = stateValue;
                            if (cursorPos >= 0 && cursorPos <= stateValue.length) {
                                textarea.setSelectionRange(cursorPos, cursorPos);
                            }
                        }
                    } else if (domValue.length > 0) {
                        // Update last known value if DOM has value
                        lastKnownValue = domValue;
                    }
                }, 30); // Check every 30ms (VERY aggressive - last line of defense)
                
                textarea.addEventListener('input', handleInput, { capture: true });
                textarea.addEventListener('beforeinput', handleBeforeInput, { capture: true });
                
                // Store cleanup functions
                this._textareaInputHandler = handleInput;
                this._textareaBeforeInputHandler = handleBeforeInput;
                this._textareaValueObserver = valueObserver;
                this._textareaValueCheckInterval = valueCheckInterval;
                
                return () => {
                    textarea.removeEventListener('input', handleInput, { capture: true });
                    textarea.removeEventListener('beforeinput', handleBeforeInput, { capture: true });
                    valueObserver.disconnect();
                    clearInterval(valueCheckInterval);
                };
            }
        }, () => [this.state.isCreating, this.commentInputRef.el]);

    }

    /**
     * According to Odoo 19/Owl best practices:
     * Prevent unnecessary re-renders when user is typing in textarea
     * This prevents Owl from resetting the textarea value
     */
    /**
     * Prevent unnecessary re-renders when user is typing in textarea
     * According to Odoo 19/Owl best practices
     * 
     * CRITICAL: When user is typing, we MUST allow update if newCommentBody changed
     * (to let t-model sync), but prevent update if only props changed
     */
    shouldUpdate(nextProps, nextState) {
        // Check if user is actively typing in textarea
        const isTyping = this.state.isCreating && (
            this._textareaHasFocus || 
            (this.commentInputRef.el && document.activeElement === this.commentInputRef.el)
        );
        
        if (isTyping) {
            // CRITICAL: If user is typing, prevent ALL re-renders unless absolutely necessary
            // This prevents Owl from resetting the textarea value
            
            // Check DOM value directly (uncontrolled component - DOM is source of truth)
            const currentDomValue = this.commentInputRef.el ? this.commentInputRef.el.value || '' : '';
            const currentStateValue = this.state.newCommentBody || '';
            const nextStateValue = nextState.newCommentBody || '';
            
            // Only allow update if:
            // 1. newCommentBody changed AND it matches DOM value (user typed something)
            // 2. Critical props changed (articleId)
            // 3. Critical state changed (isCreating, selectedComment, etc.)
            
            const newCommentBodyChanged = nextStateValue !== currentStateValue;
            const criticalPropsChanged = nextProps.articleId !== this.props.articleId;
            const criticalStateChanged = (
                nextState.selectedComment !== this.state.selectedComment ||
                nextState.replyingTo !== this.state.replyingTo ||
                nextState.showResolved !== this.state.showResolved ||
                nextState.isCreating !== this.state.isCreating
            );
            
            // Allow update only if newCommentBody changed AND it matches DOM (user typed)
            if (newCommentBodyChanged && nextStateValue === currentDomValue) {
                logger.log('shouldUpdate: Allowing update (newCommentBody matches DOM - user typed)', {
                    domValue: currentDomValue,
                    oldStateValue: currentStateValue,
                    newStateValue: nextStateValue
                });
                return true;
            }
            
            // Allow update if critical props/state changed
            if (criticalPropsChanged || criticalStateChanged) {
                logger.log('shouldUpdate: Allowing update (critical props/state changed)', {
                    criticalPropsChanged,
                    criticalStateChanged
                });
                return true;
            }
            
            // BLOCK all other updates when user is typing
            // This is critical to prevent textarea value from being reset
            logger.log('shouldUpdate: BLOCKING update (user typing, preventing re-render)', {
                currentBodyLength: currentStateValue.length,
                domValueLength: currentDomValue.length,
                newBodyLength: nextStateValue.length,
                propsChanged: nextProps !== this.props,
                stateChanged: nextState !== this.state
            });
            return false;
        }
        
        // Allow normal updates when not typing
        return true;
    }

    /**
     * Process selection data from parent component
     * Convert parent's selection format to CommentOverlay's format
     */
    processParentSelection(parentSelection) {
        if (!parentSelection || !parentSelection.text) {
            return;
        }

        const selectedText = parentSelection.text.trim();
        if (!selectedText) {
            return;
        }

        // Get content element
        const contentElement = this.props.contentElement || 
            document.querySelector('.o_knowledge_article_body');
        
        if (!contentElement) {
            logger.warn('Content element not found for processing parent selection');
            return;
        }

        // Initialize textSelectionHandler if not already done
        if (!this.textSelectionHandler) {
            this.textSelectionHandler = new TextSelectionHandler(contentElement);
        }

        // Try to get range from parent selection or from highlight span
        let range = null;
        if (parentSelection.range && parentSelection.range.startContainer) {
            range = parentSelection.range.cloneRange();
        } else {
            // Try to recreate range from highlight span
            const highlightSpan = document.querySelector('.o_knowledge_comment_temp_highlight');
            if (highlightSpan && highlightSpan.parentNode) {
                range = document.createRange();
                range.selectNodeContents(highlightSpan);
            }
        }

        if (!range) {
            logger.warn('Could not get valid range for parent selection');
            return;
        }

        // Guard: ลบ temp highlight เก่าที่อาจค้างใน DOM เพื่อลดการซ้อน
        document.querySelectorAll('.o_knowledge_comment_temp_highlight').forEach(el => {
            el.replaceWith(...el.childNodes);
        });

        // Calculate offsets using TextSelectionHandler
        let startOffset = 0;
        let endOffset = 0;
        let elementSelector = '';

        try {
            startOffset = this.textSelectionHandler.getTextOffset(
                contentElement, range.startContainer, range.startOffset
            );
            endOffset = this.textSelectionHandler.getTextOffset(
                contentElement, range.endContainer, range.endOffset
            );
            elementSelector = this.textSelectionHandler.getElementSelector(
                range.commonAncestorContainer
            );
            
            // Validate offsets - if they're equal but we have text, recalculate
            if (startOffset === endOffset && selectedText && selectedText.trim().length > 0) {
                logger.warn('Offsets are equal but text exists, recalculating using fallback');
                const plainText = this.textSelectionHandler.getPlainText(contentElement);
                
                // Try to find the selected text starting from the calculated offset
                const searchStart = Math.max(0, startOffset - 100); // Search 100 chars before
                const searchEnd = Math.min(plainText.length, startOffset + selectedText.length + 100); // Search 100 chars after
                const searchText = plainText.substring(searchStart, searchEnd);
                const relativeIndex = searchText.indexOf(selectedText.trim());
                
                if (relativeIndex >= 0) {
                    startOffset = searchStart + relativeIndex;
                    endOffset = startOffset + selectedText.trim().length;
                    logger.log('Recalculated offsets using fallback:', { startOffset, endOffset, selectedText: selectedText.trim() });
                } else {
                    // Last resort: use indexOf on full text
                    const fullIndex = plainText.indexOf(selectedText.trim());
                    if (fullIndex >= 0) {
                        startOffset = fullIndex;
                        endOffset = startOffset + selectedText.trim().length;
                        logger.log('Recalculated offsets using full text search:', { startOffset, endOffset });
                    } else {
                        // If we can't find the text, use a reasonable fallback
                        endOffset = startOffset + selectedText.trim().length;
                        logger.warn('Could not find selected text in content, using estimated endOffset:', { startOffset, endOffset, selectedText: selectedText.trim() });
                    }
                }
            }
        } catch (error) {
            logger.error('Error calculating offsets:', error);
            // Fallback: use simple offsets
            const plainText = this.textSelectionHandler.getPlainText(contentElement);
            const index = plainText.indexOf(selectedText.trim());
            if (index >= 0) {
                startOffset = index;
                endOffset = startOffset + selectedText.trim().length;
            } else {
                // Last resort: estimate based on text length
                startOffset = 0;
                endOffset = selectedText.trim().length;
                logger.warn('Could not find selected text, using estimated offsets:', { startOffset, endOffset });
            }
        }

        // Store selection in CommentOverlay format
        this.currentSelection = {
            text: selectedText,
            startOffset,
            endOffset,
            elementSelector,
            range: range.cloneRange(),
            startContainer: range.startContainer,
            startOffset_node: range.startOffset,
            endContainer: range.endContainer,
            endOffset_node: range.endOffset,
        };

        logger.log('Parent selection processed:', {
            text: selectedText,
            startOffset,
            endOffset,
            elementSelector
        });
    }

    /**
     * Initialize comment system
     */
    /**
     * Initialize comment system with retry mechanism
     * This ensures contentElement is ready before initializing
     */
    async initializeCommentSystemWithRetry(maxRetries = 5, delay = 500) {
        for (let attempt = 0; attempt < maxRetries; attempt++) {
            const contentElement = this.props.contentElement || 
                document.querySelector('.o_knowledge_article_body');
            
            if (contentElement) {
                logger.log(`Content element found on attempt ${attempt + 1}, initializing comment system`, {
                    articleId: this.props.articleId,
                    hasContentElementProp: !!this.props.contentElement
                });
                await this.initializeCommentSystem();
                return; // Success - exit retry loop
            }
            
            if (attempt < maxRetries - 1) {
                logger.log(`Content element not found (attempt ${attempt + 1}/${maxRetries}), retrying in ${delay}ms...`, {
                    articleId: this.props.articleId,
                    hasContentElementProp: !!this.props.contentElement
                });
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
        
        logger.warn('Content element not found after all retries', {
            articleId: this.props.articleId,
            maxRetries: maxRetries,
            hasContentElementProp: !!this.props.contentElement
        });
    }

    async initializeCommentSystem() {
        const contentElement = this.props.contentElement || 
            document.querySelector('.o_knowledge_article_body');
        
        if (!contentElement) {
            logger.warn('Content element not found for comments', {
                articleId: this.props.articleId,
                hasContentElementProp: !!this.props.contentElement,
                contentElementQuery: document.querySelector('.o_knowledge_article_body') ? 'found' : 'not found'
            });
            return;
        }

        // Cleanup existing text selection handler
        if (this.textSelectionHandler) {
            this.textSelectionHandler.cleanup();
            this.textSelectionHandler = null;
        }

        // Cleanup existing comment manager (clear highlights from previous article)
        if (this.commentManager) {
            this.commentManager.clearAllHighlights();
            this.commentManager = null;
        }

        this.textSelectionHandler = new TextSelectionHandler(contentElement);
        
        if (this.props.articleId) {
            // Create callback function to handle highlight clicks
            const onHighlightClick = (commentId) => {
                logger.log('Highlight clicked - opening comment panel and selecting comment:', {
                    commentId: commentId,
                    currentShowCommentPanel: this.props.showCommentPanel
                });
                
                // If callback prop is provided, use it (allows parent to control panel opening)
                if (this.props.onHighlightClick) {
                    this.props.onHighlightClick(commentId);
                } else {
                    // Fallback: Select comment in current panel
                    // Note: Panel should already be open, but if not, this won't open it
                    this.onSelectComment(commentId);
                }
            };
            
            this.commentManager = new CommentManager(
                this.orm,
                this.props.articleId,
                contentElement,
                onHighlightClick
            );

            // Wait for content to be fully rendered in DOM before loading comments
            // This ensures highlights can be properly rendered
            await new Promise(resolve => {
                requestAnimationFrame(() => {
                    requestAnimationFrame(() => {
                        resolve();
                    });
                });
            });
            
            // Load existing comments (this will automatically render highlights)
            // IMPORTANT: This should render highlights even if comment panel is not open
            await this.loadComments();
            
            // Force render highlights immediately after loading comments
            // This ensures highlights are visible even when comment panel is closed
            if (this.commentManager) {
                try {
                    this._lastHighlightRenderTime = Date.now();
                    await this.commentManager.renderHighlights();
                    logger.log('Highlights rendered immediately after loading comments', {
                        articleId: this.props.articleId,
                        showCommentPanel: this.props.showCommentPanel,
                        highlightsCount: this.commentManager.highlights.size,
                        commentsCount: this.commentManager.comments.length
                    });
                } catch (error) {
                    logger.warn('Error rendering highlights immediately after load:', error);
                }
            }
            
            // Ensure comments are loaded even if initial load failed or returned empty
            // Double-check by re-loading after a short delay
            setTimeout(async () => {
                if (this.commentManager && this.props.articleId) {
                    // Check if comments were actually loaded
                    const currentCount = this.state.comments && this.state.comments.length ? this.state.comments.length : 0;
                    if (currentCount === 0) {
                        logger.warn('No comments found after initial load, attempting to reload', {
                            articleId: this.props.articleId,
                            commentManagerExists: !!this.commentManager
                        });
                        await this.loadComments();
                        // Re-render highlights after reload
                        if (this.commentManager) {
                            try {
                                this._lastHighlightRenderTime = Date.now();
                                await this.commentManager.renderHighlights();
                                logger.log('Highlights re-rendered after reload', {
                                    highlightsCount: this.commentManager.highlights.size
                                });
                            } catch (error) {
                                logger.warn('Error re-rendering highlights after reload:', error);
                            }
                        }
                    }
                }
            }, 300);
            
            // REMOVED: Additional setTimeout render - causes infinite loop
            // Highlights should already be rendered by loadComments() above
            // Only re-render if explicitly needed (e.g., after content change)
            
            // REMOVED: Additional render after longer delay - causes infinite loop
            // Highlights should already be rendered by loadComments() above
            // Only re-render if explicitly needed, not automatically

            // Setup text selection listener
            this.setupSelectionListener(contentElement);
            
            // Setup MutationObserver to watch for highlight removal
            this.setupHighlightObserver(contentElement);

            // Observe content changes to replay highlights if DOM re-renders
            this.setupContentRenderObserver(contentElement);
            
            logger.log('Comment system initialized for article:', {
                articleId: this.props.articleId,
                commentsCount: this.commentManager ? this.commentManager.comments.length : 0
            });
        }
    }

    /**
     * Setup MutationObserver to watch for highlight removal and restore it
     */
    setupHighlightObserver(contentElement) {
        // Cleanup existing observer
        if (this._highlightObserver) {
            this._highlightObserver.disconnect();
            this._highlightObserver = null;
        }
        
        // Use debounced observer to prevent flickering
        let observerTimeout = null;
        
        this._highlightObserver = new MutationObserver((mutations) => {
            // Debounce observer callbacks to prevent flickering
            if (observerTimeout) {
                clearTimeout(observerTimeout);
            }
            
            observerTimeout = setTimeout(() => {
                // Only check if temp highlight was removed (not style changes)
                if (this.textSelectionHandler && this.textSelectionHandler.tempHighlight) {
                    const tempHighlight = this.textSelectionHandler.tempHighlight;
                    
                    // Only restore if highlight was completely removed from DOM
                    if (!tempHighlight.parentNode || !contentElement.contains(tempHighlight)) {
                        // Highlight was removed, restore it immediately if we have current selection
                        if (this.currentSelection && this.currentSelection.range && !this.state.isCreating) {
                            logger.warn('Temp highlight removed (detected by MutationObserver), restoring immediately...');
                            // Re-apply highlight immediately
                            this.textSelectionHandler.applyTempHighlight(this.currentSelection.range);
                            
                            // Re-show button
                            requestAnimationFrame(() => {
                                this.showCommentButton(this.currentSelection);
                            });
                        }
                    }
                    // Don't check visibility on every mutation - it causes flickering
                    // Style changes (like hover) are normal and shouldn't trigger restoration
                }
            }, 100); // Debounce for 100ms
        });
        
        // Observe content element for child list changes only (not subtree or attributes)
        // This prevents flickering from style changes on hover
        this._highlightObserver.observe(contentElement, {
            childList: true,
            subtree: false, // Don't observe subtree - it causes flickering on hover
            attributes: false, // Don't observe attributes - style changes are normal
            characterData: false // Don't observe text changes
        });
    }

    /**
     * Observe content DOM updates (re-render) and replay highlights
     */
    setupContentRenderObserver(contentElement) {
        if (this._contentObserver) {
            this._contentObserver.disconnect();
            this._contentObserver = null;
        }

        let rerenderTimeout = null;
        const scheduleRerender = () => {
            if (rerenderTimeout) {
                clearTimeout(rerenderTimeout);
            }
            rerenderTimeout = setTimeout(async () => {
                if (this.commentManager) {
                    // CRITICAL: Prevent infinite loop - check if already rendering
                    if (this.commentManager._isRenderingHighlights) {
                        logger.log('Skipping highlight re-render: already rendering (preventing infinite loop)');
                        return;
                    }
                    
                    // CRITICAL: Cooldown period - don't re-render if we just rendered recently (within 3 seconds)
                    const now = Date.now();
                    const timeSinceLastRender = now - this._lastHighlightRenderTime;
                    if (timeSinceLastRender < 3000) {
                        logger.log('Skipping highlight re-render: cooldown period active', {
                            timeSinceLastRender: timeSinceLastRender,
                            cooldownRemaining: 3000 - timeSinceLastRender
                        });
                        return;
                    }
                    
                    // Check if we have a temp highlight - if so, don't re-render highlights
                    // as it might remove the temp highlight
                    const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
                    if (tempHighlight && tempHighlight.parentNode) {
                        logger.log('Skipping highlight re-render: temp highlight exists', {
                            hasTempHighlight: true,
                            highlightInDOM: !!tempHighlight.parentNode
                        });
                        return; // Don't re-render if temp highlight exists
                    }
                    
                    // Check if highlights are already present - don't re-render unnecessarily
                    const unresolvedComments = this.commentManager.comments.filter(c => !c.resolved);
                    if (unresolvedComments.length === 0) {
                        // No unresolved comments - nothing to render
                        return;
                    }
                    
                    // Verify each highlight is actually in DOM (not just in map)
                    let allHighlightsPresent = true;
                    for (const comment of unresolvedComments) {
                        const highlightInDOM = this.commentManager.contentElement.querySelector(
                            `.o_knowledge_comment_highlight[data-comment-id="${comment.id}"]`
                        );
                        if (!highlightInDOM) {
                            allHighlightsPresent = false;
                            break;
                        }
                    }
                    
                    if (allHighlightsPresent) {
                        // All highlights are present - no need to re-render
                        logger.log('Skipping highlight re-render: all highlights already present in DOM', {
                            unresolvedCount: unresolvedComments.length
                        });
                        return;
                    }
                    
                    try {
                        // CRITICAL: Disconnect observer temporarily to prevent infinite loop
                        if (this._contentObserver) {
                            this._contentObserver.disconnect();
                        }
                        
                        // Update timestamp before rendering
                        this._lastHighlightRenderTime = Date.now();
                        await this.commentManager.renderHighlights();
                        logger.log('Highlights re-rendered after content change');
                        
                        // Reconnect observer after a delay
                        setTimeout(() => {
                            if (this._contentObserver && this.commentManager && this.commentManager.contentElement) {
                                this._contentObserver.observe(this.commentManager.contentElement, {
                                    childList: true,
                                    subtree: true
                                });
                            }
                        }, 2000); // Reconnect after 2 seconds
                    } catch (error) {
                        logger.warn('Failed to re-render highlights after content change', error);
                        // Reset timestamp on error so we can try again
                        this._lastHighlightRenderTime = 0;
                        
                        // Reconnect observer on error
                        if (this._contentObserver && this.commentManager && this.commentManager.contentElement) {
                            this._contentObserver.observe(this.commentManager.contentElement, {
                                childList: true,
                                subtree: true
                            });
                        }
                    }
                }
            }, 1500); // Increased delay to reduce frequency of re-renders
        };

        this._contentObserver = new MutationObserver(() => {
            scheduleRerender();
        });

        this._contentObserver.observe(contentElement, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Verify and restore highlight immediately after showing button
     * This is called right after showCommentButton to catch immediate removals
     */
    _verifyAndRestoreHighlight(selection) {
        if (!this.textSelectionHandler || !selection) return;
        
        const tempHighlight = this.textSelectionHandler.tempHighlight;
        
        // If no highlight exists, don't restore immediately if range was already used
        // After extractContents(), the original range is collapsed and cannot be reused
        if (!tempHighlight) {
            logger.warn('Temp highlight missing after showing button');
            
            // Only restore if we have a valid selection with text
            // Don't restore if range was already used (would result in empty highlight)
            if (selection && selection.text && selection.text.trim().length > 0) {
                // Check if we still have a valid selection in the DOM
                const currentSelection = window.getSelection();
                if (currentSelection && currentSelection.rangeCount > 0) {
                    try {
                        const currentRange = currentSelection.getRangeAt(0);
                        const currentText = currentRange.toString().trim();
                        // Only restore if current selection matches our stored selection
                        if (currentText === selection.text.trim() && currentText.length > 0) {
                            logger.log('Restoring highlight from current selection...');
                            this.textSelectionHandler.applyTempHighlight(currentRange);
                            requestAnimationFrame(() => {
                                this.showCommentButton(selection);
                            });
                        } else {
                            logger.warn('Cannot restore: selection changed or empty', {
                                storedText: selection.text.trim(),
                                currentText: currentText,
                                storedLength: selection.text.trim().length,
                                currentLength: currentText.length
                            });
                        }
                    } catch (e) {
                        logger.error('Error restoring highlight from selection:', e);
                    }
                } else {
                    logger.warn('Cannot restore: no active selection available');
                }
            } else {
                logger.warn('Cannot restore: selection has no text content');
            }
            return;
        }
        
        // Check if highlight is in DOM
        if (!tempHighlight.parentNode) {
            logger.warn('Temp highlight removed from DOM');
            // Don't try to restore if range was already used - would create empty highlight
            return;
        }
        
        // Check if highlight has content
        const highlightText = tempHighlight.textContent || tempHighlight.innerText || '';
        if (!highlightText.trim()) {
            logger.warn('Temp highlight exists but has no content');
            // Clear empty highlight
            if (tempHighlight.parentNode) {
                tempHighlight.parentNode.removeChild(tempHighlight);
            }
            this.textSelectionHandler.tempHighlight = null;
            return;
        }
        
        // Check if highlight is visible
        try {
            const rect = tempHighlight.getBoundingClientRect();
            const computedStyle = window.getComputedStyle(tempHighlight);
            
            // If highlight has zero size or is hidden, restore styles only
            if ((rect.width === 0 && rect.height === 0) || 
                computedStyle.display === 'none' ||
                computedStyle.visibility === 'hidden') {
                logger.warn('Temp highlight not visible, restoring styles...');
                
                // Force restore styles immediately
                tempHighlight.style.setProperty('background-color', '#ffeb3b', 'important');
                tempHighlight.style.setProperty('display', 'inline', 'important');
                tempHighlight.style.setProperty('visibility', 'visible', 'important');
                tempHighlight.style.setProperty('opacity', '1', 'important');
                
                // Verify after style restore
                requestAnimationFrame(() => {
                    const newRect = tempHighlight.getBoundingClientRect();
                    if (newRect.width === 0 && newRect.height === 0) {
                        logger.warn('Temp highlight still not visible after style restore');
                    }
                });
            }
        } catch (error) {
            logger.error('Error verifying highlight:', error);
        }
    }

    /**
     * Ensure highlight is visible - check and restore if needed
     */
    _ensureHighlightVisible(selection) {
        if (!this.textSelectionHandler) return;
        
        const tempHighlight = this.textSelectionHandler.tempHighlight;
        
        // Check if highlight exists and is in DOM
        if (!tempHighlight) {
            // No highlight exists - don't try to restore using invalid range
            // After extractContents(), the original range is collapsed and cannot be reused
            logger.warn('Temp highlight missing (cannot restore - range already used)');
            return;
        }
        
        // Check if highlight is in DOM
        if (!tempHighlight.parentNode) {
            // Highlight was removed from DOM - cannot restore with used range
            logger.warn('Temp highlight removed from DOM (cannot restore - range already used)');
            this.textSelectionHandler.tempHighlight = null;
            return;
        }
        
        // Check if highlight has content
        const highlightText = tempHighlight.textContent || tempHighlight.innerText || '';
        if (!highlightText.trim()) {
            logger.warn('Temp highlight exists but has no content, removing...');
            if (tempHighlight.parentNode) {
                tempHighlight.parentNode.removeChild(tempHighlight);
            }
            this.textSelectionHandler.tempHighlight = null;
            return;
        }
        
        // Check if highlight is visible (has valid dimensions and styles)
        try {
            const rect = tempHighlight.getBoundingClientRect();
            const computedStyle = window.getComputedStyle(tempHighlight);
            
            // Check if highlight has zero size or is hidden
            if ((rect.width === 0 && rect.height === 0) || 
                computedStyle.display === 'none' ||
                computedStyle.visibility === 'hidden' ||
                computedStyle.opacity === '0') {
                logger.warn('Temp highlight not visible, restoring styles...');
                
                // Force restore styles
                tempHighlight.style.backgroundColor = '#ffeb3b';
                tempHighlight.style.display = 'inline';
                tempHighlight.style.visibility = 'visible';
                tempHighlight.style.opacity = '1';
                
                // Verify it's visible now
                requestAnimationFrame(() => {
                    const newRect = tempHighlight.getBoundingClientRect();
                    if (newRect.width === 0 && newRect.height === 0) {
                        // Still not visible, re-apply highlight
                        logger.warn('Temp highlight still not visible after style restore, re-applying...');
                        if (selection && selection.range && !this.state.isCreating) {
                            this.textSelectionHandler.applyTempHighlight(selection.range);
                            requestAnimationFrame(() => {
                                this.showCommentButton(selection);
                            });
                        }
                    }
                });
            }
        } catch (error) {
            logger.error('Error checking highlight visibility:', error);
        }
    }

    /**
     * Helper method to find text node at offset
     */
    _findTextNode(element, offset) {
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null
        );
        
        let currentOffset = 0;
        let node = walker.nextNode();
        
        while (node) {
            const nodeLength = node.textContent.length;
            if (currentOffset + nodeLength >= offset) {
                return node;
            }
            currentOffset += nodeLength;
            node = walker.nextNode();
        }
        
        return null;
    }

    /**
     * Setup listener for text selection
     */
    setupSelectionListener(contentElement) {
        // Cleanup existing listeners if any
        if (this._mousedownListener) {
            contentElement.removeEventListener('mousedown', this._mousedownListener);
            this._mousedownListener = null;
        }
        
        if (this._mousemoveListener) {
            contentElement.removeEventListener('mousemove', this._mousemoveListener);
            this._mousemoveListener = null;
        }
        
        if (this._mouseupListener) {
            contentElement.removeEventListener('mouseup', this._mouseupListener);
            this._mouseupListener = null;
        }
        
        // Reset selection flag
        this._isSelecting = false;
        
        // Clear any pending timers
        if (this._selectionProcessTimer) {
            clearTimeout(this._selectionProcessTimer);
            this._selectionProcessTimer = null;
        }
        
        // Handle mousedown to detect start of text selection
        this._mousedownListener = (e) => {
            // Don't handle if clicking on comment UI elements
            if (e.target.closest('.o_knowledge_comment_selection_overlay') ||
                e.target.closest('.o_knowledge_comment_form') ||
                e.target.closest('.o_knowledge_comment_list_wrapper')) {
                return;
            }
            
            // Mark that user is starting to select
            this._isSelecting = true;
            
            // Clear any pending selection processing timer
            if (this._selectionProcessTimer) {
                clearTimeout(this._selectionProcessTimer);
                this._selectionProcessTimer = null;
            }
            
            logger.log('Mousedown detected - user starting text selection', {
                isSelecting: this._isSelecting
            });
        };
        
        contentElement.addEventListener('mousedown', this._mousedownListener);
        
        // Handle mousemove to detect active selection dragging
        this._mousemoveListener = (e) => {
            if (!this._isSelecting) {
                // Check if user might be continuing selection (mousedown without setting flag)
                // This can happen if user releases mouse, then clicks and drags again quickly
                const selection = window.getSelection();
                if (selection && selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const selectedText = range.toString().trim();
                    if (selectedText && contentElement.contains(range.commonAncestorContainer)) {
                        // User might be continuing selection - set flag
                        this._isSelecting = true;
                        logger.log('Mousemove detected - user continuing selection', {
                            selectedText: selectedText.substring(0, 50)
                        });
                    }
                }
                return;
            }
            
            // User is actively dragging - clear any pending processing timer
            if (this._selectionProcessTimer) {
                clearTimeout(this._selectionProcessTimer);
                this._selectionProcessTimer = null;
                logger.log('Cleared selection processing timer - user is still dragging');
            }
            
            // Check if there's an active selection while dragging
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const selectedText = range.toString().trim();
                
                // If there's text selected while dragging, user is extending selection
                if (selectedText && contentElement.contains(range.commonAncestorContainer)) {
                    logger.log('Mousemove detected - user is actively dragging selection', {
                        selectedText: selectedText.substring(0, 50),
                        selectedLength: selectedText.length
                    });
                }
            }
        };
        
        contentElement.addEventListener('mousemove', this._mousemoveListener);
        
        // Handle mouseup for text selection
        this._mouseupListener = (e) => {
            logger.log('Mouseup event detected in content element', {
                target: e.target && e.target.tagName ? e.target.tagName : null,
                hasTextSelectionHandler: !!this.textSelectionHandler,
                contentElementMatches: contentElement === e.currentTarget,
                isSelecting: this._isSelecting
            });
            
            // Don't handle if clicking on comment button or overlay
            if (e.target.closest('.o_knowledge_comment_selection_overlay') ||
                e.target.closest('.o_knowledge_comment_form') ||
                e.target.closest('.o_knowledge_comment_list_wrapper')) {
                logger.log('Mouseup ignored: clicked on comment UI elements');
                this._isSelecting = false;
                return;
            }
            
            // Clear any pending hide timer
            if (this._hideButtonTimer) {
                clearTimeout(this._hideButtonTimer);
                this._hideButtonTimer = null;
            }
            
            // Clear any pending selection processing timer
            if (this._selectionProcessTimer) {
                clearTimeout(this._selectionProcessTimer);
                this._selectionProcessTimer = null;
            }
            
            // CRITICAL: Use a more robust approach - wait for selection to become stable
            // User might pause and continue dragging, so we need to wait until selection stops changing
            
            // Store initial selection for comparison
            const initialSelection = window.getSelection();
            const initialSelectionText = initialSelection && initialSelection.rangeCount > 0 ? 
                initialSelection.toString().trim() : '';
            
            if (!initialSelectionText) {
                // No selection - mark as not selecting
                this._isSelecting = false;
                return;
            }
            
            logger.log('Mouseup detected - waiting for selection to stabilize', {
                initialSelectionText: initialSelectionText.substring(0, 50),
                initialSelectionLength: initialSelectionText.length
            });
            
            // Prevent hiding temporarily
            this._preventHide = true;
            
            // Use periodic checks to see if selection has stabilized
            let lastSelectionText = initialSelectionText;
            let stableCount = 0;
            const requiredStableChecks = 3; // Selection must be stable for 3 consecutive checks
            const checkInterval = 150; // Check every 150ms
            let checkCount = 0;
            const maxChecks = 20; // Maximum 20 checks (3 seconds total)
            
            const stabilityCheckInterval = setInterval(() => {
                checkCount++;
                
                const currentSelection = window.getSelection();
                const currentSelectionText = currentSelection && currentSelection.rangeCount > 0 ? 
                    currentSelection.toString().trim() : '';
                
                // Check if selection has changed
                if (currentSelectionText === lastSelectionText && currentSelectionText.length > 0) {
                    // Selection is the same - increment stable count
                    stableCount++;
                    logger.log(`Selection stable check ${stableCount}/${requiredStableChecks}`, {
                        selectionText: currentSelectionText.substring(0, 50),
                        selectionLength: currentSelectionText.length
                    });
                    
                    // If selection has been stable for required checks, process it
                    if (stableCount >= requiredStableChecks) {
                        clearInterval(stabilityCheckInterval);
                        this._isSelecting = false;
                        
                        logger.log('Selection has stabilized - processing highlight', {
                            finalSelectionText: currentSelectionText.substring(0, 50),
                            finalSelectionLength: currentSelectionText.length,
                            checksPerformed: checkCount
                        });
                        
                        // Process the stable selection
                        this.onTextSelection();
                    }
                } else {
                    // Selection has changed - reset stable count
                    if (currentSelectionText.length > lastSelectionText.length) {
                        logger.log('Selection expanded - user continuing to drag', {
                            oldLength: lastSelectionText.length,
                            newLength: currentSelectionText.length,
                            oldText: lastSelectionText.substring(0, 50),
                            newText: currentSelectionText.substring(0, 50)
                        });
                    } else if (currentSelectionText.length < lastSelectionText.length) {
                        logger.log('Selection reduced - user adjusting selection', {
                            oldLength: lastSelectionText.length,
                            newLength: currentSelectionText.length
                        });
                    }
                    
                    stableCount = 0;
                    lastSelectionText = currentSelectionText || '';
                }
                
                // Stop checking after max checks
                if (checkCount >= maxChecks) {
                    clearInterval(stabilityCheckInterval);
                    this._isSelecting = false;
                    
                    // Process whatever selection we have
                    const finalSelection = window.getSelection();
                    const finalSelectionText = finalSelection && finalSelection.rangeCount > 0 ? 
                        finalSelection.toString().trim() : '';
                    
                    if (finalSelectionText) {
                        logger.log('Max checks reached - processing current selection', {
                            selectionText: finalSelectionText.substring(0, 50)
                        });
                        this.onTextSelection();
                    }
                }
            }, checkInterval);
            
            // Store interval reference for cleanup
            this._selectionStabilityCheckInterval = stabilityCheckInterval;
        };
        
        contentElement.addEventListener('mouseup', this._mouseupListener);
        
        // Also listen to selectionchange event as a backup
        if (this._selectionChangeListener) {
            document.removeEventListener('selectionchange', this._selectionChangeListener);
            this._selectionChangeListener = null;
        }
        
        this._selectionChangeListener = () => {
            // CRITICAL: Don't process selection changes while user is actively selecting
            // This prevents highlight from being created prematurely while user is still dragging
            if (this._isSelecting) {
                // User is still dragging - ignore selection changes
                // They will be processed after mouseup
                return;
            }
            
            const selection = window.getSelection();
            if (selection && selection.rangeCount > 0) {
                const range = selection.getRangeAt(0);
                const selectedText = range.toString().trim();
                
                // Only process if selection is within content element and has text
                if (selectedText && contentElement.contains(range.commonAncestorContainer)) {
                    logger.log('Selection change detected (not actively selecting)', {
                        selectedText: selectedText.substring(0, 50),
                        hasTextSelectionHandler: !!this.textSelectionHandler,
                        isSelecting: this._isSelecting
                    });
                    
                    // Debounce to avoid too many calls
                    if (this._selectionChangeTimeout) {
                        clearTimeout(this._selectionChangeTimeout);
                    }
                    
                    // Use longer delay when not actively selecting to ensure selection is stable
                    this._selectionChangeTimeout = setTimeout(() => {
                        // Double-check that user is not selecting
                        if (!this._isSelecting && this.textSelectionHandler) {
                            this.onTextSelection();
                        }
                    }, 200);
                }
            }
        };
        
        document.addEventListener('selectionchange', this._selectionChangeListener);
        
        logger.log('Selection listener setup completed', {
            contentElement: !!contentElement,
            hasTextSelectionHandler: !!this.textSelectionHandler
        });
        
        // Prevent hiding comment button when clicking on it or related elements
        document.addEventListener('click', (e) => {
            // Cancel any pending hide operation
            if (this._hideButtonTimer) {
                clearTimeout(this._hideButtonTimer);
                this._hideButtonTimer = null;
            }
            
            // If clicking on comment button, overlay, or comment panel, don't hide
            if (e.target.closest('.o_knowledge_comment_selection_overlay') ||
                e.target.closest('.o_knowledge_comment_form') ||
                e.target.closest('.o_knowledge_comment_list_wrapper') ||
                e.target.closest('.o_knowledge_comment_temp_highlight')) {
                this._preventHide = true;
                return;
            }
            
            // If clicking in content area and there's a temp highlight, don't clear it
            if (contentElement.contains(e.target)) {
                const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
                if (tempHighlight && tempHighlight.parentNode) {
                    // Ensure highlight stays visible
                    if (!tempHighlight.parentNode || !contentElement.contains(tempHighlight)) {
                        // Highlight was removed, try to restore if we have selection
                        if (this.currentSelection && this.currentSelection.range) {
                            logger.warn('Temp highlight removed on click, restoring...');
                            this.textSelectionHandler.applyTempHighlight(this.currentSelection.range);
                            this.showCommentButton(this.currentSelection);
                        }
                    }
                }
            }
            
            // If clicking in content area and there's a temp highlight, don't hide
            if (contentElement.contains(e.target)) {
                const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
                if (tempHighlight && tempHighlight.parentNode && 
                    (contentElement.contains(tempHighlight) || tempHighlight.parentNode.contains(e.target))) {
                    this._preventHide = true;
                    return;
                }
            }
            
            // If clicking outside content area, hide button after a delay
            // This allows user to click on the button itself
            if (!contentElement.contains(e.target) && 
                !e.target.closest('.o_knowledge_comment_selection_overlay')) {
                // Use longer delay to prevent accidental hiding
                this._hideButtonTimer = setTimeout(() => {
                    // Double-check: make sure user didn't click on button
                    const activeElement = document.activeElement;
                    if (!activeElement || 
                        !activeElement.closest('.o_knowledge_comment_selection_overlay')) {
                        // Check if temp highlight still exists
                        const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
                        if (tempHighlight && tempHighlight.parentNode) {
                            // Highlight still exists, don't hide
                            return;
                        }
                        
                        // Only hide if not clicking on button and no text is selected
                        const selection = window.getSelection();
                        if (!selection || selection.rangeCount === 0 || !selection.toString().trim()) {
                            if (!this._preventHide && !this.state.isCreating) {
                                this.hideCommentButton();
                            }
                        }
                    }
                    this._hideButtonTimer = null;
                }, 300); // Increased delay to 300ms
            }
        });
    }

    /**
     * Handle text selection event
     */
    onTextSelection() {
        if (!this.textSelectionHandler) return;

        // Clear any pending hide timer
        if (this._hideButtonTimer) {
            clearTimeout(this._hideButtonTimer);
            this._hideButtonTimer = null;
        }

        const selection = this.textSelectionHandler.getSelection();
        
        // CRITICAL: Check if we have an existing temp highlight and new selection
        // If new selection text doesn't match existing highlight, clear old highlight first
        if (selection && selection.text.trim().length > 0) {
            const existingHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
            
            if (existingHighlight && existingHighlight.parentNode) {
                const existingHighlightText = existingHighlight.textContent || existingHighlight.innerText || '';
                const existingNormalized = existingHighlightText.trim().replace(/\s+/g, ' ');
                const newSelectedNormalized = selection.text.trim().replace(/\s+/g, ' ');
                
                // Check if new selection is exactly the same as existing highlight
                if (existingNormalized === newSelectedNormalized) {
                    // Same selection - no need to do anything, keep existing highlight
                    logger.log('New selection is same as existing highlight, keeping existing highlight', {
                        highlightText: existingNormalized.substring(0, 50)
                    });
                    // Don't clear or recreate - just update currentSelection reference
                    this.currentSelection = selection;
                    return; // Exit early, don't recreate highlight
                }
                
                // Check if new selection extends/contains existing highlight (user is extending selection)
                const newContainsOld = newSelectedNormalized.includes(existingNormalized);
                const oldContainsNew = existingNormalized.includes(newSelectedNormalized);
                
                if (newContainsOld && newSelectedNormalized.length > existingNormalized.length) {
                    // New selection extends existing highlight - clear old and create new one with extended selection
                    logger.log('New selection extends existing highlight, clearing old and creating extended highlight', {
                        existingHighlightText: existingNormalized.substring(0, 50),
                        newSelectedText: newSelectedNormalized.substring(0, 50),
                        existingLength: existingNormalized.length,
                        newLength: newSelectedNormalized.length
                    });
                    
                    // CRITICAL: Get fresh range from current selection BEFORE clearing highlight
                    // This ensures the range covers all selected text (original + extended)
                    const currentSelection = window.getSelection();
                    if (currentSelection && currentSelection.rangeCount > 0) {
                        const freshRange = currentSelection.getRangeAt(0).cloneRange();
                        selection.range = freshRange;
                        logger.log('Cloned fresh range before clearing highlight for extended selection', {
                            rangeText: freshRange.toString().substring(0, 50),
                            rangeLength: freshRange.toString().length
                        });
                    }
                    
                    // Clear old highlight first (this will normalize DOM)
                    if (this.textSelectionHandler) {
                        this.textSelectionHandler.clearTempHighlight();
                    }
                    
                    // CRITICAL: Get fresh selection again after clearing highlight
                    // DOM may have changed, so we need to restore selection
                    setTimeout(() => {
                        const updatedSelection = window.getSelection();
                        if (updatedSelection && updatedSelection.rangeCount > 0) {
                            // Selection might have been lost, try to restore it
                            const currentRange = updatedSelection.getRangeAt(0);
                            if (currentRange.toString().trim() !== newSelectedNormalized.trim()) {
                                // Selection was lost, restore using the cloned range
                                updatedSelection.removeAllRanges();
                                updatedSelection.addRange(selection.range);
                                logger.log('Restored selection after clearing highlight');
                            }
                        }
                    }, 0);
                    
                    // Don't hide button - we'll show it again after creating new highlight
                    // Continue to create new highlight with extended selection
                } else if (!oldContainsNew && !newContainsOld) {
                    // New selection is completely different - clear old one
                    logger.log('New selection is completely different from existing highlight, clearing old highlight', {
                        existingHighlightText: existingNormalized.substring(0, 50),
                        newSelectedText: newSelectedNormalized.substring(0, 50)
                    });
                    
                    // Clear old highlight
                    if (this.textSelectionHandler) {
                        this.textSelectionHandler.clearTempHighlight();
                    }
                    this.hideCommentButton();
                    // Continue to create new highlight with new selection
                } else if (oldContainsNew && existingNormalized.length > newSelectedNormalized.length) {
                    // New selection is a subset of existing highlight (user reduced selection)
                    logger.log('New selection is a subset of existing highlight, updating highlight', {
                        existingHighlightText: existingNormalized.substring(0, 50),
                        newSelectedText: newSelectedNormalized.substring(0, 50)
                    });
                    
                    // Clear old highlight and create new one with reduced selection
                    if (this.textSelectionHandler) {
                        this.textSelectionHandler.clearTempHighlight();
                    }
                    // Continue to create new highlight with reduced selection
                }
            }
            
            this.currentSelection = selection;
            // Prevent hiding while processing selection
            this._preventHide = true;
            
            // Keep a temporary highlight so it doesn't disappear when selection is cleared
            // Only apply if range has text content
            if (!selection.range || !selection.text || !selection.text.trim().length) {
                logger.warn('Cannot apply highlight: selection has no text', {
                    hasRange: !!selection.range,
                    hasText: !!selection.text,
                    textLength: selection.text && selection.text.length ? selection.text.length : 0
                });
                return; // Don't show button if we can't create highlight
            }
            
            // CRITICAL: When extending selection, we need to use the current range from selection
            // Clear any existing highlight first to avoid conflicts
            // Note: existingHighlight was already declared above, so we reuse it
            // Get fresh range from current selection (in case DOM changed)
            const currentSelection = window.getSelection();
            if (currentSelection && currentSelection.rangeCount > 0) {
                const currentRange = currentSelection.getRangeAt(0);
                // Clone the range before clearing highlight (to preserve selection boundaries)
                selection.range = currentRange.cloneRange();
                logger.log('Cloned fresh range before applying highlight', {
                    rangeText: selection.range.toString().substring(0, 50)
                });
            }
            
            // Apply highlight immediately with the selection range (which should include all selected text)
            this.textSelectionHandler.applyTempHighlight(selection.range);
            
            // Verify highlight was created successfully
            const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
            if (!tempHighlight) {
                logger.warn('Failed to create highlight, cannot show button');
                return;
            }
            
            // Use double requestAnimationFrame to ensure highlight is fully rendered in DOM before showing button
            requestAnimationFrame(() => {
                requestAnimationFrame(() => {
                    // Re-verify highlight is still in DOM (may be removed by external code)
                    const currentHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
                    if (!currentHighlight || !currentHighlight.parentNode) {
                        logger.warn('Highlight removed before showing button, cannot restore');
                        return;
                    }
                    
                    // Verify highlight has content and matches selected text
                    const highlightText = currentHighlight.textContent || currentHighlight.innerText || '';
                    if (!highlightText.trim()) {
                        logger.warn('Highlight has no content, removing...');
                        if (currentHighlight.parentNode) {
                            currentHighlight.parentNode.removeChild(currentHighlight);
                        }
                        this.textSelectionHandler.tempHighlight = null;
                        return;
                    }
                    
                    // CRITICAL: Verify that highlight text matches the selected text
                    const selectedText = selection.text || '';
                    const highlightNormalized = highlightText.trim().replace(/\s+/g, ' ');
                    const selectedNormalized = selectedText.trim().replace(/\s+/g, ' ');
                    
                    // Check if highlight text matches selected text
                    if (selectedText && 
                        highlightNormalized !== selectedNormalized && 
                        !highlightNormalized.includes(selectedNormalized) && 
                        !selectedNormalized.includes(highlightNormalized) &&
                        highlightNormalized.length < selectedNormalized.length * 0.8) {
                        // Highlight text doesn't match selected text - wrong highlight!
                        logger.error('Highlight text does not match selected text! Removing incorrect highlight', {
                            selectedText: selectedNormalized.substring(0, 50),
                            highlightText: highlightNormalized.substring(0, 50),
                            selectedLength: selectedNormalized.length,
                            highlightLength: highlightNormalized.length
                        });
                        
                        // Remove incorrect highlight and clear reference
                        if (currentHighlight.parentNode) {
                            currentHighlight.parentNode.removeChild(currentHighlight);
                        }
                        this.textSelectionHandler.tempHighlight = null;
                        
                        // Try to re-apply highlight with correct range
                        if (selection.range && !selection.range.collapsed) {
                            logger.log('Re-applying highlight with correct range');
                            this.textSelectionHandler.applyTempHighlight(selection.range);
                            
                            // Check again after re-application
                            const newHighlight = this.textSelectionHandler.tempHighlight;
                            if (newHighlight && newHighlight.parentNode) {
                                const newHighlightText = newHighlight.textContent || newHighlight.innerText || '';
                                const newHighlightNormalized = newHighlightText.trim().replace(/\s+/g, ' ');
                                if (newHighlightNormalized !== selectedNormalized && 
                                    !newHighlightNormalized.includes(selectedNormalized)) {
                                    logger.error('Re-applied highlight still incorrect, giving up');
                                    if (newHighlight.parentNode) {
                                        newHighlight.parentNode.removeChild(newHighlight);
                                    }
                                    this.textSelectionHandler.tempHighlight = null;
                                    return;
                                }
                            } else {
                                logger.error('Failed to re-apply highlight');
                                return;
                            }
                        } else {
                            logger.error('Cannot re-apply: range is invalid');
                            return;
                        }
                    }
                    
                    // Ensure overlay element exists before showing
                    if ((!this.overlayRef || !this.overlayRef.el) && !document.querySelector('.o_knowledge_comment_selection_overlay')) {
                        this.createOverlayElement();
                    }
                    
                    // Show comment button or overlay at selection position
                    // Pass selection but button will use tempHighlight element for position
                    this.showCommentButton(selection);
                    
                    // Aggressively verify and restore highlight after showing button
                    // Use multiple checks to ensure highlight stays visible
                    requestAnimationFrame(() => {
                        requestAnimationFrame(() => {
                            this._ensureHighlightVisible(selection);
                        });
                    });
                    
                    // Also check after a short delay to catch any delayed DOM changes
                    setTimeout(() => {
                        this._ensureHighlightVisible(selection);
                    }, 100);
                    
                    // Disable interval check - it causes flickering on hover
                    // Only check once after a delay instead of continuously
                    // if (!this._highlightCheckInterval) {
                    //     this._highlightCheckInterval = setInterval(() => {
                    //         if ((this.textSelectionHandler && this.textSelectionHandler.tempHighlight) && !this.state.isCreating) {
                    //             this._ensureHighlightVisible(this.currentSelection);
                    //         }
                    //     }, 500); // Check every 500ms
                    // }
                    
                    // Allow hiding after a delay to prevent immediate hiding
                    setTimeout(() => {
                        this._preventHide = false;
                    }, 500); // Prevent hiding for 500ms after showing button
                });
            });
        } else {
            // No current selection - check if we should clear existing highlight
            const tempHighlight = this.textSelectionHandler && this.textSelectionHandler.tempHighlight ? this.textSelectionHandler.tempHighlight : null;
            
            if (tempHighlight && tempHighlight.parentNode) {
                // Temp highlight exists but no selection
                // Check if user is creating a comment - if so, keep highlight
                if (this.state.isCreating) {
                    logger.log('Selection cleared but creating comment - keeping highlight visible', {
                        hasTempHighlight: true,
                        highlightInDOM: !!tempHighlight.parentNode,
                        highlightText: tempHighlight.textContent ? tempHighlight.textContent.substring(0, 50) : null
                    });
                    return; // Don't hide or clear while creating comment
                }
                
                // Check if we have a stored currentSelection that matches the highlight
                if (this.currentSelection && this.currentSelection.text) {
                    const highlightText = tempHighlight.textContent || tempHighlight.innerText || '';
                    const highlightNormalized = highlightText.trim().replace(/\s+/g, ' ');
                    const selectedNormalized = this.currentSelection.text.trim().replace(/\s+/g, ' ');
                    
                    // CRITICAL: Strict matching - only keep highlight if texts actually match
                    // Check if texts match exactly first
                    const exactMatch = highlightNormalized === selectedNormalized;
                    
                    if (!exactMatch) {
                        // If not exact match, check if one contains the other significantly
                        // (at least 80% of shorter text must be contained in longer text)
                        const longerText = highlightNormalized.length >= selectedNormalized.length ? highlightNormalized : selectedNormalized;
                        const shorterText = highlightNormalized.length < selectedNormalized.length ? highlightNormalized : selectedNormalized;
                        
                        const fullContains = longerText.includes(shorterText);
                        const minContainRatio = 0.8; // At least 80% of shorter text must be contained
                        
                        // Calculate how much of shorter text is actually contained
                        let containRatio = 0;
                        if (fullContains && shorterText.length > 0) {
                            // Find the position where shorter text appears in longer text
                            const startIndex = longerText.indexOf(shorterText);
                            if (startIndex !== -1) {
                                // Check if the contained portion is significant
                                containRatio = shorterText.length / longerText.length;
                            }
                        }
                        
                        // Also check if texts are similar by calculating character-by-character similarity
                        let similarity = 0;
                        if (highlightNormalized.length > 0 && selectedNormalized.length > 0) {
                            const maxLength = Math.max(highlightNormalized.length, selectedNormalized.length);
                            let matchingChars = 0;
                            
                            // Compare character by character at same positions
                            const minLength = Math.min(highlightNormalized.length, selectedNormalized.length);
                            for (let i = 0; i < minLength; i++) {
                                if (highlightNormalized[i] === selectedNormalized[i]) {
                                    matchingChars++;
                                }
                            }
                            similarity = matchingChars / maxLength;
                        }
                        
                        // Only keep highlight if:
                        // 1. Exact match, OR
                        // 2. One fully contains the other AND contained portion is significant (>= 80%), OR
                        // 3. Character-by-character similarity is high (>= 90%)
                        const minSimilarity = 0.9;
                        const shouldKeep = exactMatch || 
                                         (fullContains && containRatio >= minContainRatio) || 
                                         (similarity >= minSimilarity && Math.abs(highlightNormalized.length - selectedNormalized.length) <= 5);
                        
                        if (shouldKeep) {
                            logger.log('Selection cleared but temp highlight matches stored selection - keeping highlight visible', {
                                hasTempHighlight: true,
                                highlightInDOM: !!tempHighlight.parentNode,
                                highlightText: highlightNormalized.substring(0, 50),
                                selectedText: selectedNormalized.substring(0, 50),
                                exactMatch: exactMatch,
                                fullContains: fullContains,
                                containRatio: containRatio.toFixed(2),
                                similarity: similarity.toFixed(2)
                            });
                            return; // Don't hide or clear
                        } else {
                            // Highlight doesn't match well enough - clear it
                            logger.warn('Selection cleared but temp highlight does not match stored selection - clearing highlight', {
                                hasTempHighlight: true,
                                highlightInDOM: !!tempHighlight.parentNode,
                                highlightText: highlightNormalized.substring(0, 50),
                                selectedText: selectedNormalized.substring(0, 50),
                                exactMatch: exactMatch,
                                fullContains: fullContains,
                                containRatio: containRatio.toFixed(2),
                                similarity: similarity.toFixed(2),
                                highlightLength: highlightNormalized.length,
                                selectedLength: selectedNormalized.length,
                                lengthDiff: Math.abs(highlightNormalized.length - selectedNormalized.length)
                            });
                        }
                    } else {
                        // Exact match - keep highlight
                        logger.log('Selection cleared but temp highlight exactly matches stored selection - keeping highlight visible', {
                            hasTempHighlight: true,
                            highlightInDOM: !!tempHighlight.parentNode,
                            highlightText: highlightNormalized.substring(0, 50),
                            selectedText: selectedNormalized.substring(0, 50)
                        });
                        return; // Don't hide or clear
                    }
                }
                
                // Highlight doesn't match or no stored selection - clear it
                logger.log('Selection cleared and highlight doesn\'t match - clearing highlight', {
                    hasTempHighlight: true,
                    highlightInDOM: !!tempHighlight.parentNode,
                    highlightText: tempHighlight.textContent ? tempHighlight.textContent.substring(0, 50) : null
                });
                
                // Clear highlight and hide button
                this._preventHide = false;
                if (!this.state.isCreating) {
                    this.hideCommentButton();
                    if (this.textSelectionHandler) {
                        this.textSelectionHandler.clearTempHighlight();
                    }
                }
                return;
            }
            
            // Only hide if there's really no selection, no temp highlight, and we're not creating a comment
            this._preventHide = false;
            if (!this.state.isCreating) {
                this.hideCommentButton();
                if (this.textSelectionHandler) {
                    this.textSelectionHandler.clearTempHighlight();
                }
            }
        }
    }

    /**
     * Show comment button at selection position
     */
    showCommentButton(selection) {
        // Try to get overlay element - use multiple methods to find it
        let overlay = this.overlayRef && this.overlayRef.el ? this.overlayRef.el : null;
        
        // Fallback: Try to find by class name if ref is not available
        if (!overlay) {
            overlay = document.querySelector('.o_knowledge_comment_selection_overlay');
        }
        
        // Fallback 2: Try to find within component's root element
        if (!overlay && this.__owl__ && this.__owl__.bdom && this.__owl__.bdom.parentEl) {
            overlay = this.__owl__.bdom.parentEl.querySelector('.o_knowledge_comment_selection_overlay');
        }
        
        if (!overlay) {
            logger.warn('Overlay element not found', {
                hasOverlayRef: !!this.overlayRef,
                overlayRefEl: !!(this.overlayRef && this.overlayRef.el),
                foundByClass: !!document.querySelector('.o_knowledge_comment_selection_overlay')
            });
            // Try to create overlay element if it doesn't exist
            this.createOverlayElement();
            overlay = document.querySelector('.o_knowledge_comment_selection_overlay');
            if (!overlay) {
                return;
            }
        }

        let rect = null;
        let source = 'unknown';
        
        // Priority 1: Try to get rect from temp highlight element (most reliable after highlight is applied)
        if (this.textSelectionHandler && this.textSelectionHandler.tempHighlight) {
            const tempHighlightEl = this.textSelectionHandler.tempHighlight;
            if (tempHighlightEl && tempHighlightEl.parentNode) {
                rect = tempHighlightEl.getBoundingClientRect();
                source = 'tempHighlight';
                
                // Validate rect - ensure it's not all zeros (which means element might not be in viewport yet)
                if (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0) {
                    logger.warn('Temp highlight rect is all zeros, element may not be positioned yet');
                    rect = null;
                }
            }
        }
        
        // Priority 2: Use range.getBoundingClientRect() if temp highlight not available or invalid
        if ((!rect || (rect.width === 0 && rect.height === 0)) && selection && selection.range) {
            try {
                const rangeRect = selection.range.getBoundingClientRect();
                if (rangeRect.width > 0 || rangeRect.height > 0 || rangeRect.top !== 0 || rangeRect.left !== 0) {
                    rect = rangeRect;
                    source = 'range';
                }
            } catch (error) {
                logger.warn('Error getting bounding rect from range:', error);
            }
        }
        
        // Priority 3: Try to find the highlighted element in DOM (fallback)
        if ((!rect || (rect.width === 0 && rect.height === 0)) && this.textSelectionHandler && this.textSelectionHandler.tempHighlight) {
            const tempHighlightEl = this.textSelectionHandler.tempHighlight;
            // Force a reflow to ensure element is positioned
            void tempHighlightEl.offsetHeight;
            if (tempHighlightEl && tempHighlightEl.parentNode) {
                rect = tempHighlightEl.getBoundingClientRect();
                source = 'tempHighlight-after-reflow';
            }
        }

        // If still no valid rect, log warning and return
        if (!rect || (rect.width === 0 && rect.height === 0 && rect.top === 0 && rect.left === 0)) {
            logger.warn('Could not get valid bounding rect for comment button', {
                hasTempHighlight: !!(this.textSelectionHandler && this.textSelectionHandler.tempHighlight),
                hasSelection: !!selection,
                hasRange: !!(selection && selection.range),
                tempHighlightInDOM: (this.textSelectionHandler && this.textSelectionHandler.tempHighlight && this.textSelectionHandler.tempHighlight.parentNode) ? true : false
            });
            return;
        }

        // Calculate text box position: positioned to the right of selected text
        // Position text box at the right edge of the content area, below the highlight
        const boxWidth = 350; // Text box width
        const boxHeight = 150; // Estimated text box height (will adjust based on content)
        const boxTop = rect.bottom + 12; // Position below highlight with 12px gap
        // Position at end of line (right edge of content area, with margin)
        const contentElement = this.props.contentElement || document.querySelector('.o_knowledge_article_body');
        let endOfLineLeft = rect.right; // Default to right of highlight
        
        // Try to find the right edge of the content container or line
        if (contentElement) {
            const contentRect = contentElement.getBoundingClientRect();
            const rightEdge = contentRect.right;
            const minMargin = 20; // Margin from right edge
            // Use right edge of content minus box width and margin, but ensure it's after highlight
            endOfLineLeft = Math.max(rect.right + 12, rightEdge - boxWidth - minMargin);
        } else {
            // Fallback: use viewport width
            const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
            const minMargin = 20;
            endOfLineLeft = Math.max(rect.right + 12, viewportWidth - boxWidth - minMargin);
        }
        
        const boxLeft = endOfLineLeft;
        
        // Also check if box would go off screen, adjust if needed
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight;
        
        // Additional validation: ensure positions are reasonable
        if (isNaN(boxTop) || isNaN(boxLeft) || boxTop < 0 || boxLeft < 0) {
            logger.warn('Invalid text box position calculated', {
                boxTop,
                boxLeft,
                rect
            });
            return;
        }
        
        // Determine final position: position below highlight, aligned to right
        let finalTop = boxTop;
        let finalLeft = boxLeft;
        
        // Ensure box doesn't go off right edge of viewport
        const maxLeft = viewportWidth - boxWidth - 20; // Leave 20px margin from right edge
        if (finalLeft > maxLeft) {
            finalLeft = maxLeft;
            logger.log('Text box adjusted to stay within viewport', {
                originalLeft: boxLeft,
                finalLeft: finalLeft,
                maxLeft: maxLeft
            });
        }
        
        // Ensure box is at least to the right of highlight (don't overlap)
        if (finalLeft < rect.right + 8) {
            finalLeft = rect.right + 8; // Minimum 8px gap from highlight
        }
        
        // Ensure box doesn't go above viewport
        if (finalTop < 0) {
            finalTop = 10; // 10px from top
        }
        
        // Ensure box doesn't go below viewport - if it does, position above highlight instead
        if (finalTop + boxHeight > viewportHeight - 20) {
            finalTop = rect.top - boxHeight - 12; // Position above highlight with 12px gap
            // If still doesn't fit, position at top of viewport
            if (finalTop < 10) {
                finalTop = 10;
            }
        }
        
        overlay.style.display = 'block';
        overlay.style.position = 'fixed';
        overlay.style.top = `${finalTop}px`;
        overlay.style.left = `${finalLeft}px`;
        overlay.style.zIndex = '2000';

        this.overlayVisible = true;
        
        // CRITICAL: Immediately verify and ensure highlight is still visible after showing text box
        // This is a common issue where highlight disappears right after box appears
        requestAnimationFrame(() => {
            this._verifyAndRestoreHighlight(selection);
        });
        
        // Also check after a short delay to catch any delayed DOM changes
        setTimeout(() => {
            this._verifyAndRestoreHighlight(selection);
        }, 50);
        
        logger.log('Comment text box shown:', {
            top: overlay.style.top,
            left: overlay.style.left,
            rect: { 
                top: rect.top, 
                bottom: rect.bottom, 
                left: rect.left, 
                right: rect.right,
                width: rect.width,
                height: rect.height 
            },
            boxPosition: { 
                calculatedTop: boxTop, 
                calculatedLeft: boxLeft,
                finalTop: finalTop,
                finalLeft: finalLeft,
                viewportWidth: viewportWidth,
                viewportHeight: viewportHeight,
                endOfLineLeft: endOfLineLeft,
                distanceFromHighlight: finalLeft - rect.right,
                boxWidth: boxWidth,
                boxHeight: boxHeight,
                positioning: 'end-of-line'
            },
            source: source
        });
    }

    /**
     * Hide comment button
     */
    hideCommentButton() {
        // Don't hide if prevent flag is set
        if (this._preventHide) {
            logger.log('Hide prevented by _preventHide flag');
            return;
        }
        
        // Only hide if not currently creating a comment
        if (this.state.isCreating) {
            return; // Don't hide if user is in the process of creating a comment
        }
        
        // Check if temp highlight still exists - if it does, keep button visible
        if (this.textSelectionHandler && this.textSelectionHandler.tempHighlight) {
            const tempHighlight = this.textSelectionHandler.tempHighlight;
            if (tempHighlight && tempHighlight.parentNode) {
                // Highlight still exists, don't hide button
                logger.log('Hide prevented: temp highlight still exists');
                return;
            }
        }
        
        let overlay = this.overlayRef && this.overlayRef.el ? this.overlayRef.el : null;
        if (!overlay) {
            overlay = document.querySelector('.o_knowledge_comment_selection_overlay');
        }
        if (overlay) {
            overlay.style.display = 'none';
        }
        this.overlayVisible = false;
    }

    /**
     * Load comments for current article
     */
    async loadComments() {
        if (!this.commentManager) {
            logger.warn('Cannot load comments: commentManager is null', {
                articleId: this.props.articleId,
                showCommentPanel: this.props.showCommentPanel
            });
            // Try to initialize if we have articleId
            if (this.props.articleId) {
                logger.log('Attempting to initialize comment manager before loading comments');
                await this.initializeCommentSystem();
                if (!this.commentManager) {
                    logger.error('Failed to initialize comment manager');
                    return;
                }
            } else {
                return;
            }
        }

        try {
            logger.log('Starting to load comments...', {
                articleId: this.props.articleId,
                commentManagerExists: !!this.commentManager,
                showCommentPanel: this.props.showCommentPanel
            });
            
            const comments = await this.commentManager.loadComments();
            logger.log('Raw comments loaded from manager:', {
                count: comments.length,
                comments: comments.map(c => ({ id: c.id, resolved: c.resolved, selected_text: c.selected_text }))
            });
            
            // getThreadedComments should always return an array, even if empty
            const threadedComments = this.commentManager.getThreadedComments ? 
                this.commentManager.getThreadedComments() : [];
            
            logger.log('Threaded comments prepared:', {
                count: threadedComments.length,
                threadedComments: threadedComments.map(c => ({ id: c.id, resolved: c.resolved, repliesCount: (c.replies && c.replies.length) ? c.replies.length : 0 }))
            });
            
            // CRITICAL: Force reactivity by creating new array
            // Use Object.assign to ensure Owl detects the change
            const newComments = [...threadedComments];
            this.state.comments = newComments;
            
            // Force a render by triggering reactivity
            this.render();
            
            logger.log('Comments loaded successfully and set to state:', {
                count: this.state.comments.length,
                stateCommentsCount: this.state.comments.length,
                articleId: this.props.articleId,
                showResolved: this.state.showResolved,
                displayCommentsCount: this.getDisplayComments().length,
                stateCommentsArray: this.state.comments
            });
            
            // CRITICAL: Ensure highlights are rendered immediately after comments are loaded
            // This is especially important after creating a new comment
            if (this.commentManager) {
                await new Promise(resolve => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(async () => {
                            try {
                                this._lastHighlightRenderTime = Date.now();
                                await this.commentManager.renderHighlights();
                                logger.log('Highlights rendered immediately after loadComments()', {
                                    highlightsCount: this.commentManager.highlights.size,
                                    unresolvedCommentsCount: this.commentManager.comments.filter(c => !c.resolved).length
                                });
                            } catch (error) {
                                logger.warn('Error rendering highlights immediately after loadComments():', error);
                            }
                            resolve();
                        });
                    });
                });
            }
        } catch (error) {
            logger.error('Error loading comments in overlay:', error);
            // Log detailed error information for debugging
            if (error.data && error.data.message) {
                logger.error('RPC Error details:', error.data.message);
            }
            if (error.message) {
                logger.error('Error message:', error.message);
            }
            // Don't show error notification if comments array is empty (might be normal)
            // Only show if there's an actual error
            if (error && error.message && !error.message.includes('empty')) {
                this.notification.add('เกิดข้อผิดพลาดในการโหลด comments', { type: 'danger' });
            }
            // Ensure state.comments is always an array to prevent UI errors
            this.state.comments = [];
        }
    }

    /**
     * Start creating a new comment
     */
    /**
     * Copy text to clipboard (helper method)
     * @param {string} textToCopy - Text to copy
     * @returns {Promise<boolean>} Success status
     */
    async _copyToClipboard(textToCopy) {
        if (!textToCopy || !textToCopy.trim()) {
            return false;
        }

        const text = textToCopy.trim();
        
        try {
            // Try to use modern Clipboard API first
            if (navigator.clipboard && navigator.clipboard.writeText) {
                await navigator.clipboard.writeText(text);
                logger.log('Text copied to clipboard using Clipboard API', {
                    textLength: text.length,
                    textPreview: text.substring(0, 50)
                });
                return true;
            } else {
                // Fallback: Use traditional method
                const textArea = document.createElement('textarea');
                textArea.value = text;
                textArea.style.position = 'fixed';
                textArea.style.left = '-999999px';
                textArea.style.top = '-999999px';
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                
                try {
                    const successful = document.execCommand('copy');
                    if (!successful) {
                        throw new Error('execCommand copy failed');
                    }
                    logger.log('Text copied to clipboard using execCommand', {
                        textLength: text.length,
                        textPreview: text.substring(0, 50)
                    });
                    return true;
                } finally {
                    document.body.removeChild(textArea);
                }
            }
        } catch (error) {
            logger.error('Failed to copy text to clipboard:', error);
            return false;
        }
    }

    /**
     * Copy selected text to clipboard (from floating button)
     */
    async onCopyText() {
        if (!this.currentSelection || !this.currentSelection.text) {
            this.notification.add('กรุณาเลือกข้อความก่อน copy', { type: 'warning' });
            return;
        }

        const textToCopy = this.currentSelection.text.trim();
        
        if (!textToCopy) {
            this.notification.add('ไม่มีข้อความให้ copy', { type: 'warning' });
            return;
        }

        const success = await this._copyToClipboard(textToCopy);
        
        if (success) {
            // Show success notification
            this.notification.add(`Copy ข้อความสำเร็จ! (${textToCopy.length} ตัวอักษร)`, { 
                type: 'success',
                sticky: false
            });
        } else {
            this.notification.add('ไม่สามารถ copy ข้อความได้ กรุณาลองอีกครั้ง', { 
                type: 'danger',
                sticky: true
            });
        }
    }

    /**
     * Copy selected text from comment form
     */
    async onCopySelectedText() {
        if (!this.currentSelection || !this.currentSelection.text) {
            this.notification.add('ไม่มีข้อความให้ copy', { type: 'warning' });
            return;
        }

        const textToCopy = this.currentSelection.text.trim();
        const success = await this._copyToClipboard(textToCopy);
        
        if (success) {
            this.notification.add(`Copy ข้อความสำเร็จ! (${textToCopy.length} ตัวอักษร)`, { 
                type: 'success',
                sticky: false
            });
        } else {
            this.notification.add('ไม่สามารถ copy ข้อความได้ กรุณาลองอีกครั้ง', { 
                type: 'danger',
                sticky: true
            });
        }
    }

    /**
     * Copy comment selected text from comment list
     */
    async onCopyCommentText(selectedText) {
        if (!selectedText || !selectedText.trim()) {
            this.notification.add('ไม่มีข้อความให้ copy', { type: 'warning' });
            return;
        }

        const success = await this._copyToClipboard(selectedText);
        
        if (success) {
            this.notification.add(`Copy ข้อความสำเร็จ! (${selectedText.trim().length} ตัวอักษร)`, { 
                type: 'success',
                sticky: false
            });
        } else {
            this.notification.add('ไม่สามารถ copy ข้อความได้ กรุณาลองอีกครั้ง', { 
                type: 'danger',
                sticky: true
            });
        }
    }

    onCreateComment() {
        if (!this.currentSelection) {
            this.notification.add('กรุณาเลือกข้อความก่อนสร้าง comment', { type: 'warning' });
            return;
        }

        logger.log('onCreateComment called - keeping temp highlight visible while user types', {
            hasTempHighlight: !!(this.textSelectionHandler && this.textSelectionHandler.tempHighlight),
            tempHighlightInDOM: !!(this.textSelectionHandler && this.textSelectionHandler.tempHighlight && this.textSelectionHandler.tempHighlight.parentNode)
        });

        // IMPORTANT: Don't clear temp highlight - keep it visible while user types comment
        // The highlight will be converted to permanent highlight when comment is saved
        // Only clear if user cancels
        
        // Set prevent hide flag to false to allow hiding button
        this._preventHide = false;
        
        // Force hide comment button immediately when clicked (force = true bypasses all checks)
        this.hideCommentButton(true);

        // Initialize for new comment (uncontrolled component - DOM is source of truth)
        this.state.isCreating = true;
        this.state.newCommentBody = ""; // Clear state

        // If parent supplied a callback (e.g., main view state), use it to sync UI
        if (this.props.onCreateCommentFromSelection) {
            this.props.onCreateCommentFromSelection();
        }
        
        // Focus textarea after form opens and clear it (uncontrolled component)
        setTimeout(() => {
            const textarea = this.commentInputRef.el || document.querySelector('.o_knowledge_comment_form textarea');
            if (textarea) {
                textarea.value = ""; // Clear DOM value directly
                textarea.focus();
            }
        }, 100);
    }

    /**
     * Handle textarea focus event
     */
    onTextareaFocus(ev) {
        this._textareaHasFocus = true;
        logger.log('Textarea focused');
    }

    /**
     * Handle textarea blur event
     */
    onTextareaBlur(ev) {
        // Delay blur to allow click events on buttons to fire first
        setTimeout(() => {
            this._textareaHasFocus = false;
            logger.log('Textarea blurred');
        }, 200);
    }

    /**
     * Handle textarea input change - manually sync to state
     * This is needed because t-model is not working reliably in this context
     * CRITICAL: This must update state immediately and prevent any resets
     */
    onCommentInputChange(ev) {
        const newValue = (ev.target.value || '').trim() === '' ? ev.target.value : ev.target.value;
        const oldStateValue = this.state.newCommentBody || '';
        
        logger.log('onCommentInputChange called:', {
            newValue: newValue,
            newLength: newValue.length,
            oldStateValue: oldStateValue,
            oldLength: oldStateValue.length,
            hasFocus: this._textareaHasFocus,
            willUpdate: newValue !== oldStateValue
        });
        
        // CRITICAL: Update state immediately - don't wait for anything
        // Use direct assignment to ensure it happens synchronously
        this.state.newCommentBody = newValue;
        this._textareaHasFocus = true; // Mark as focused when typing
        
        // Double-check after a microtask to ensure it wasn't reset
        Promise.resolve().then(() => {
            if (this.commentInputRef.el && this.commentInputRef.el.value !== this.state.newCommentBody) {
                const currentDomValue = this.commentInputRef.el.value || '';
                logger.warn('onCommentInputChange: State was reset after update, restoring from DOM', {
                    domValue: currentDomValue,
                    stateValue: this.state.newCommentBody
                });
                this.state.newCommentBody = currentDomValue;
            }
        });
        
        // Also propagate to parent if callback exists (for backward compatibility)
        if (this.props.onUpdateNewCommentBody) {
            this.props.onUpdateNewCommentBody(newValue);
        }
    }
    
    /**
     * Get comment body from state
     * Also check DOM value as fallback if state is out of sync
     */
    getCommentBody() {
        // Also check DOM value as fallback
        if (this.commentInputRef.el && this.commentInputRef.el.value) {
            const domValue = this.commentInputRef.el.value;
            if (domValue !== this.state.newCommentBody) {
                logger.log('getCommentBody: DOM value differs from state, using DOM value', {
                    domValue: domValue,
                    stateValue: this.state.newCommentBody
                });
                this.state.newCommentBody = domValue;
            }
        }
        return this.state.newCommentBody || "";
    }

    /**
     * Cancel creating comment
     */
    onCancelCreate() {
        this.state.isCreating = false;
        this.state.newCommentBody = ""; // Clear using state
        this._propagateNewCommentBodyImmediate("");
        this.currentSelection = null;
        
        // Clear temp highlight when user cancels
        if (this.textSelectionHandler) {
            this.textSelectionHandler.clearSelection();
            this.textSelectionHandler.clearTempHighlight();
        }
        
        // Hide comment button
        this.hideCommentButton();
    }

    /**
     * Save new comment
     */
    async onSaveComment() {
        if (!this.commentManager || !this.currentSelection) return;

        // Get value directly from textarea to ensure we have the latest value
        const body = this.getCommentBody().trim();
        if (!body) {
            this.notification.add('กรุณาใส่ข้อความ comment', { type: 'warning' });
            return;
        }

        // Propagate final value to parent before saving
        this._propagateNewCommentBodyImmediate(body);

        try {
            await this.commentManager.createComment(this.currentSelection, body);
            
            this.notification.add('สร้าง comment เรียบร้อยแล้ว', { type: 'success' });
            
            // Reset state and clear textarea
            this.state.isCreating = false;
            this.state.newCommentBody = ""; // Clear using state
            this._propagateNewCommentBodyImmediate("");
            
            // IMPORTANT: Don't clear temp highlight immediately - let renderHighlights() handle it
            // The temp highlight will be replaced by permanent highlight when comments are reloaded
            // Only clear selection, not the highlight
            if (this.textSelectionHandler) {
                // Clear selection but keep temp highlight until renderHighlights() replaces it
                this.textSelectionHandler.clearSelection();
                // Don't call clearTempHighlight() - renderHighlights() will replace temp with permanent highlight
            }
            
            this.currentSelection = null;

            // Reload comments - this will render permanent highlights and replace temp highlight
            await this.loadComments();
            
            // CRITICAL: Force render highlights IMMEDIATELY after loading comments
            // Multiple attempts to ensure highlights are rendered
            if (this.commentManager) {
                // First attempt: immediate render
                try {
                    this._lastHighlightRenderTime = Date.now();
                    await this.commentManager.renderHighlights();
                    logger.log('Highlights rendered immediately after comment creation (attempt 1)', {
                        highlightsCount: this.commentManager.highlights.size,
                        commentsCount: this.commentManager.comments.length,
                        unresolvedCount: this.commentManager.comments.filter(c => !c.resolved).length
                    });
                } catch (error) {
                    logger.warn('Error rendering highlights immediately after comment creation (attempt 1):', error);
                }
                
                // Second attempt: after DOM is ready
                await new Promise(resolve => {
                    requestAnimationFrame(() => {
                        requestAnimationFrame(async () => {
                            try {
                                this._lastHighlightRenderTime = Date.now();
                                await this.commentManager.renderHighlights();
                                logger.log('Highlights rendered after DOM ready (attempt 2)', {
                                    highlightsCount: this.commentManager.highlights.size,
                                    commentsCount: this.commentManager.comments.length
                                });
                            } catch (error) {
                                logger.warn('Error rendering highlights after DOM ready (attempt 2):', error);
                            }
                            resolve();
                        });
                    });
                });
            }
            
            // Also verify highlights are visible after a short delay
            setTimeout(async () => {
                if (this.commentManager) {
                    const unresolvedComments = this.commentManager.comments.filter(c => !c.resolved);
                    const highlightsInDOM = this.commentManager.contentElement ? 
                        this.commentManager.contentElement.querySelectorAll('.o_knowledge_comment_highlight').length : 0;
                    
                    logger.log('Highlight verification after comment creation', {
                        unresolvedCommentsCount: unresolvedComments.length,
                        highlightsInDOM: highlightsInDOM,
                        highlightsInMap: this.commentManager.highlights.size
                    });
                    
                    // CRITICAL: Always force re-render to ensure highlights are visible
                    // This fixes the issue where highlights don't show until refresh
                    if (unresolvedComments.length > 0) {
                        if (highlightsInDOM < unresolvedComments.length) {
                            logger.warn('Some highlights are missing, forcing re-render', {
                                expected: unresolvedComments.length,
                                found: highlightsInDOM
                            });
                        } else {
                            logger.log('All highlights are present, but re-rendering to ensure visibility', {
                                expected: unresolvedComments.length,
                                found: highlightsInDOM
                            });
                        }
                        
                        try {
                            this._lastHighlightRenderTime = Date.now();
                            await this.commentManager.renderHighlights();
                            
                            // Verify again after re-render
                            const highlightsAfterRender = this.commentManager.contentElement ? 
                                this.commentManager.contentElement.querySelectorAll('.o_knowledge_comment_highlight').length : 0;
                            
                            logger.log('Highlights after force re-render', {
                                expected: unresolvedComments.length,
                                found: highlightsAfterRender,
                                success: highlightsAfterRender >= unresolvedComments.length
                            });
                        } catch (error) {
                            logger.error('Error force re-rendering highlights:', error);
                        }
                    }
                }
            }, 200);
            
            // After reloading, renderHighlights() should have replaced temp highlight with permanent highlight
            // Don't manually clear temp highlight here - let renderHighlights() handle it
            // It will only remove temp highlight after permanent highlight is successfully created
            logger.log('Comment creation completed, highlights should be visible now', {
                tempHighlightExists: !!(this.textSelectionHandler && this.textSelectionHandler.tempHighlight),
                tempHighlightInDOM: !!(this.textSelectionHandler && this.textSelectionHandler.tempHighlight && this.textSelectionHandler.tempHighlight.parentNode),
                commentsCount: this.commentManager ? this.commentManager.comments.length : 0,
                unresolvedCommentsCount: this.commentManager ? this.commentManager.comments.filter(c => !c.resolved).length : 0,
                highlightsCount: this.commentManager ? this.commentManager.highlights.size : 0
            });
        } catch (error) {
            logger.error('Error creating comment:', error);
            
            // Log full error details first for debugging
            logger.error('Full error details:', {
                error,
                errorType: error && error.constructor && error.constructor.name ? error.constructor.name : null,
                errorKeys: error ? Object.keys(error) : [],
                errorData: error && error.data ? error.data : null,
                errorMessage: error && error.message ? error.message : null,
                errorTraceback: (error && error.data && error.data.debug) ? error.data.debug : ((error && error.data && error.data.traceback) ? error.data.traceback : (error && error.traceback ? error.traceback : null)),
                selectionInfo: this.currentSelection,
                bodyLength: body.length,
                articleId: this.props.articleId,
                offsetsEqual: (this.currentSelection && this.currentSelection.startOffset && this.currentSelection.endOffset) ? this.currentSelection.startOffset === this.currentSelection.endOffset : false
            });
            
            // Extract error message from Odoo RPC error
            // According to Odoo 19, RPC errors have different structure
            let errorMessage = 'เกิดข้อผิดพลาดในการสร้าง comment';
            
            // Try multiple ways to extract error message (priority order)
            if (error) {
                // Method 1: Error data with arguments (most detailed)
                if (error.data && error.data.arguments && Array.isArray(error.data.arguments) && error.data.arguments.length > 0) {
                    // Odoo ValidationError usually has message as first argument
                    errorMessage = String(error.data.arguments[0]);
                }
                // Method 2: Error data with message
                else if (error.data && error.data.message) {
                    errorMessage = error.data.message;
                }
                // Method 3: Error data with debug/traceback
                else if (error.data && (error.data.debug || error.data.traceback)) {
                    const debug = error.data.debug || error.data.traceback;
                    // Extract first line of traceback which usually contains the error message
                    if (typeof debug === 'string') {
                        const lines = debug.split('\n');
                        errorMessage = lines[0] || debug.substring(0, 200);
                    } else {
                        errorMessage = String(debug).substring(0, 200);
                    }
                }
                // Method 4: Error data with name
                else if (error.data && error.data.name) {
                    errorMessage = error.data.name;
                }
                // Method 5: Direct message property
                else if (error.message) {
                    errorMessage = error.message;
                }
                // Method 6: Error arguments array
                else if (error.arguments && Array.isArray(error.arguments) && error.arguments.length > 0) {
                    errorMessage = String(error.arguments[0]);
                }
                // Method 7: Error as string
                else if (typeof error === 'string') {
                    errorMessage = error;
                }
                // Method 8: Stringify entire error for debugging
                else {
                    try {
                        errorMessage = JSON.stringify(error).substring(0, 300);
                    } catch (e) {
                        errorMessage = String(error);
                    }
                }
            }
            
            // Show detailed error message
            this.notification.add(errorMessage, { 
                type: 'danger',
                sticky: true,
                title: 'Error creating comment'
            });
        }
    }

    /**
     * Start replying to a comment
     */
    onStartReply(commentId) {
        this.state.replyingTo = commentId;
        this.state.replyBody = "";
    }

    /**
     * Cancel reply
     */
    onCancelReply() {
        this.state.replyingTo = null;
        this.state.replyBody = "";
    }

    /**
     * Save reply
     */
    async onSaveReply(parentCommentId) {
        if (!this.commentManager) return;

        const body = this.state.replyBody.trim();
        if (!body) {
            this.notification.add('กรุณาใส่ข้อความ reply', { type: 'warning' });
            return;
        }

        try {
            await this.commentManager.replyToComment(parentCommentId, body);
            
            this.notification.add('ส่ง reply เรียบร้อยแล้ว', { type: 'success' });
            
            // Reset state
            this.state.replyingTo = null;
            this.state.replyBody = "";
            
            // Reload comments
            await this.loadComments();
        } catch (error) {
            logger.error('Error replying to comment:', error);
            this.notification.add('เกิดข้อผิดพลาดในการส่ง reply', { type: 'danger' });
        }
    }

    /**
     * Toggle resolve/unresolve comment
     */
    async onToggleResolve(commentId) {
        if (!this.commentManager) return;

        const comment = this.commentManager.getComment(commentId);
        if (!comment) return;

        try {
            await this.commentManager.toggleResolve(commentId, !comment.resolved);
            
            this.notification.add(
                comment.resolved ? 'ยกเลิกการ resolve แล้ว' : 'Resolve comment แล้ว',
                { type: 'success' }
            );
            
            // Reload comments and re-render highlights
            await this.loadComments();
        } catch (error) {
            logger.error('Error toggling resolve:', error);
            this.notification.add('เกิดข้อผิดพลาดในการ resolve comment', { type: 'danger' });
        }
    }

    /**
     * Select a comment (highlight it)
     */
    onSelectComment(commentId) {
        logger.log('onSelectComment called:', {
            commentId: commentId,
            showCommentPanel: this.props.showCommentPanel
        });
        
        this.state.selectedComment = commentId;
        
        // Scroll to comment in comment panel (not the highlight in content)
        const commentElement = document.querySelector(
            `.o_knowledge_comment_item[data-comment-id="${commentId}"]`
        );
        
        if (commentElement) {
            logger.log('Scrolling to comment in panel:', {
                commentId: commentId,
                commentElementFound: true
            });
            
            // Scroll comment into view in the panel
            commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // Add highlight animation to comment item
            commentElement.classList.add('o_knowledge_comment_highlighted');
            setTimeout(() => {
                commentElement.classList.remove('o_knowledge_comment_highlighted');
            }, 2000);
        } else {
            logger.warn('Comment element not found in panel:', {
                commentId: commentId
            });
        }
        
        // Also pulse the highlight in the content area
        const highlight = document.querySelector(
            `.o_knowledge_comment_highlight[data-comment-id="${commentId}"]`
        );
        if (highlight) {
            // Pulse animation
            highlight.style.transition = 'background-color 0.3s';
            highlight.style.backgroundColor = '#ff9800';
            setTimeout(() => {
                const comment = this.commentManager && this.commentManager.getComment ? this.commentManager.getComment(commentId) : null;
                if (comment) {
                    highlight.style.backgroundColor = comment.highlight_color || '#ffeb3b';
                } else {
                    highlight.style.backgroundColor = '#ffeb3b';
                }
            }, 500);
        }
    }
    
    /**
     * Handle click on comment item in panel - scroll to highlight in article content
     * @param {number} commentId - Comment ID
     */
    onCommentItemClick(commentId) {
        // Critical: Log immediately to verify method is being called
        logger.log('=== onCommentItemClick CALLED ===', {
            commentId: commentId,
            commentIdType: typeof commentId,
            commentIdValue: commentId,
            hasCommentManager: !!this.commentManager,
            hasContentElement: !!this.props.contentElement,
            commentManagerHighlights: this.commentManager && this.commentManager.highlights ? this.commentManager.highlights.size : 0,
            allHighlightsInDOM: document.querySelectorAll('.o_knowledge_comment_highlight').length
        });
        
        logger.log('onCommentItemClick called:', {
            commentId: commentId,
            commentIdType: typeof commentId,
            hasCommentManager: !!this.commentManager,
            hasContentElement: !!this.props.contentElement,
            commentManagerHighlights: this.commentManager && this.commentManager.highlights ? this.commentManager.highlights.size : 0
        });
        
        // Set selected comment state
        this.state.selectedComment = commentId;
        
        // Convert commentId to number if it's a string
        const numericCommentId = typeof commentId === 'string' ? parseInt(commentId, 10) : commentId;
        
        // Try multiple methods to find the highlight element
        let highlight = null;
        
        // Method 1: Use commentManager highlights map (most reliable)
        if (this.commentManager && this.commentManager.highlights) {
            highlight = this.commentManager.highlights.get(numericCommentId);
            logger.log('Checking commentManager highlights map:', {
                commentId: numericCommentId,
                found: !!highlight,
                highlightsSize: this.commentManager.highlights.size,
                highlightIds: Array.from(this.commentManager.highlights.keys())
            });
        }
        
        // Method 2: If not found in map, search in DOM using contentElement
        if (!highlight || !highlight.parentNode) {
            const contentElement = this.props.contentElement;
            if (contentElement && contentElement.querySelector) {
                highlight = contentElement.querySelector(
                    `.o_knowledge_comment_highlight[data-comment-id="${numericCommentId}"]`
                );
                logger.log('Searching in contentElement:', {
                    commentId: numericCommentId,
                    found: !!highlight,
                    contentElementTag: contentElement.tagName
                });
            }
        }
        
        // Method 3: Fallback - search in entire document
        if (!highlight || !highlight.parentNode) {
            highlight = document.querySelector(
                `.o_knowledge_comment_highlight[data-comment-id="${numericCommentId}"]`
            );
            logger.log('Searching in document:', {
                commentId: numericCommentId,
                found: !!highlight
            });
        }
        
        // Method 4: Try searching with string ID as well
        if (!highlight || !highlight.parentNode) {
            highlight = document.querySelector(
                `.o_knowledge_comment_highlight[data-comment-id="${commentId}"]`
            );
            logger.log('Searching with string ID:', {
                commentId: commentId,
                found: !!highlight
            });
        }
        
        // Method 5: Try finding by iterating all highlights and checking data attribute
        if (!highlight || !highlight.parentNode) {
            const allHighlights = document.querySelectorAll('.o_knowledge_comment_highlight');
            logger.log('Method 5 - Iterating all highlights:', {
                totalHighlights: allHighlights.length,
                lookingFor: numericCommentId
            });
            for (let i = 0; i < allHighlights.length; i++) {
                const hl = allHighlights[i];
                const dataId = hl.getAttribute('data-comment-id');
                const dataIdNum = dataId ? parseInt(dataId, 10) : null;
                logger.log(`  Highlight ${i}: data-comment-id="${dataId}" (parsed: ${dataIdNum})`);
                if (dataIdNum === numericCommentId || dataId === String(numericCommentId) || dataId === String(commentId)) {
                    highlight = hl;
                    logger.log('  MATCH FOUND!');
                    break;
                }
            }
        }
        
        if (highlight && highlight.parentNode) {
            logger.log('Highlight found, scrolling to it:', {
                commentId: numericCommentId,
                highlightInDOM: !!highlight.parentNode,
                highlightText: highlight.textContent ? highlight.textContent.substring(0, 50) : null,
                highlightElement: highlight.tagName,
                dataCommentId: highlight.getAttribute('data-comment-id')
            });
            
            // Scroll to highlight smoothly
            // Use a small delay to ensure DOM is ready
            setTimeout(() => {
                highlight.scrollIntoView({ 
                    behavior: 'smooth', 
                    block: 'center',
                    inline: 'nearest'
                });
                
                // Pulse animation - change background color temporarily
                const originalBgColor = highlight.style.backgroundColor || '';
                const originalTransition = highlight.style.transition || '';
                
                // Apply pulse animation
                highlight.style.transition = 'background-color 0.3s ease, box-shadow 0.3s ease';
                highlight.style.backgroundColor = '#ff9800'; // Orange
                highlight.style.boxShadow = '0 0 8px rgba(255, 152, 0, 0.5)';
                
                // Restore original color after animation
                setTimeout(() => {
                    const comment = this.commentManager && this.commentManager.getComment ? this.commentManager.getComment(numericCommentId) : null;
                    if (comment && comment.highlight_color) {
                        highlight.style.backgroundColor = comment.highlight_color;
                    } else {
                        highlight.style.backgroundColor = '#ffeb3b'; // Default yellow
                    }
                    highlight.style.boxShadow = '';
                    
                    // Restore original transition after a moment
                    setTimeout(() => {
                        if (originalTransition) {
                            highlight.style.transition = originalTransition;
                        } else {
                            highlight.style.transition = '';
                        }
                    }, 100);
                }, 800);
            }, 100);
        } else {
            logger.warn('Highlight not found in article content:', {
                commentId: numericCommentId,
                originalCommentId: commentId,
                hasCommentManager: !!this.commentManager,
                hasHighlightsMap: !!(this.commentManager && this.commentManager.highlights),
                highlightsMapSize: this.commentManager && this.commentManager.highlights ? this.commentManager.highlights.size : 0,
                contentElementExists: !!this.props.contentElement,
                commentManagerContentElement: !!(this.commentManager && this.commentManager.contentElement),
                allHighlightsInDOM: document.querySelectorAll('.o_knowledge_comment_highlight').length
            });
            
            // Try to re-render highlights if they're missing
            if (this.commentManager && this.commentManager.highlights && this.commentManager.highlights.size === 0) {
                logger.log('Highlights map is empty, attempting to re-render highlights...');
                // Trigger re-render of highlights
                this.commentManager.renderHighlights().catch(error => {
                    logger.error('Error re-rendering highlights:', error);
                });
                
                // Wait a bit and try again
                setTimeout(() => {
                    const retryHighlight = document.querySelector(
                        `.o_knowledge_comment_highlight[data-comment-id="${numericCommentId}"]`
                    );
                    if (retryHighlight && retryHighlight.parentNode) {
                        logger.log('Highlight found after re-render, scrolling...');
                        retryHighlight.scrollIntoView({ 
                            behavior: 'smooth', 
                            block: 'center',
                            inline: 'nearest'
                        });
                        
                        // Pulse animation
                        retryHighlight.style.transition = 'background-color 0.3s ease, box-shadow 0.3s ease';
                        retryHighlight.style.backgroundColor = '#ff9800';
                        retryHighlight.style.boxShadow = '0 0 8px rgba(255, 152, 0, 0.5)';
                        
                        setTimeout(() => {
                            const comment = this.commentManager && this.commentManager.getComment ? this.commentManager.getComment(numericCommentId) : null;
                            if (comment && comment.highlight_color) {
                                retryHighlight.style.backgroundColor = comment.highlight_color;
                            } else {
                                retryHighlight.style.backgroundColor = '#ffeb3b';
                            }
                            retryHighlight.style.boxShadow = '';
                        }, 800);
                    }
                }, 500);
            }
            
            // Fallback: Just scroll to comment in panel
            const commentElement = document.querySelector(
                `.o_knowledge_comment_item[data-comment-id="${numericCommentId}"]`
            );
            if (commentElement) {
                commentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                commentElement.classList.add('o_knowledge_comment_highlighted');
                setTimeout(() => {
                    commentElement.classList.remove('o_knowledge_comment_highlighted');
                }, 2000);
            }
        }
    }

    /**
     * Cleanup
     */
    // Removed setupTextareaListener and setupTextareaObserver - using t-model with state instead

    /**
     * Propagate draft body to parent if provided
     * Use debounce to prevent too many re-renders
     * Only called on blur to avoid re-render during typing
     */
    _propagateNewCommentBody(value) {
        if (!this.props.onUpdateNewCommentBody) {
            return;
        }

        // Clear existing timer
        if (this._propagateDebounceTimer) {
            clearTimeout(this._propagateDebounceTimer);
        }

        // Debounce: only propagate after user stops typing for 1000ms (longer to avoid re-render)
        this._propagateDebounceTimer = setTimeout(() => {
            if (this.props.onUpdateNewCommentBody) {
                this.props.onUpdateNewCommentBody(value);
            }
            this._propagateDebounceTimer = null;
        }, 1000);
    }

    /**
     * Immediately propagate value (used when closing/canceling)
     */
    _propagateNewCommentBodyImmediate(value) {
        if (this._propagateDebounceTimer) {
            clearTimeout(this._propagateDebounceTimer);
            this._propagateDebounceTimer = null;
        }
        if (this.props.onUpdateNewCommentBody) {
            this.props.onUpdateNewCommentBody(value);
        }
    }

    // Removed startContinuousRestore and stopContinuousRestore - using t-model with state instead

    /**
     * Cleanup listeners
     */
    cleanup() {
        // Cleanup textarea monitoring
        if (this._textareaInputHandler && this.commentInputRef.el) {
            this.commentInputRef.el.removeEventListener('input', this._textareaInputHandler, { capture: true });
            this._textareaInputHandler = null;
        }
        if (this._textareaBeforeInputHandler && this.commentInputRef.el) {
            this.commentInputRef.el.removeEventListener('beforeinput', this._textareaBeforeInputHandler, { capture: true });
            this._textareaBeforeInputHandler = null;
        }
        if (this._textareaValueObserver) {
            this._textareaValueObserver.disconnect();
            this._textareaValueObserver = null;
        }
        if (this._textareaValueCheckInterval) {
            clearInterval(this._textareaValueCheckInterval);
            this._textareaValueCheckInterval = null;
        }
        
        // Cleanup debounce timer
        if (this._propagateDebounceTimer) {
            clearTimeout(this._propagateDebounceTimer);
            this._propagateDebounceTimer = null;
        }
        
        // Cleanup MutationObserver if it exists (for backward compatibility)
        if (this._textareaObserver) {
            this._textareaObserver.disconnect();
            this._textareaObserver = null;
        }
        
        // Cleanup highlight observer
        if (this._highlightObserver) {
            this._highlightObserver.disconnect();
            this._highlightObserver = null;
        }

        // Cleanup content observer
        if (this._contentObserver) {
            this._contentObserver.disconnect();
            this._contentObserver = null;
        }
        
        // Cleanup highlight check interval
        if (this._highlightCheckInterval) {
            clearInterval(this._highlightCheckInterval);
            this._highlightCheckInterval = null;
        }
        
        // Cleanup hide timer
        if (this._hideButtonTimer) {
            clearTimeout(this._hideButtonTimer);
            this._hideButtonTimer = null;
        }
        
        // Cleanup selection change timeout
        if (this._selectionChangeTimeout) {
            clearTimeout(this._selectionChangeTimeout);
            this._selectionChangeTimeout = null;
        }
        
        // Cleanup selection process timer
        if (this._selectionProcessTimer) {
            clearTimeout(this._selectionProcessTimer);
            this._selectionProcessTimer = null;
        }
        
        // Cleanup selection stability check interval
        if (this._selectionStabilityCheckInterval) {
            clearInterval(this._selectionStabilityCheckInterval);
            this._selectionStabilityCheckInterval = null;
        }
        
        // Remove event listeners
        if (this.textSelectionHandler && this.textSelectionHandler.contentElement) {
            const contentElement = this.textSelectionHandler.contentElement;
            
            if (this._mousedownListener) {
                contentElement.removeEventListener('mousedown', this._mousedownListener);
                this._mousedownListener = null;
            }
            
            if (this._mousemoveListener) {
                contentElement.removeEventListener('mousemove', this._mousemoveListener);
                this._mousemoveListener = null;
            }
            
            if (this._mouseupListener) {
                contentElement.removeEventListener('mouseup', this._mouseupListener);
                this._mouseupListener = null;
            }
        }
        
        if (this._selectionChangeListener) {
            document.removeEventListener('selectionchange', this._selectionChangeListener);
            this._selectionChangeListener = null;
        }
        
        // Reset selection flag
        this._isSelecting = false;

        // Cleanup text selection handler
        if (this.textSelectionHandler) {
            this.textSelectionHandler.cleanup();
            this.textSelectionHandler = null;
        }
        // Remove temp highlight spans that may remain
        document.querySelectorAll('.o_knowledge_comment_temp_highlight').forEach(el => {
            el.replaceWith(...el.childNodes);
        });

        // Cleanup comment manager
        if (this.commentManager) {
            this.commentManager.clearAllHighlights();
        }
        this.hideCommentButton();
    }

    /**
     * Get showCommentPanel prop value (for template access)
     */
    getShowCommentPanel() {
        return this.props.showCommentPanel ?? false;
    }

    /**
     * Get display comments (filter by resolved status)
     */
    getDisplayComments() {
        const comments = this.state.comments || [];
        
        // Helper function to recursively check if comment or its replies are unresolved
        const hasUnresolved = (comment) => {
            if (!comment.resolved) {
                return true;
            }
            if (comment.replies && comment.replies.length > 0) {
                return comment.replies.some(reply => hasUnresolved(reply));
            }
            return false;
        };
        
        // Helper function to recursively count unresolved comments
        const countUnresolved = (commentList) => {
            let count = 0;
            commentList.forEach(comment => {
                if (!comment.resolved) {
                    count++;
                }
                if (comment.replies && comment.replies.length > 0) {
                    count += countUnresolved(comment.replies);
                }
            });
            return count;
        };
        
        logger.log('getDisplayComments called:', {
            totalComments: comments.length,
            showResolved: this.state.showResolved,
            resolvedCount: comments.filter(c => c.resolved).length,
            unresolvedCount: comments.filter(c => !c.resolved).length,
            unresolvedIncludingReplies: countUnresolved(comments)
        });
        
        if (this.state.showResolved) {
            return comments;
        }
        
        // Filter: include comments that are unresolved OR have unresolved replies
        const filtered = comments.filter(c => hasUnresolved(c));
        
        logger.log('getDisplayComments filtered result:', {
            filteredCount: filtered.length,
            filteredIds: filtered.map(c => c.id),
            unresolvedIncludingReplies: countUnresolved(filtered)
        });
        return filtered;
    }

    /**
     * Format date for display in Thailand timezone (UTC+7)
     * Odoo sends datetime in format: "YYYY-MM-DD HH:MM:SS" (stored in UTC)
     * We need to properly parse and convert to Thailand timezone
     */
    formatDate(dateString) {
        if (!dateString) return '';
        
        try {
            // Odoo sends datetime in format: "YYYY-MM-DD HH:MM:SS" or "YYYY-MM-DDTHH:MM:SS"
            // Odoo stores datetime in UTC but sends without timezone indicator
            // We need to treat it as UTC and convert to Thailand timezone
            
            let date;
            if (typeof dateString === 'string') {
                // Normalize the string
                let normalizedString = dateString.trim();
                
                // Replace first space with T if not already in ISO format
                // Format: "2025-12-07 14:25:00" -> "2025-12-07T14:25:00"
                if (normalizedString.includes(' ') && !normalizedString.includes('T')) {
                    normalizedString = normalizedString.replace(' ', 'T');
                }
                
                // Remove microseconds if present (e.g., ".123456")
                normalizedString = normalizedString.replace(/\.\d{6}/, '');
                
                // Check if timezone indicator exists
                // Format can be: "Z", "+07:00", "-05:00", etc.
                const hasTimezone = normalizedString.endsWith('Z') || 
                                   /[+-]\d{2}:?\d{2}$/.test(normalizedString);
                
                // If no timezone, treat as UTC by adding 'Z'
                // This is critical because Odoo stores datetime in UTC
                if (!hasTimezone) {
                    normalizedString = normalizedString + 'Z';
                }
                
                date = new Date(normalizedString);
            } else {
                date = new Date(dateString);
            }
            
            // Validate date
            if (isNaN(date.getTime())) {
                logger.warn('Invalid date string:', dateString);
                return dateString; // Return original string if parsing fails
            }
            
            // Log for debugging (can be removed in production)
            // logger.log('formatDate:', {
            //     original: dateString,
            //     parsed: date.toISOString(),
            //     utcTime: date.toUTCString()
            // });
            
            // Use Intl.DateTimeFormat for better timezone handling
            // Convert to Thailand timezone (Asia/Bangkok, UTC+7)
            const formatter = new Intl.DateTimeFormat('th-TH', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                timeZone: 'Asia/Bangkok' // Force Thailand timezone (UTC+7)
            });
            
            const formatted = formatter.format(date);
            
            // Log result for debugging (can be removed in production)
            // logger.log('formatDate result:', {
            //     original: dateString,
            //     formatted: formatted,
            //     utcHour: date.getUTCHours(),
            //     thaiHour: new Date(formatter.formatToParts(date).find(p => p.type === 'hour').value)
            // });
            
            return formatted;
        } catch (error) {
            logger.error('Error formatting date:', error, dateString);
            return dateString; // Return original string on error
        }
    }

    /**
     * Get avatar URL for user
     * @param {Object} comment - Comment object with author_id and author_image
     * @returns {string} Avatar URL or placeholder
     */
    getAvatarUrl(comment) {
        if (!comment.author_id || !comment.author_id[0]) {
            return '/web/static/img/avatar.png';
        }

        // If we have author_image (base64 or binary), use it
        if (comment.author_image) {
            // If it's base64, return as data URL
            if (typeof comment.author_image === 'string' && comment.author_image.startsWith('data:')) {
                return comment.author_image;
            }
            // If it's binary data, convert to base64 data URL
            // Note: In Odoo, binary fields are returned as base64 strings
            if (typeof comment.author_image === 'string') {
                return `data:image/png;base64,${comment.author_image}`;
            }
        }

        // Fallback: Use Odoo's web/image route
        return `/web/image/res.users/${comment.author_id[0]}/image_128`;
    }

    /**
     * Load current user information
     */
    async loadCurrentUser() {
        try {
            const userId = this.orm.userId;
            if (userId) {
                const users = await this.orm.read(
                    'res.users',
                    [[userId]],
                    ['id', 'name', 'image_128']
                );
                if (users && users.length > 0) {
                    this.state.currentUser = users[0];
                    logger.log('Current user loaded', {
                        userId: users[0].id,
                        userName: users[0].name
                    });
                }
            }
        } catch (error) {
            logger.warn('Failed to load current user:', error);
            this.state.currentUser = null;
        }
    }

    /**
     * Get current user avatar URL
     * @returns {string} Avatar URL
     */
    getCurrentUserAvatar() {
        if (!this.state.currentUser || !this.state.currentUser.id) {
            return '/web/static/img/avatar.png';
        }

        // If we have image_128, use it
        if (this.state.currentUser.image_128) {
            // If it's base64, return as data URL
            if (typeof this.state.currentUser.image_128 === 'string' && this.state.currentUser.image_128.startsWith('data:')) {
                return this.state.currentUser.image_128;
            }
            // If it's binary data, convert to base64 data URL
            if (typeof this.state.currentUser.image_128 === 'string') {
                return `data:image/png;base64,${this.state.currentUser.image_128}`;
            }
        }

        // Fallback: Use Odoo's web/image route
        return `/web/image/res.users/${this.state.currentUser.id}/image_128`;
    }

    /**
     * Get current user name
     * @returns {string} User name
     */
    getCurrentUserName() {
        if (!this.state.currentUser || !this.state.currentUser.name) {
            return 'User';
        }
        return this.state.currentUser.name;
    }

    /**
     * Get markup function for rendering HTML content
     * This is needed to properly render HTML in t-out directive
     */
    markup(html) {
        if (!html) return markup('');
        // If already a markup object, return it
        if (html && typeof html === 'object' && html.isMarkup) {
            return html;
        }
        // Convert string to markup
        return markup(String(html));
    }

    /**
     * Close comment panel
     */
    onCloseCommentPanel() {
        if (this.props.onClose) {
            this.props.onClose();
        } else {
            // Fallback: hide comment panel by hiding the parent element
            const panel = this.el && this.el.closest('.o_knowledge_comment_panel');
            if (panel) {
                panel.style.display = 'none';
            }
        }
    }
}
