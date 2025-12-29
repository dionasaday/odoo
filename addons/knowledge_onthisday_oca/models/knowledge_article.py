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
    
    def get_pdf_attachment(self):
        """Get the first PDF attachment associated with this article
        
        Returns:
            dict: Attachment data with id, name, mimetype, and url, or empty dict if no PDF found
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        attachment_model = self.env['ir.attachment']
        has_datas_fname = 'datas_fname' in attachment_model._fields
        has_access_token = 'access_token' in attachment_model._fields

        def _or_domain(conditions):
            if not conditions:
                return []
            if len(conditions) == 1:
                return conditions
            return ['|'] * (len(conditions) - 1) + conditions

        def _is_pdf_attachment(attachment):
            if not attachment:
                return False
            mimetype = (attachment.mimetype or '').lower()
            name = (attachment.name or '').lower()
            datas_fname = (attachment.datas_fname or '').lower() if has_datas_fname else ''
            return ('pdf' in mimetype) or name.endswith('.pdf') or datas_fname.endswith('.pdf')
        
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        _logger.info(f"Getting PDF attachment for article {self.id} ({self.name})")
        
        # First, check message_main_attachment_id if available (Odoo 13+)
        # This is the main attachment shown in chatter
        if hasattr(self, 'message_main_attachment_id') and self.message_main_attachment_id:
            main_attachment = self.message_main_attachment_id
            _logger.info(f"Found message_main_attachment_id: {main_attachment.id}, mimetype: {main_attachment.mimetype}")
            if _is_pdf_attachment(main_attachment):
                result = {
                    'id': main_attachment.id,
                    'name': main_attachment.name,
                    'mimetype': main_attachment.mimetype or 'application/pdf',
                    'url': f"{base_url}/web/content/{main_attachment.id}?download=true",
                    'access_url': f"{base_url}/web/content/{main_attachment.id}",
                }
                _logger.info(f"Returning PDF attachment from message_main_attachment_id: {result}")
                return result
        
        # Search for PDF attachments linked to this article (from messages/chatter)
        pdf_filters = [
            ('mimetype', 'ilike', 'pdf'),
            ('name', 'ilike', '%.pdf'),
        ]
        if has_datas_fname:
            pdf_filters.append(('datas_fname', 'ilike', '%.pdf'))

        pdf_attachments = attachment_model.search([
            ('res_model', '=', 'knowledge.article'),
            ('res_id', '=', self.id),
        ] + _or_domain(pdf_filters), limit=1, order='create_date desc')
        
        _logger.info(f"Found {len(pdf_attachments)} PDF attachments with res_model='knowledge.article'")
        
        if pdf_attachments:
            attachment = pdf_attachments[0]
            result = {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype or 'application/pdf',
                'url': f"{base_url}/web/content/{attachment.id}?download=true",
                'access_url': f"{base_url}/web/content/{attachment.id}",
            }
            _logger.info(f"Returning PDF attachment: {result}")
            return result
        
        # Also search in message attachments (attachments posted in chatter messages)
        if hasattr(self, 'message_ids'):
            message_ids = self.message_ids.ids
            _logger.info(f"Searching in {len(message_ids)} messages for PDF attachments")
            if message_ids:
                message_attachments = attachment_model.search([
                    ('res_model', '=', 'mail.message'),
                    ('res_id', 'in', message_ids),
                ] + _or_domain(pdf_filters), limit=1, order='create_date desc')
                
                _logger.info(f"Found {len(message_attachments)} PDF attachments in messages")
                
                if message_attachments:
                    attachment = message_attachments[0]
                    result = {
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype or 'application/pdf',
                        'url': f"{base_url}/web/content/{attachment.id}?download=true",
                        'access_url': f"{base_url}/web/content/{attachment.id}",
                    }
                    _logger.info(f"Returning PDF attachment from messages: {result}")
                    return result
        
        # Search all attachments linked to this article (any mimetype, then filter)
        # Try with and without res_model to catch all possible attachment locations
        all_attachments = attachment_model.search([
            ('res_id', '=', self.id),
            '|',
            ('res_model', '=', 'knowledge.article'),
            ('res_model', '=', False),  # Some attachments may have res_model=False
        ], limit=50, order='create_date desc')
        
        _logger.info(f"Found {len(all_attachments)} total attachments for article {self.id} (including res_model=False)")
        for att in all_attachments[:10]:  # Log first 10 only
            _logger.info(f"  - Attachment {att.id}: {att.name} (mimetype: {att.mimetype}, res_model: {att.res_model})")
        
        # Check if any attachment is PDF
        pdf_from_all = all_attachments.filtered(lambda a: _is_pdf_attachment(a))
        if pdf_from_all:
            attachment = pdf_from_all[0]
            result = {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype or 'application/pdf',
                'url': f"{base_url}/web/content/{attachment.id}?download=true",
                'access_url': f"{base_url}/web/content/{attachment.id}",
            }
            _logger.info(f"Returning PDF attachment from filtered attachments: {result}")
            return result
        
        # Also try searching by name pattern (PDF files often have .pdf extension)
        pdf_name_filters = [
            ('name', 'ilike', '%.pdf'),
        ]
        if has_datas_fname:
            pdf_name_filters.append(('datas_fname', 'ilike', '%.pdf'))

        pdf_by_name = attachment_model.search([
            ('res_id', '=', self.id),
            ('res_model', 'in', ['knowledge.article', False]),
        ] + _or_domain(pdf_name_filters), limit=10, order='create_date desc')
        
        if pdf_by_name:
            attachment = pdf_by_name[0]
            if _is_pdf_attachment(attachment):
                result = {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype or 'application/pdf',
                    'url': f"{base_url}/web/content/{attachment.id}?download=true",
                    'access_url': f"{base_url}/web/content/{attachment.id}",
                }
                _logger.info(f"Returning PDF attachment found by name pattern: {result}")
                return result
        
        # Last resort: Check if content field contains PDF attachment references
        if self.content:
            import re
            import json
            import html as html_lib
            try:
                from html.parser import HTMLParser

                class _AttachmentParser(HTMLParser):
                    def __init__(self):
                        super().__init__()
                        self.matches = []
                        self.embedded_files = []
                        self._current_anchor = None

                    def handle_starttag(self, tag, attrs):
                        attr = dict(attrs)
                        embedded_props = attr.get('data-embedded-props')
                        if attr.get('data-embedded') == 'file' and embedded_props:
                            self.embedded_files.append({
                                'props': embedded_props,
                                'mimetype': attr.get('data-mimetype') or '',
                                'title': attr.get('title') or '',
                            })
                        attachment_id = (
                            attr.get('data-oe-id')
                            or attr.get('data-oe-attachment-id')
                            or attr.get('data-attachment-id')
                        )
                        if not attachment_id:
                            return
                        candidate = {
                            'id': attachment_id,
                            'file_hint': attr.get('data-oe-file') or attr.get('data-file') or attr.get('title') or '',
                            'href': attr.get('href') or '',
                            'text': '',
                        }
                        self.matches.append(candidate)
                        if tag == 'a':
                            self._current_anchor = candidate

                    def handle_data(self, data):
                        if self._current_anchor is not None:
                            self._current_anchor['text'] += data

                    def handle_endtag(self, tag):
                        if tag == 'a':
                            self._current_anchor = None

                parser = _AttachmentParser()
                parser.feed(self.content)
                for embedded in parser.embedded_files:
                    props_raw = embedded.get('props') or ''
                    try:
                        props = json.loads(html_lib.unescape(props_raw))
                    except (ValueError, json.JSONDecodeError) as e:
                        _logger.warn(f"Error parsing embedded file props JSON: {e}")
                        continue
                    file_data = props.get('fileData') or {}
                    filename = (file_data.get('filename') or embedded.get('title') or '').strip()
                    mimetype_hint = (file_data.get('mimetype') or embedded.get('mimetype') or '').lower()
                    is_pdf_hint = filename.lower().endswith('.pdf') or ('pdf' in mimetype_hint)
                    if not is_pdf_hint:
                        continue
                    attachment_id = (
                        file_data.get('id')
                        or file_data.get('attachment_id')
                        or file_data.get('attachmentId')
                    )
                    url_hint = file_data.get('url') or ''
                    access_token = file_data.get('access_token') or file_data.get('accessToken')
                    if attachment_id:
                        try:
                            attachment_id = int(attachment_id)
                        except (ValueError, TypeError):
                            attachment_id = None
                    if not attachment_id and url_hint:
                        match = re.search(r'/web/content/(\d+)', url_hint)
                        if match:
                            attachment_id = int(match.group(1))
                    if attachment_id:
                        attachment = attachment_model.browse(attachment_id)
                        if attachment.exists():
                            token = attachment.access_token if has_access_token else None
                            access_suffix = f"?access_token={token}" if token else ""
                            download_suffix = f"?access_token={token}&download=true" if token else "?download=true"
                            result = {
                                'id': attachment.id,
                                'name': attachment.name or filename or f"Attachment {attachment.id}",
                                'mimetype': attachment.mimetype or 'application/pdf',
                                'url': f"{base_url}/web/content/{attachment.id}{download_suffix}",
                                'access_url': f"{base_url}/web/content/{attachment.id}{access_suffix}",
                            }
                            _logger.info(f"Returning PDF attachment found from embedded file ID: {result}")
                            return result
                    if access_token and has_access_token:
                        attachment = attachment_model.search([
                            ('access_token', '=', access_token),
                        ], limit=1)
                        if attachment and (is_pdf_hint or _is_pdf_attachment(attachment)):
                            token = attachment.access_token or access_token
                            access_suffix = f"?access_token={token}" if token else ""
                            download_suffix = f"?access_token={token}&download=true" if token else "?download=true"
                            result = {
                                'id': attachment.id,
                                'name': attachment.name or filename or f"Attachment {attachment.id}",
                                'mimetype': attachment.mimetype or 'application/pdf',
                                'url': f"{base_url}/web/content/{attachment.id}{download_suffix}",
                                'access_url': f"{base_url}/web/content/{attachment.id}{access_suffix}",
                            }
                            _logger.info(f"Returning PDF attachment found from embedded file access token: {result}")
                            return result
                for candidate in parser.matches:
                    try:
                        attachment_id = int(candidate['id'])
                    except (ValueError, TypeError):
                        continue
                    pdf_hint = f"{candidate['file_hint']} {candidate['href']} {candidate['text']}".lower()
                    if '.pdf' not in pdf_hint:
                        continue
                    attachment = attachment_model.browse(attachment_id)
                    if attachment.exists():
                        name_hint = candidate['file_hint'].strip() or candidate['text'].strip()
                        result = {
                            'id': attachment.id,
                            'name': attachment.name or name_hint or f"Attachment {attachment.id}",
                            'mimetype': attachment.mimetype or 'application/pdf',
                            'url': f"{base_url}/web/content/{attachment.id}?download=true",
                            'access_url': f"{base_url}/web/content/{attachment.id}",
                        }
                        _logger.info(f"Returning PDF attachment found in HTML metadata: {result}")
                        return result
            except Exception as e:
                _logger.warn(f"Error parsing HTML content for attachment metadata: {e}")
            # Look for attachment URLs in HTML content
            # Pattern: /web/content/\d+ or similar attachment URLs
            pdf_url_patterns = [
                r'/web/content/(\d+)[^"\'>\s]*\.pdf',
                r'/web/content/(\d+)',
                r'data-oe-id=["\'](\d+)["\']',
                r'data-oe-attachment-id=["\'](\d+)["\']',
                r'data-attachment-id=["\'](\d+)["\']',
            ]
            checked_ids = set()
            for pattern in pdf_url_patterns:
                matches = re.findall(pattern, self.content, re.IGNORECASE)
                if matches:
                    for match in matches:
                        try:
                            attachment_id = int(match)
                            if attachment_id in checked_ids:
                                continue
                            checked_ids.add(attachment_id)
                            attachment = self.env['ir.attachment'].browse(attachment_id)
                            if attachment.exists() and _is_pdf_attachment(attachment):
                                result = {
                                    'id': attachment.id,
                                    'name': attachment.name,
                                    'mimetype': attachment.mimetype or 'application/pdf',
                                    'url': f"{base_url}/web/content/{attachment.id}?download=true",
                                    'access_url': f"{base_url}/web/content/{attachment.id}",
                                }
                                _logger.info(f"Returning PDF attachment found in HTML content: {result}")
                                return result
                        except (ValueError, TypeError) as e:
                            _logger.warn(f"Error parsing attachment ID from content: {e}")
                            continue
        
        _logger.info(f"No PDF attachment found for article {self.id}")
        _logger.info(f"Total attachments checked: {len(all_attachments)}")
        # Return empty dict instead of False for JSON serialization
        return {}
