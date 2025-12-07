/**
 * Test script to manually test highlight functionality
 * Run this in browser console after selecting text
 */

window.testHighlight = function() {
    const highlight = document.querySelector('.o_knowledge_comment_temp_highlight');
    
    if (!highlight) {
        console.error('No highlight found!');
        return;
    }
    
    console.log('=== Highlight Debug Info ===');
    console.log('Element:', highlight);
    console.log('Text:', highlight.textContent);
    console.log('In DOM:', highlight.parentNode !== null);
    console.log('Parent:', highlight.parentNode);
    
    const computed = window.getComputedStyle(highlight);
    console.log('=== Computed Styles ===');
    console.log('backgroundColor:', computed.backgroundColor);
    console.log('background:', computed.background);
    console.log('display:', computed.display);
    console.log('visibility:', computed.visibility);
    console.log('opacity:', computed.opacity);
    console.log('width:', computed.width);
    console.log('height:', computed.height);
    
    const rect = highlight.getBoundingClientRect();
    console.log('=== Bounding Rect ===');
    console.log('x:', rect.x, 'y:', rect.y);
    console.log('width:', rect.width, 'height:', rect.height);
    console.log('top:', rect.top, 'right:', rect.right, 'bottom:', rect.bottom, 'left:', rect.left);
    
    console.log('=== Inline Styles ===');
    console.log('style attribute:', highlight.getAttribute('style'));
    console.log('classList:', highlight.className);
    
    // Try to force highlight visibility
    console.log('=== Forcing Highlight Visibility ===');
    highlight.style.setProperty('background-color', '#ffeb3b', 'important');
    highlight.style.setProperty('background', '#ffeb3b', 'important');
    highlight.style.setProperty('display', 'inline-block', 'important');
    highlight.style.setProperty('visibility', 'visible', 'important');
    highlight.style.setProperty('opacity', '1', 'important');
    highlight.style.setProperty('position', 'relative', 'important');
    highlight.style.setProperty('z-index', '9999', 'important');
    
    // Check again
    const newComputed = window.getComputedStyle(highlight);
    console.log('New backgroundColor:', newComputed.backgroundColor);
    console.log('New display:', newComputed.display);
    
    return highlight;
};

console.log('Test highlight function loaded. Run testHighlight() in console.');

