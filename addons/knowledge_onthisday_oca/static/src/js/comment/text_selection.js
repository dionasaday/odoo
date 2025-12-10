/** @odoo-module **/

import { logger } from '../utils/logger';

/**
 * Text Selection Handler
 * 
 * Handles text selection in article content and provides utilities
 * for calculating offsets and storing selection metadata.
 */
export class TextSelectionHandler {
    constructor(contentElement) {
        this.contentElement = contentElement;
        this.tempHighlight = null;
    }

    /**
     * Get current text selection
     * @returns {Object|null} Selection info with text, offsets, and range
     */
    getSelection() {
        const selection = window.getSelection();
        if (!selection || selection.rangeCount === 0) {
            return null;
        }

        const range = selection.getRangeAt(0);
        const selectedText = range.toString().trim();

        if (!selectedText) {
            return null;
        }

        // Check if selection is within content element
        if (!this.contentElement.contains(range.commonAncestorContainer)) {
            return null;
        }

        // Calculate offsets from plain text content
        const plainText = this.getPlainText(this.contentElement);
        const startOffset = this.getTextOffset(this.contentElement, range.startContainer, range.startOffset);
        const endOffset = this.getTextOffset(this.contentElement, range.endContainer, range.endOffset);

        // Get element selector for the container
        const elementSelector = this.getElementSelector(range.commonAncestorContainer);

        // Clone range for later use
        const clonedRange = range.cloneRange();

        return {
            text: selectedText,
            startOffset,
            endOffset,
            elementSelector,
            range: clonedRange,
            startContainer: range.startContainer,
            startOffset_node: range.startOffset,
            endContainer: range.endContainer,
            endOffset_node: range.endOffset,
        };
    }

    /**
     * Get plain text content from HTML element
     * @param {HTMLElement} element 
     * @returns {string} Plain text content
     */
    getPlainText(element) {
        if (!element) return '';
        
        // Clone element to avoid modifying original
        const clone = element.cloneNode(true);
        
        // Remove script and style elements
        const scripts = clone.querySelectorAll('script, style');
        scripts.forEach(el => el.remove());
        
        // Get text content
        return clone.textContent || clone.innerText || '';
    }

