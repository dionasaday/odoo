# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError, AccessError
from odoo.tools.translate import _
import re
import logging

_logger = logging.getLogger(__name__)


class KnowledgeArticleComment(models.Model):
    """Knowledge Article Comment Model
    
    Stores comments on specific text selections within knowledge articles.
    Similar to Google Docs comment system.
    """
    _name = 'knowledge.article.comment'
    _description = 'Knowledge Article Comment'
    _inherit = ['mail.thread']
    _order = 'create_date asc'
    _rec_name = 'selected_text'

    article_id = fields.Many2one(
        'knowledge.article',
        string='Article',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='The article this comment belongs to'
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
        help='Character offset from start of content (plain text)'
    )
    
    end_offset = fields.Integer(
        string='End Offset',
        required=True,
        help='Character offset from end of selection (plain text)'
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
        sanitize_attributes=True,  # Security: Enable attribute sanitization to prevent XSS
        sanitize_form=True,         # Security: Sanitize form elements
        sanitize_style=True,        # Enforce inline style sanitization for production safety
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
        tracking=True,
        help='User who created this comment'
    )
    
    # Highlight Color (for UI)
    highlight_color = fields.Char(
        string='Highlight Color',
        default='#ffeb3b',  # Yellow (Google Docs default)
        help='Color used to highlight selected text'
    )
    
    # Computed fields
    is_reply = fields.Boolean(
        string='Is Reply',
        compute='_compute_is_reply',
        store=False,
        help='Whether this comment is a reply to another comment'
    )
    
    reply_count = fields.Integer(
        string='Reply Count',
        compute='_compute_reply_count',
        store=False,
        help='Number of replies to this comment'
    )
    
    @api.depends('parent_id')
    def _compute_is_reply(self):
        """Compute whether this comment is a reply"""
        for record in self:
            record.is_reply = bool(record.parent_id)
    
    @api.depends('child_ids')
    def _compute_reply_count(self):
        """Compute number of replies"""
        for record in self:
            record.reply_count = len(record.child_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to handle mentions and notifications
        
        In Odoo 19, create() receives vals_list (list of dicts) instead of vals (single dict)
        """
        # Process each vals dict in the list
        comments = []
        for vals in vals_list:
            _logger.info(f"Creating comment with vals: article_id={vals.get('article_id')}, body_length={len(vals.get('body', ''))}, selected_text={vals.get('selected_text', '')[:50]}")
            
            # Validate required fields before creating
            article_id = vals.get('article_id')
            if not article_id:
                _logger.error("Validation failed: Article ID is required")
                raise ValidationError(_("Article ID is required"))
            
            # Security: Validate article exists and user has access
            article = self.env['knowledge.article'].browse(article_id)
            if not article.exists():
                _logger.error(f"Validation failed: Article {article_id} does not exist")
                raise ValidationError(_("Article not found"))
            
            # Security: Check if user has read access to article (Odoo ACL will handle this automatically,
            # but we add explicit check for better error messages and security)
            try:
                # Try to read article to verify access
                article.check_access_rights('read', raise_exception=True)
                article.check_access_rule('read')
            except AccessError:
                _logger.warning(f"Access denied: User {self.env.user.id} cannot access article {article_id}")
                raise ValidationError(_("You do not have permission to comment on this article"))
            
            if not vals.get('body'):
                _logger.error("Validation failed: Comment body is required")
                raise ValidationError(_("Comment body is required"))
            
            if not vals.get('selected_text'):
                _logger.error("Validation failed: Selected text is required")
                raise ValidationError(_("Selected text is required"))
            
            # Validate offsets
            start_offset = vals.get('start_offset', 0)
            end_offset = vals.get('end_offset', 0)
            selected_text = vals.get('selected_text', '').strip()
            
            _logger.info(f"Offset validation: start={start_offset}, end={end_offset}, selected_text_length={len(selected_text)}")
            
            if start_offset < 0:
                _logger.error(f"Validation failed: Start offset {start_offset} cannot be negative")
                raise ValidationError(_("Start offset cannot be negative"))
            
            # If offsets are equal but we have selected text, calculate proper end offset
            if end_offset == start_offset and selected_text:
                end_offset = start_offset + len(selected_text)
                vals['end_offset'] = end_offset
                _logger.info(f"Adjusted end_offset from {start_offset} to {end_offset} based on selected_text length")
            
            if end_offset < start_offset:
                _logger.error(f"Validation failed: End offset {end_offset} must be >= start offset {start_offset}")
                raise ValidationError(_("End offset must be greater than or equal to start offset"))
            
            # Ensure author_id is set (if not provided, use current user)
            if 'author_id' not in vals:
                vals['author_id'] = self.env.user.id
                _logger.info(f"Setting author_id to current user: {self.env.user.id}")
        
        # Call super().create() with the processed vals_list
        try:
            _logger.info(f"Calling super().create() with {len(vals_list)} comment(s)")
            comments = super().create(vals_list)
            _logger.info(f"Comment(s) created successfully: {[c.id for c in comments]}")
            
            # Process each created comment
            for comment, vals in zip(comments, vals_list):
                # Extract mentions from body
                if vals.get('body'):
                    mentioned_users = self._extract_mentions(vals['body'])
                    if mentioned_users:
                        comment.mentioned_user_ids = [(6, 0, mentioned_users)]
                        _logger.info(f"Extracted {len(mentioned_users)} mentions for comment {comment.id}")
                        # Notify mentioned users
                        comment._notify_mentioned_users(mentioned_users)
                
                # Send notification to article owner/responsible
                comment._notify_article_owner()
            
            return comments
            
        except ValidationError:
            # Re-raise ValidationError as-is
            raise
        except Exception as e:
            _logger.error(f"Unexpected error creating comment: {e}", exc_info=True)
            # Wrap other errors in ValidationError with user-friendly message
            raise ValidationError(_("Failed to create comment: %s") % str(e))
    
    def write(self, vals):
        """Override write to handle resolve/unresolve and access control"""
        # Security: Check if user has write access (Odoo ACL will handle this automatically,
        # but we add explicit check for better security)
        for record in self:
            is_privileged = (
                self.env.user.has_group('base.group_system') or
                self.env.user.has_group('knowledge_onthisday_oca.group_knowledge_manager')
            )
            if not is_privileged and record.author_id.id != self.env.user.id:
                _logger.warning(f"Access denied: User {self.env.user.id} cannot modify comment {record.id} (not author)")
                raise AccessError(_("You can only edit your own comments"))

            # Check if user is trying to modify comment content (body) or other sensitive fields
            # Only allow author or admin to modify comment content
            if 'body' in vals or 'selected_text' in vals or 'start_offset' in vals or 'end_offset' in vals:
                # Only author or admin can modify comment content
                if record.author_id.id != self.env.user.id and not is_privileged:
                    _logger.warning(f"Access denied: User {self.env.user.id} cannot modify comment {record.id} (not author)")
                    raise AccessError(_("You can only edit your own comments"))
            
            # Check article access
            if record.article_id:
                try:
                    record.article_id.check_access_rights('read', raise_exception=True)
                    record.article_id.check_access_rule('read')
                except AccessError:
                    _logger.warning(f"Access denied: User {self.env.user.id} cannot access article {record.article_id.id}")
                    raise AccessError(_("You do not have permission to modify comments on this article"))
        
        if 'resolved' in vals:
            if vals['resolved']:
                # Resolving
                vals['resolved_by'] = self.env.user.id
                vals['resolved_date'] = fields.Datetime.now()
            else:
                # Unresolving
                vals['resolved_by'] = False
                vals['resolved_date'] = False
        
        result = super().write(vals)
        
        # Handle new mentions if body changed
        if 'body' in vals:
            mentioned_users = self._extract_mentions(vals['body'])
            if mentioned_users:
                self.mentioned_user_ids = [(6, 0, mentioned_users)]
                self._notify_mentioned_users(mentioned_users)
        
        return result

    def unlink(self):
        """Only allow author or managers to delete comments."""
        for record in self:
            is_privileged = (
                self.env.user.has_group('base.group_system') or
                self.env.user.has_group('knowledge_onthisday_oca.group_knowledge_manager')
            )
            if not is_privileged and record.author_id.id != self.env.user.id:
                _logger.warning(f"Access denied: User {self.env.user.id} cannot delete comment {record.id} (not author)")
                raise AccessError(_("You can only delete your own comments"))
        return super().unlink()
    
    def _extract_mentions(self, html_body):
        """Extract @mentions from HTML body
        
        Returns list of user IDs mentioned in the comment.
        Pattern: @username or @user_name
        """
        mentioned_user_ids = []
        
        # Extract text from HTML (simple approach)
        # Remove HTML tags
        text_only = re.sub(r'<[^>]+>', '', html_body)
        
        # Find @mentions (pattern: @username)
        mentions = re.findall(r'@(\w+)', text_only)
        
        if not mentions:
            return mentioned_user_ids
        
        # Find users by login or name
        User = self.env['res.users']
        for mention in mentions:
            # Try to find by login first
            user = User.search([
                '|',
                ('login', 'ilike', mention),
                ('name', 'ilike', mention)
            ], limit=1)
            
            if user and user.id not in mentioned_user_ids:
                mentioned_user_ids.append(user.id)
        
        return mentioned_user_ids
    
    def _notify_mentioned_users(self, user_ids):
        """Notify mentioned users about the comment"""
        if not user_ids:
            return
        
        # Create activity/notification
        # This can be customized based on requirements
        _logger.info(f"Notifying users {user_ids} about comment {self.id}")
        
        # TODO: Implement actual notification mechanism
        # Could use mail.message, activity, or bus notification
    
    def _notify_article_owner(self):
        """Notify article owner/responsible about new comment"""
        if not self.article_id.responsible_id:
            return
        
        # Skip if commenter is the owner
        if self.author_id.id == self.article_id.responsible_id.id:
            return
        
        # Create notification
        _logger.info(f"Notifying article owner {self.article_id.responsible_id.name} about comment {self.id}")
        
        # TODO: Implement actual notification mechanism
    
    def action_resolve(self):
        """Action to resolve this comment"""
        self.write({'resolved': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Comment Resolved',
                'message': 'Comment has been marked as resolved.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_unresolve(self):
        """Action to unresolve this comment"""
        self.write({'resolved': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Comment Unresolved',
                'message': 'Comment has been marked as unresolved.',
                'type': 'info',
                'sticky': False,
            }
        }
    
    @api.constrains('start_offset', 'end_offset', 'selected_text')
    def _check_offsets(self):
        """Validate that offsets are valid"""
        for record in self:
            if record.start_offset < 0:
                raise ValidationError("Start offset cannot be negative")
            
            # Auto-adjust if offsets are equal but we have selected text
            if record.end_offset == record.start_offset and record.selected_text:
                record.end_offset = record.start_offset + len(record.selected_text.strip())
                _logger.info(f"Auto-adjusted end_offset for comment {record.id}: {record.start_offset} -> {record.end_offset}")
            
            if record.end_offset < record.start_offset:
                raise ValidationError("End offset must be greater than or equal to start offset")
