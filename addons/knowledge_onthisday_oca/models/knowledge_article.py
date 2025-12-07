# -*- coding: utf-8 -*-

from odoo import models, fields, api


class KnowledgeArticle(models.Model):
    """Knowledge Article Model
    
    Represents a knowledge article for internal documentation.
    Based on OCA knowledge module patterns, adapted for Odoo 19 Community.
    """
    _name = 'knowledge.article'
    _description = 'Knowledge Article'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(
        string='Title',
        required=True,
        tracking=True,
        help='Title of the knowledge article'
    )
    
    content = fields.Html(
        string='Content',
        help='HTML content of the article'
    )
    
    category_id = fields.Many2one(
        comodel_name='knowledge.article.category',
        string='Category',
        index=True,
        tracking=True,
        help='Category of the knowledge article',
        default=lambda self: self._get_default_category()
    )
    
    @api.model
    def _get_default_category(self):
        """Get default category (SOP)
        
        Returns False if category model is not available yet (during module installation).
        """
        try:
            # Check if category model exists and is available
            if 'knowledge.article.category' not in self.env:
                return False
            
            # Check if table exists by attempting a search
            category = self.env['knowledge.article.category'].search([('code', '=', 'sop')], limit=1)
            return category.id if category else False
        except (KeyError, AttributeError, Exception):
            # Model not available yet, return False
            return False
    
    # Remove legacy category field completely - it causes view errors
    # category = fields.Selection(...)  # REMOVED - use category_id instead
    
    parent_id = fields.Many2one(
        comodel_name='knowledge.article',
        string='Parent Article',
        ondelete='set null',
        help='Parent article in the hierarchical structure'
    )
    
    child_ids = fields.One2many(
        comodel_name='knowledge.article',
        inverse_name='parent_id',
        string='Child Articles',
        help='Child articles in the hierarchical structure'
    )
    
    responsible_id = fields.Many2one(
        comodel_name='res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
        help='User responsible for maintaining this article'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, it will allow you to hide the article without removing it.'
    )

    # Favorites: Many2many to track users who favorited this article
    favorite_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='knowledge_article_favorite_user_rel',
        column1='article_id',
        column2='user_id',
        string='Favorited By',
        help='Users who have favorited this article'
    )

    # Shared: Many2many to track users who can access this article
    shared_user_ids = fields.Many2many(
        comodel_name='res.users',
        relation='knowledge_article_shared_user_rel',
        column1='article_id',
        column2='user_id',
        string='Shared With',
        help='Users who have access to this shared article'
    )

    # Tags: Many2many to track tags/labels for this article
    tag_ids = fields.Many2many(
        comodel_name='knowledge.article.tag',
        relation='knowledge_article_tag_rel',
        column1='article_id',
        column2='tag_id',
        string='Tags',
        help='Tags/labels for categorizing and organizing this article'
    )

    # Share link token for public access
    share_token = fields.Char(
        string='Share Token',
        copy=False,
        index=True,
        help='Unique token for public sharing. If set, article can be accessed via share link.'
    )

    share_link = fields.Char(
        string='Share Link',
        compute='_compute_share_link',
        store=False,  # Explicitly set store=False for computed field
        help='Public URL for sharing this article'
    )

    @api.depends('share_token')
    def _compute_share_link(self):
        """Compute share link URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for article in self:
            if article.share_token:
                article.share_link = f"{base_url}/knowledge/article/{article.share_token}"
            else:
                article.share_link = False

    def generate_share_token(self):
        """Generate a unique share token for this article"""
        import random
        import string
        import hashlib
        import time
        
        # Generate a secure random token using multiple sources
        # Combine random string with timestamp hash for uniqueness
        alphabet = string.ascii_letters + string.digits
        random_part = ''.join(random.choice(alphabet) for _ in range(24))
        timestamp_part = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
        token = random_part + timestamp_part
        
        # Ensure uniqueness (check if token already exists)
        max_attempts = 10
        attempts = 0
        while self.env['knowledge.article'].search([('share_token', '=', token)], limit=1) and attempts < max_attempts:
            random_part = ''.join(random.choice(alphabet) for _ in range(24))
            timestamp_part = hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
            token = random_part + timestamp_part
            attempts += 1
        
        # If still not unique after max attempts, add article ID to ensure uniqueness
        if self.env['knowledge.article'].search([('share_token', '=', token)], limit=1):
            token = f"{token}{self.id}"
        
        self.share_token = token
        return token

    def action_generate_share_link(self):
        """Action to generate share link"""
        if not self.share_token:
            self.generate_share_token()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Share Link Created',
                'message': f'Share link has been generated. Token: {self.share_token}',
                'type': 'success',
                'sticky': False,
            }
        }

    # Trash/restore helpers
    def action_move_to_trash(self):
        """Soft delete: mark inactive so it appears in Trash."""
        self.write({'active': False})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Moved to Trash',
                'message': f'Article \"{self.name}\" was moved to Trash. You can restore it later.',
                'type': 'warning',
                'sticky': False,
            }
        }

    def action_restore_from_trash(self):
        """Restore from trash (reactivate)."""
        self.write({'active': True})
        # After restore, send user back to the normal form of this record
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'knowledge.article',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
            'context': {},
        }

    def action_delete_permanently(self):
        """Permanently delete article (use carefully)."""
        name = self.name
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Article Deleted',
                'message': f'Article \"{name}\" was permanently deleted.',
                'type': 'danger',
                'sticky': False,
            }
        }
    
    # Comments relationship
    comment_ids = fields.One2many(
        'knowledge.article.comment',
        'article_id',
        string='Comments',
        help='Comments on this article'
    )
    
    comment_count = fields.Integer(
        string='Comment Count',
        compute='_compute_comment_count',
        store=False,
        help='Number of comments on this article'
    )
    
    unresolved_comment_count = fields.Integer(
        string='Unresolved Comments',
        compute='_compute_comment_count',
        store=False,
        help='Number of unresolved comments on this article'
    )
    
    @api.depends('comment_ids', 'comment_ids.resolved')
    def _compute_comment_count(self):
        """Compute comment counts"""
        for article in self:
            article.comment_count = len(article.comment_ids)
            article.unresolved_comment_count = len(article.comment_ids.filtered(lambda c: not c.resolved))