    /**
     * Calculate text offset for a node and offset within content element
     * @param {HTMLElement} rootElement - Root content element
     * @param {Node} node - Node containing the selection start/end
     * @param {number} offset - Character offset within the node
     * @returns {number} Character offset from start of plain text content
     */
    getTextOffset(rootElement, node, offset) {
        let totalOffset = 0;
        const walker = document.createTreeWalker(
            rootElement,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        let currentNode;
        while (currentNode = walker.nextNode()) {
            if (currentNode === node) {
                return totalOffset + offset;
            }
            totalOffset += currentNode.textContent.length;
        }

        // If node not found, return total length
        return this.getPlainText(rootElement).length;
    }

    /**
     * Get CSS selector for an element
     * @param {Node} element 
     * @returns {string} CSS selector
     */
    getElementSelector(element) {
        if (!element || element.nodeType !== Node.ELEMENT_NODE) {
            // If it's a text node, get parent element
            element = element.parentElement;
        }

        if (!element) return '';

        // Try to build a unique selector
        const path = [];
        while (element && element !== this.contentElement) {
            let selector = element.nodeName.toLowerCase();
            
            if (element.id) {
                selector += `#${element.id}`;
                path.unshift(selector);
                break;
            }
            
            if (element.className && typeof element.className === 'string') {
                const classes = element.className.trim().split(/\s+/).filter(Boolean);
                if (classes.length > 0) {
                    selector += '.' + classes[0];
                }
            }

            // Add nth-child if needed for uniqueness
            const siblings = Array.from(element.parentElement?.children || []);
            const index = siblings.indexOf(element);
            if (index > 0) {
                selector += `:nth-child(${index + 1})`;
            }

            path.unshift(selector);
            element = element.parentElement;
        }

        return path.join(' > ') || '';
    }

    /**
     * Highlight text with comment marker
     * @param {number} commentId - Comment ID
     * @param {number} startOffset - Start character offset
     * @param {number} endOffset - End character offset
     * @param {string} color - Highlight color (default: yellow)
     */
    highlightText(commentId, startOffset, endOffset, color = '#ffeb3b') {
        // This will be implemented when we create the highlight manager
        // For now, just a placeholder
        logger.log(`Highlighting text: ${startOffset}-${endOffset} with color ${color}`);
    }

    /**
     * Remove highlight for a comment
     * @param {number} commentId - Comment ID
     */
    removeHighlight(commentId) {
        const highlights = this.contentElement.querySelectorAll(
            `.o_knowledge_comment_highlight[data-comment-id="${commentId}"]`
        );
        highlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize();
        });
    }

    /**
     * Restore selection from stored range info
     * @param {Object} selectionInfo - Selection info with startContainer, endContainer, offsets
     */
    restoreSelection(selectionInfo) {
        try {
            const selection = window.getSelection();
            const range = document.createRange();
            
            range.setStart(selectionInfo.startContainer, selectionInfo.startOffset_node);
            range.setEnd(selectionInfo.endContainer, selectionInfo.endOffset_node);
            
            selection.removeAllRanges();
            selection.addRange(range);
        } catch (error) {
            logger.error('Error restoring selection:', error);
        }
    }

    /**
     * Clear current selection
     */
    clearSelection() {
        const selection = window.getSelection();
        if (selection && selection.rangeCount > 0) {
            selection.removeAllRanges();
        }
        this.clearTempHighlight();
    }

    /**
     * Apply a temporary highlight so selection stays visible when native selection is cleared
     * @param {Range} range 
     */
    applyTempHighlight(range) {
        // CRITICAL: Clear ALL existing temp highlights first (not just the one in this handler)
        // Remove all temp highlights from DOM to prevent old highlights from persisting
        if (this.contentElement) {
            const allTempHighlights = this.contentElement.querySelectorAll('.o_knowledge_comment_temp_highlight');
            allTempHighlights.forEach(highlight => {
                const parent = highlight.parentNode;
                if (parent) {
                    const text = highlight.textContent || highlight.innerText;
                    parent.replaceChild(document.createTextNode(text), highlight);
                    parent.normalize();
                }
            });
        }
        
        // Also clear the reference in this handler
        this.clearTempHighlight();
        
        if (!range) return;
        
        // Save the selected text BEFORE any manipulation
        // This is critical because after extractContents(), range will collapse
        const selectedText = range.toString();
        
        // Validate that we have actual text content
        if (!selectedText || !selectedText.trim()) {
            logger.warn('Cannot apply highlight: range has no text content', {
                rangeCollapsed: range.collapsed,
                startContainer: range.startContainer && range.startContainer.nodeName,
                endContainer: range.endContainer && range.endContainer.nodeName,
                startOffset: range.startOffset,
                endOffset: range.endOffset
            });
            return;
        }
        
        const tempSpan = document.createElement('span');
        tempSpan.className = 'o_knowledge_comment_temp_highlight';
        // Use setProperty with important to prevent style overrides
        tempSpan.style.setProperty('background-color', '#ffeb3b', 'important');
        tempSpan.style.setProperty('border-radius', '2px', 'important');
        tempSpan.style.setProperty('display', 'inline', 'important');
        tempSpan.style.setProperty('user-select', 'text', 'important');
        tempSpan.style.setProperty('-webkit-user-select', 'text', 'important');
        tempSpan.style.setProperty('-moz-user-select', 'text', 'important');
        tempSpan.style.setProperty('-ms-user-select', 'text', 'important');
        tempSpan.style.setProperty('visibility', 'visible', 'important');
        tempSpan.style.setProperty('opacity', '1', 'important');
        tempSpan.style.setProperty('position', 'relative', 'important');
        tempSpan.style.setProperty('z-index', '1', 'important');
        
        // CRITICAL: Save selected text FIRST before any DOM manipulation
        // This ensures we have the correct text even if range gets corrupted
        const selectedTextBeforeManipulation = selectedText;
        logger.log('Applying temp highlight with selected text:', {
            selectedText: selectedTextBeforeManipulation,
            selectedLength: selectedTextBeforeManipulation.length,
            rangeCollapsed: range.collapsed
        });
        
        try {
            // Use improved method that properly handles multi-node selections
            // First, try using surroundContents which is more reliable for single-node selections
            // If that fails, use extractContents as fallback
            
            // Clone the range to preserve the original
            const workingRange = range.cloneRange();
            
            // Verify range is valid
            if (workingRange.collapsed) {
                logger.warn('Cannot apply highlight: range is collapsed');
                return;
            }
            
            // Try surroundContents first (simpler and preserves content better)
            try {
                workingRange.surroundContents(tempSpan);
                this.tempHighlight = tempSpan;
                
                // CRITICAL: Restore selection after applying highlight so user can copy
                // surroundContents may collapse the selection, so we need to restore it
                // Use requestAnimationFrame to ensure DOM is fully updated before restoring selection
                requestAnimationFrame(() => {
                    try {
                        const selection = window.getSelection();
                        if (selection && tempSpan && tempSpan.parentNode) {
                            // Create a new range that covers the highlight element
                            const newRange = document.createRange();
                            newRange.selectNodeContents(tempSpan);
                            selection.removeAllRanges();
                            selection.addRange(newRange);
                            logger.log('Selection restored after applying highlight with surroundContents');
                        }
                    } catch (selectionError) {
                        logger.warn('Failed to restore selection after surroundContents:', selectionError);
                    }
                });
                
                logger.log('Highlight applied using surroundContents');
            } catch (surroundError) {
                // surroundContents failed (likely because range spans multiple elements)
                // Use extractContents method instead
                logger.log('surroundContents failed, using extractContents:', surroundError);
                
                // Clone range again for extractContents
                const extractRange = range.cloneRange();
                
                // Extract all contents from the range
                const contents = extractRange.extractContents();
                
                // Verify contents were extracted
                if (!contents || contents.childNodes.length === 0) {
                    throw new Error('extractContents returned empty fragment');
                }
                
                // Append extracted contents to span
                tempSpan.appendChild(contents);
                
                // Insert the span at the start position
                extractRange.insertNode(tempSpan);
                
                this.tempHighlight = tempSpan;
                
                // CRITICAL: Restore selection after applying highlight so user can copy
                // extractContents will collapse the selection, so we need to restore it
                // Use requestAnimationFrame to ensure DOM is fully updated before restoring selection
                requestAnimationFrame(() => {
                    try {
                        const selection = window.getSelection();
                        if (selection && tempSpan && tempSpan.parentNode) {
                            // Create a new range that covers the highlight element
                            const newRange = document.createRange();
                            newRange.selectNodeContents(tempSpan);
                            selection.removeAllRanges();
                            selection.addRange(newRange);
                            logger.log('Selection restored after applying highlight with extractContents');
                        }
                    } catch (selectionError) {
                        logger.warn('Failed to restore selection after extractContents:', selectionError);
                    }
                });
                
                logger.log('Highlight applied using extractContents');
            }
            
            // Verify highlight is in DOM
            if (!this.tempHighlight || !this.tempHighlight.parentNode) {
                throw new Error('Highlight not in DOM after creation');
            }
            
            // CRITICAL: Verify the highlight contains ALL selected text
            const highlightText = this.tempHighlight.textContent || this.tempHighlight.innerText || '';
            const highlightTrimmed = highlightText.trim();
            const selectedTrimmed = selectedTextBeforeManipulation.trim();
            
            // Critical check: if highlight has no content, remove it immediately
            if (!highlightTrimmed) {
                logger.error('Highlight created but has no content, removing...', {
                    selectedText: selectedTrimmed,
                    highlightText: highlightText,
                    rangeCollapsed: range.collapsed
                });
                if (this.tempHighlight.parentNode) {
                    this.tempHighlight.parentNode.removeChild(this.tempHighlight);
                }
                this.tempHighlight = null;
                return;
            }
            
            // Normalize whitespace for comparison
            const highlightNormalized = highlightTrimmed.replace(/\s+/g, ' ').trim();
            const selectedNormalized = selectedTrimmed.replace(/\s+/g, ' ').trim();
            
            // Calculate length difference
            const lengthDiff = Math.abs(selectedNormalized.length - highlightNormalized.length);
            const missingPercentage = selectedNormalized.length > 0 ? 
                ((selectedNormalized.length - highlightNormalized.length) / selectedNormalized.length * 100) : 0;
            
            // CRITICAL: Check if highlight text matches selected text (not just length)
            // If the texts are completely different, it means we're highlighting the wrong content
            const textsMatch = highlightNormalized === selectedNormalized || 
                             highlightNormalized.includes(selectedNormalized) ||
                             selectedNormalized.includes(highlightNormalized);
            
            // If highlight text doesn't match selected text at all, it's wrong
            if (!textsMatch && highlightNormalized.length < selectedNormalized.length * 0.8) {
                logger.error('Highlight text does not match selected text! Removing incorrect highlight', {
                    selectedText: selectedNormalized.substring(0, 100),
                    highlightText: highlightNormalized.substring(0, 100),
                    selectedLength: selectedNormalized.length,
                    highlightLength: highlightNormalized.length,
                    difference: lengthDiff,
                    missingPercentage: missingPercentage.toFixed(1) + '%'
                });
                
                // Remove the incorrect highlight
                if (this.tempHighlight && this.tempHighlight.parentNode) {
                    this.tempHighlight.parentNode.removeChild(this.tempHighlight);
                }
                this.tempHighlight = null;
                
                // Throw error to trigger fallback method
                throw new Error(`Highlight text does not match selected text: "${highlightNormalized.substring(0, 50)}" vs "${selectedNormalized.substring(0, 50)}"`);
            }
            
            // CRITICAL: If highlight is missing more than 5% of content, it's incomplete
            if (highlightNormalized.length < selectedNormalized.length * 0.95) {
                logger.warn('Highlight content is incomplete, removing and retrying with improved method', {
                    selectedLength: selectedNormalized.length,
                    highlightLength: highlightNormalized.length,
                    difference: lengthDiff,
                    missingPercentage: missingPercentage.toFixed(1) + '%',
                    selectedText: selectedNormalized.substring(0, 100),
                    highlightText: highlightNormalized.substring(0, 100)
                });
                
                // Remove the incomplete highlight
                if (this.tempHighlight && this.tempHighlight.parentNode) {
                    this.tempHighlight.parentNode.removeChild(this.tempHighlight);
                }
                this.tempHighlight = null;
                
                // Throw error to trigger fallback method
                throw new Error(`Highlight content incomplete: ${highlightNormalized.length}/${selectedNormalized.length} chars (${missingPercentage.toFixed(1)}% missing)`);
            }
            
            // Verify that highlight text matches selected text
            if (highlightNormalized !== selectedNormalized && 
                !highlightNormalized.includes(selectedNormalized) && 
                !selectedNormalized.includes(highlightNormalized)) {
                logger.warn('Highlight text may not match selected text exactly', {
                    selectedText: selectedNormalized.substring(0, 50),
                    highlightText: highlightNormalized.substring(0, 50),
                    selectedLength: selectedNormalized.length,
                    highlightLength: highlightNormalized.length
                });
            }
            
            // Success - log if there's any minor difference
            if (lengthDiff > 3) {
                logger.log('Highlight applied successfully (minor differences due to DOM structure)', {
                    selectedLength: selectedNormalized.length,
                    highlightLength: highlightNormalized.length,
                    difference: lengthDiff,
                    selectedText: selectedNormalized.substring(0, 50),
                    highlightText: highlightNormalized.substring(0, 50)
                });
            } else {
                logger.log('Highlight applied successfully - text matches', {
                    selectedLength: selectedNormalized.length,
                    highlightLength: highlightNormalized.length,
                    selectedText: selectedNormalized.substring(0, 50)
                });
            }
            
        } catch (error) {
            logger.error('Error applying temp highlight, trying improved fallback method:', error);
            
            // Improved fallback method using splitText to properly handle multi-node selections
            try {
                // Need to use a fresh range since the previous one may be corrupted
                const fallbackRange = range.cloneRange();
                const fallbackSelectedText = fallbackRange.toString();
                
                if (!fallbackSelectedText || !fallbackSelectedText.trim()) {
                    logger.error('Cannot apply fallback highlight: no selected text in range');
                    return;
                }
                
                // Get start and end containers
                let startContainer = fallbackRange.startContainer;
                let endContainer = fallbackRange.endContainer;
                let startOffset = fallbackRange.startOffset;
                let endOffset = fallbackRange.endOffset;
                
                // Split text nodes at boundaries to get clean nodes to wrap
                if (startContainer.nodeType === Node.TEXT_NODE) {
                    if (startOffset > 0) {
                        startContainer = startContainer.splitText(startOffset);
                        startOffset = 0;
                    }
                }
                
                if (endContainer.nodeType === Node.TEXT_NODE) {
                    if (endOffset > 0 && endOffset < endContainer.textContent.length) {
                        endContainer.splitText(endOffset);
                    }
                }
                
                // Collect all nodes between start and end
                const nodesToWrap = [];
                const commonAncestor = fallbackRange.commonAncestorContainer;
                const container = commonAncestor.nodeType === Node.TEXT_NODE ? 
                                 commonAncestor.parentNode : commonAncestor;
                
                // Find all nodes in the range
                const walker = document.createTreeWalker(
                    container,
                    NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
                    {
                        acceptNode: (node) => {
                            // Check if node is within range
                            const rangeStart = fallbackRange.compareBoundaryPoints(Range.START_TO_START, document.createRange().selectNode(node));
                            const rangeEnd = fallbackRange.compareBoundaryPoints(Range.END_TO_END, document.createRange().selectNode(node));
                            
                            if (rangeStart >= 0 && rangeEnd <= 0) {
                                return NodeFilter.FILTER_ACCEPT;
                            }
                            return NodeFilter.FILTER_REJECT;
                        }
                    }
                );
                
                let node;
                while (node = walker.nextNode()) {
                    if (node.nodeType === Node.TEXT_NODE) {
                        nodesToWrap.push(node);
                    } else if (node.nodeType === Node.ELEMENT_NODE && 
                               !node.classList.contains('o_knowledge_comment_highlight') &&
                               !node.classList.contains('o_knowledge_comment_temp_highlight')) {
                        // Include element if it's fully within range
                        nodesToWrap.push(node);
                    }
                }
                
                // Alternative: Use simpler approach - collect nodes between start and end sequentially
                if (nodesToWrap.length === 0) {
                    // Start with startContainer
                    if (startContainer.nodeType === Node.TEXT_NODE) {
                        nodesToWrap.push(startContainer);
                    }
                    
                    // Walk through DOM from start to end
                    let current = startContainer;
                    while (current && current !== endContainer) {
                        // If current is an element, get its next sibling
                        if (current.nodeType === Node.ELEMENT_NODE) {
                            current = current.nextSibling;
                        } else {
                            current = current.nextSibling || current.parentNode.nextSibling;
                        }
                        
                        if (!current) break;
                        
                        // Check if we've reached or passed endContainer
                        if (current === endContainer || 
                            (current.compareDocumentPosition && current.compareDocumentPosition(endContainer) & Node.DOCUMENT_POSITION_FOLLOWING)) {
                            if (current.nodeType === Node.TEXT_NODE) {
                                nodesToWrap.push(current);
                            }
                            break;
                        }
                        
                        // Add text nodes and elements (excluding highlights)
                        if (current.nodeType === Node.TEXT_NODE) {
                            nodesToWrap.push(current);
                        } else if (current.nodeType === Node.ELEMENT_NODE && 
                                   !current.classList.contains('o_knowledge_comment_highlight') &&
                                   !current.classList.contains('o_knowledge_comment_temp_highlight')) {
                            // Check if element is fully within range
                            const elementText = current.textContent || '';
                            if (elementText.length > 0) {
                                nodesToWrap.push(current);
                            }
                        }
                    }
                }
                
                // Wrap the nodes using a more reliable method
                if (nodesToWrap.length > 0) {
                    const firstNode = nodesToWrap[0];
                    const parent = firstNode.parentNode;
                    
                    if (parent) {
                        // Create a new range that encompasses all nodes
                        const wrapRange = document.createRange();
                        wrapRange.setStartBefore(firstNode);
                        
                        // Find the last node to wrap
                        let lastNode = nodesToWrap[nodesToWrap.length - 1];
                        if (lastNode.nodeType === Node.TEXT_NODE) {
                            wrapRange.setEndAfter(lastNode);
                        } else {
                            wrapRange.setEndAfter(lastNode.lastChild || lastNode);
                        }
                        
                        // Extract all nodes using cloneContents to preserve DOM
                        const clonedContents = wrapRange.cloneContents();
                        
                        // Move cloned contents to span
                        while (clonedContents.firstChild) {
                            tempSpan.appendChild(clonedContents.firstChild);
                        }
                        
                        // Remove original nodes and insert span
                        wrapRange.deleteContents();
                        wrapRange.insertNode(tempSpan);
                        
                        this.tempHighlight = tempSpan;
                        
                        // CRITICAL: Restore selection after applying highlight so user can copy
                        // Use requestAnimationFrame to ensure DOM is fully updated before restoring selection
                        requestAnimationFrame(() => {
                            try {
                                const selection = window.getSelection();
                                if (selection && tempSpan && tempSpan.parentNode) {
                                    // Create a new range that covers the highlight element
                                    const newRange = document.createRange();
                                    newRange.selectNodeContents(tempSpan);
                                    selection.removeAllRanges();
                                    selection.addRange(newRange);
                                    logger.log('Selection restored after applying highlight with fallback method');
                                }
                            } catch (selectionError) {
                                logger.warn('Failed to restore selection after fallback method:', selectionError);
                            }
                        });
                        
                        // Verify content again
                        const finalText = this.tempHighlight.textContent || this.tempHighlight.innerText || '';
                        const finalNormalized = finalText.replace(/\s+/g, ' ').trim();
                        const selectedNormalized = fallbackSelectedText.replace(/\s+/g, ' ').trim();
                        
                        if (finalNormalized.length < selectedNormalized.length * 0.95) {
                            logger.error('Fallback method also produced incomplete highlight, trying final method', {
                                selectedLength: selectedNormalized.length,
                                finalLength: finalNormalized.length,
                                missingPercentage: ((selectedNormalized.length - finalNormalized.length) / selectedNormalized.length * 100).toFixed(1) + '%'
                            });
                            
                            // Remove incomplete highlight
                            if (this.tempHighlight.parentNode) {
                                this.tempHighlight.parentNode.removeChild(this.tempHighlight);
                            }
                            this.tempHighlight = null;
                            
                            // Final fallback: Use original range and cloneContents
                            const finalRange = range.cloneRange();
                            const finalContents = finalRange.cloneContents();
                            
                            // Create new span with cloned contents
                            const finalSpan = document.createElement('span');
                            finalSpan.className = 'o_knowledge_comment_temp_highlight';
                            finalSpan.style.setProperty('background-color', '#ffeb3b', 'important');
                            finalSpan.style.setProperty('border-radius', '2px', 'important');
                            finalSpan.style.setProperty('display', 'inline', 'important');
                            finalSpan.style.setProperty('user-select', 'text', 'important');
                            finalSpan.style.setProperty('-webkit-user-select', 'text', 'important');
                            finalSpan.style.setProperty('-moz-user-select', 'text', 'important');
                            finalSpan.style.setProperty('-ms-user-select', 'text', 'important');
                            finalSpan.style.setProperty('visibility', 'visible', 'important');
                            finalSpan.style.setProperty('opacity', '1', 'important');
                            finalSpan.style.setProperty('position', 'relative', 'important');
                            finalSpan.style.setProperty('z-index', '1', 'important');
                            
                            // Move contents to span
                            while (finalContents.firstChild) {
                                finalSpan.appendChild(finalContents.firstChild);
                            }
                            
                            // Replace range content with span
                            finalRange.deleteContents();
                            finalRange.insertNode(finalSpan);
                            
                            this.tempHighlight = finalSpan;
                            
                            // CRITICAL: Restore selection after applying highlight so user can copy
                            // Use requestAnimationFrame to ensure DOM is fully updated before restoring selection
                            requestAnimationFrame(() => {
                                try {
                                    const selection = window.getSelection();
                                    if (selection && finalSpan && finalSpan.parentNode) {
                                        // Create a new range that covers the highlight element
                                        const newRange = document.createRange();
                                        newRange.selectNodeContents(finalSpan);
                                        selection.removeAllRanges();
                                        selection.addRange(newRange);
                                        logger.log('Selection restored after applying highlight with final fallback method');
                                    }
                                } catch (selectionError) {
                                    logger.warn('Failed to restore selection after final fallback method:', selectionError);
                                }
                            });
                            
                            // Final verification
                            const finalFinalText = this.tempHighlight.textContent || this.tempHighlight.innerText || '';
                            const finalFinalNormalized = finalFinalText.replace(/\s+/g, ' ').trim();
                            
                            if (finalFinalNormalized.length < selectedNormalized.length * 0.95) {
                                logger.error('All methods failed to preserve complete text, removing highlight', {
                                    selectedLength: selectedNormalized.length,
                                    finalLength: finalFinalNormalized.length
                                });
                                if (this.tempHighlight.parentNode) {
                                    this.tempHighlight.parentNode.removeChild(this.tempHighlight);
                                }
                                this.tempHighlight = null;
                            } else {
                                logger.log('Highlight applied using final fallback method', {
                                    selectedLength: selectedNormalized.length,
                                    finalLength: finalFinalNormalized.length
                                });
                            }
                        } else {
                            logger.log('Highlight applied using improved fallback method', {
                                selectedLength: selectedNormalized.length,
                                finalLength: finalNormalized.length
                            });
                        }
                    }
                } else {
                    logger.error('No nodes found to wrap in fallback method');
                    this.tempHighlight = null;
                }
            } catch (fallbackError) {
                logger.error('Error in fallback highlight method:', fallbackError);
                this.tempHighlight = null;
            }
        }
        
        // Add data attribute to help identify it
        if (this.tempHighlight) {
            this.tempHighlight.setAttribute('data-temp-highlight', 'true');
            this.tempHighlight.setAttribute('data-highlight-id', Date.now().toString());
            
            // Add MutationObserver to watch for attribute or removal changes
            // This helps detect if the highlight is being removed
            if (!this.tempHighlight._observer) {
                const observer = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        if (mutation.type === 'childList' && mutation.removedNodes.length > 0) {
                            // Check if highlight was removed
                            for (let node of mutation.removedNodes) {
                                if (node === this.tempHighlight) {
                                    logger.warn('Temp highlight detected as removed via MutationObserver');
                                }
                            }
                        }
                    });
                });
                
                if (this.tempHighlight.parentNode) {
                    observer.observe(this.tempHighlight.parentNode, {
                        childList: true,
                        subtree: false
                    });
                    this.tempHighlight._observer = observer;
                }
            }
            
            // Force visibility by ensuring styles
            requestAnimationFrame(() => {
                if (this.tempHighlight && this.tempHighlight.parentNode) {
                    const computedStyle = window.getComputedStyle(this.tempHighlight);
                    if (computedStyle.backgroundColor === 'rgba(0, 0, 0, 0)' || 
                        computedStyle.display === 'none' ||
                        computedStyle.visibility === 'hidden') {
                        logger.warn('Temp highlight not visible, restoring styles');
                        this.tempHighlight.style.backgroundColor = '#ffeb3b';
                        this.tempHighlight.style.display = 'inline';
                        this.tempHighlight.style.visibility = 'visible';
                    }
                }
            });
        }
    }

    /**
     * Clear temporary highlight
     */
    clearTempHighlight() {
        if (this.tempHighlight && this.tempHighlight.parentNode) {
            const parent = this.tempHighlight.parentNode;
            parent.replaceChild(document.createTextNode(this.tempHighlight.textContent), this.tempHighlight);
            parent.normalize();
        }
        this.tempHighlight = null;
    }

    /**
     * Get all text nodes within a range
     * @param {Range} range 
     * @returns {Array<Node>} Array of text nodes
     */
    _getTextNodesInRange(range) {
        const textNodes = [];
        const walker = document.createTreeWalker(
            range.commonAncestorContainer,
            NodeFilter.SHOW_TEXT,
            {
                acceptNode: (node) => {
                    const range2 = range.cloneRange();
                    range2.setStartBefore(node);
                    range2.setEndAfter(node);
                    
                    // Check if node is fully or partially within range
                    if (range.compareBoundaryPoints(Range.START_TO_START, range2) <= 0 &&
                        range.compareBoundaryPoints(Range.END_TO_END, range2) >= 0) {
                        return NodeFilter.FILTER_ACCEPT;
                    }
                    return NodeFilter.FILTER_REJECT;
                }
            }
        );
        
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }
        
        return textNodes;
    }

    /**
     * Cleanup - remove all temporary highlights and reset state
     */
    cleanup() {
        this.clearTempHighlight();
        this.clearSelection();
        this.contentElement = null;
    }
}
