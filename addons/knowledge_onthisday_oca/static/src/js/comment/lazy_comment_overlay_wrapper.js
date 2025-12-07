/** @odoo-module **/

import { Component } from "@odoo/owl";
import { CommentOverlay } from "./comment_overlay";

/**
 * Comment Overlay Wrapper
 * 
 * Simple wrapper that just passes through to CommentOverlay.
 * This allows us to easily swap implementations if needed.
 */
export class LazyCommentOverlayWrapper extends Component {
    static template = "knowledge_onthisday_oca.LazyCommentOverlayWrapper";
    static components = { CommentOverlay };
    static props = ["*"]; // Accept all props
    
    getProps() {
        // Pass all props to CommentOverlay
        return {
            articleId: this.props.articleId,
            contentElement: this.props.contentElement,
            selectionData: this.props.selectionData,
            triggerCreation: this.props.triggerCreation,
            onCreateCommentFromSelection: this.props.onCreateCommentFromSelection,
        };
    }
}

