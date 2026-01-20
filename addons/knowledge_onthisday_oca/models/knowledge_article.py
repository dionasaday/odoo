# -*- coding: utf-8 -*-

import difflib
import html as html_lib
import re

from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError
from odoo.tools import html2plaintext


class KnowledgeArticle(models.Model):
    """Knowledge Article Model
    
    Represents a knowledge article for internal documentation.
    Based on OCA knowledge module patterns, adapted for Odoo 19 Community.
    """
    _name = 'knowledge.article'
    _description = 'Knowledge Article'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'parent_id, sequence, name'
    _sql_constraints = [
        ('knowledge_article_share_token_unique', 'unique(share_token)', 'Share token must be unique.'),
    ]

    ICON_CHOICES = [
        ('📝', '📝 Note'),
        ('📋', '📋 Checklist'),
        ('📄', '📄 Document'),
        ('📚', '📚 Library'),
        ('📦', '📦 Product'),
        ('⚙️', '⚙️ Settings'),
        ('🛠️', '🛠️ Tools'),
        ('🔧', '🔧 Repair'),
        ('✅', '✅ Done'),
        ('❓', '❓ FAQ'),
        ('☕', '☕ Coffee'),
        ('🧹', '🧹 Cleaning'),
        ('🧰', '🧰 Equipment'),
        ('📊', '📊 Report'),
        ('📅', '📅 Schedule'),
        ('📌', '📌 Pin'),
        ('📁', '📁 Folder'),
        ('custom', 'Custom'),
    ]

    name = fields.Char(
        string='Title',
        required=True,
        tracking=True,
        help='Title of the knowledge article'
    )

    icon = fields.Char(
        string='Icon',
        help='Emoji or icon character for this article'
    )

    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Ordering for article display'
    )

    icon_choice = fields.Selection(
        selection=ICON_CHOICES,
        string='Icon Picker',
        compute='_compute_icon_choice',
        inverse='_inverse_icon_choice',
        store=False
    )
    
    content = fields.Html(
        string='Content',
        help='HTML content of the article'
    )

    revision_ids = fields.One2many(
        comodel_name='knowledge.article.revision',
        inverse_name='article_id',
        string='Revisions',
        help='Revision history for this article'
    )

    revision_count = fields.Integer(
        string='Revision Count',
        compute='_compute_revision_count',
        store=False
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

    @api.onchange('category_id')
    def _onchange_category_id(self):
        for article in self:
            if article.category_id and article.category_id.default_share_permission:
                article.default_share_permission = article.category_id.default_share_permission
            if article.category_id and not article.icon:
                article.icon = article.category_id.icon or '📝'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('default_share_permission') and vals.get('category_id'):
                category = self.env['knowledge.article.category'].browse(vals['category_id'])
                if category and category.default_share_permission:
                    vals['default_share_permission'] = category.default_share_permission
            if not vals.get('icon') and vals.get('category_id'):
                category = self.env['knowledge.article.category'].browse(vals['category_id'])
                if category and category.icon:
                    vals['icon'] = category.icon
        return super().create(vals_list)

    @api.depends('icon', 'category_id')
    def _compute_icon_choice(self):
        icon_values = {choice[0] for choice in self.ICON_CHOICES}
        for article in self:
            icon_value = article.icon or (article.category_id.icon if article.category_id else None)
            if icon_value in icon_values:
                article.icon_choice = icon_value
            else:
                article.icon_choice = 'custom'

    def _inverse_icon_choice(self):
        for article in self:
            if article.icon_choice and article.icon_choice != 'custom':
                article.icon = article.icon_choice
    
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

    share_member_ids = fields.One2many(
        comodel_name='knowledge.article.member',
        inverse_name='article_id',
        string='Share Members',
        help='Users with explicit access rights for this article'
    )

    share_public = fields.Boolean(
        string='Article Published',
        default=False,
        tracking=True,
        help='If enabled, anyone with the share link can view this article'
    )

    default_share_permission = fields.Selection(
        selection=[('read', 'Can read'), ('edit', 'Can edit')],
        string='Default Access Rights',
        default='read',
        tracking=True,
        help='Default access rights for newly invited users'
    )

    last_change_summary = fields.Text(
        string='Last Change Summary',
        help='Summary sentence for the latest content update.'
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

    @api.depends('revision_ids')
    def _compute_revision_count(self):
        for article in self:
            article.revision_count = self.env['knowledge.article.revision'].search_count([
                ('article_id', '=', article.id),
            ])

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
        import secrets
        
        token = secrets.token_urlsafe(32)
        
        # Ensure uniqueness (check if token already exists)
        max_attempts = 10
        attempts = 0
        while self.env['knowledge.article'].search([('share_token', '=', token)], limit=1) and attempts < max_attempts:
            token = secrets.token_urlsafe(32)
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
        if not self.share_public:
            self.share_public = True
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

    def action_open_article_view(self):
        """Open the article in the document (view) mode."""
        self.ensure_one()
        return {
            'type': 'ir.actions.client',
            'tag': 'knowledge_document_view',
            'name': _('Knowledge Base'),
            'context': {
                'active_id': self.id,
                'knowledge_article_id': self.id,
            },
            'params': {
                'article_id': self.id,
            },
        }

    def _can_edit_article(self, user=None):
        user = user or self.env.user
        if not user:
            return False
        if user.has_group('base.group_system') or user.has_group('knowledge_onthisday_oca.group_knowledge_manager'):
            return True
        for article in self:
            if article.responsible_id.id == user.id:
                return True
            if article.share_member_ids.filtered(lambda m: m.user_id.id == user.id and m.permission == 'edit'):
                return True
        return False

    def _can_read_article(self, user=None):
        """Check if user has read access to this article
        
        Returns True if:
        - User is system/admin/manager
        - Internal users can read all active articles
        - User is the responsible (owner)
        - User is a share member with read or edit permission
        """
        user = user or self.env.user
        if not user:
            return False
        if user.has_group('base.group_system') or user.has_group('knowledge_onthisday_oca.group_knowledge_manager'):
            return True
        if user.has_group('base.group_user'):
            for article in self:
                if article.active:
                    return True
            return False
        for article in self:
            # Owner always has access
            if article.responsible_id.id == user.id:
                return True
            # Shared users (record rule uses shared_user_ids)
            if article.shared_user_ids.filtered(lambda u: u.id == user.id):
                return True
            # Check if user is a share member with read or edit permission
            if article.share_member_ids.filtered(lambda m: m.user_id.id == user.id and m.permission in ('read', 'edit')):
                return True
        return False

    def _normalize_plain_text(self, html_content):
        text = html2plaintext(html_content or "")
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _split_sentences(self, text):
        if not text:
            return []
        parts = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [part.strip() for part in parts if part and part.strip()]

    def _truncate_text(self, text, max_len=160):
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return f"{text[:max_len].rstrip()}..."

    def _build_change_summary(self, old_html, new_html):
        old_text = self._normalize_plain_text(old_html)
        new_text = self._normalize_plain_text(new_html)
        if not new_text:
            return ""
        if not old_text:
            return self._truncate_text(new_text)

        old_sentences = self._split_sentences(old_text)
        new_sentences = self._split_sentences(new_text)
        if new_sentences:
            diff = difflib.ndiff(old_sentences, new_sentences)
            for item in diff:
                if item.startswith('+ '):
                    return self._truncate_text(item[2:])

        if old_text != new_text:
            matcher = difflib.SequenceMatcher(None, old_text, new_text)
            for tag, _i1, _i2, j1, j2 in matcher.get_opcodes():
                if tag in ('replace', 'insert'):
                    snippet = new_text[j1:j2].strip()
                    if snippet:
                        return self._truncate_text(snippet)
            return self._truncate_text(new_text)

        return ""

    def _highlight_sentence_diff(self, old_sentence, new_sentence, max_tokens=40):
        old_tokens = [t for t in (old_sentence or "").split() if t]
        new_tokens = [t for t in (new_sentence or "").split() if t]
        if not old_tokens and not new_tokens:
            return "", ""

        base_matcher = difflib.SequenceMatcher(None, old_tokens, new_tokens)
        diff_ops = [op for op in base_matcher.get_opcodes() if op[0] != 'equal']
        if diff_ops:
            _, i1, i2, j1, j2 = diff_ops[0]
            old_start = max(0, i1 - 6)
            old_end = min(len(old_tokens), i2 + 6)
            new_start = max(0, j1 - 6)
            new_end = min(len(new_tokens), j2 + 6)
        else:
            old_start, old_end = 0, min(len(old_tokens), max_tokens)
            new_start, new_end = 0, min(len(new_tokens), max_tokens)

        old_slice = old_tokens[old_start:old_end]
        new_slice = new_tokens[new_start:new_end]
        matcher = difflib.SequenceMatcher(None, old_slice, new_slice)

        def _escape_tokens(tokens):
            return [html_lib.escape(token, quote=True) for token in tokens]

        escaped_old = _escape_tokens(old_slice)
        escaped_new = _escape_tokens(new_slice)

        def _build_highlight(side):
            parts = []
            for tag, i1, i2, j1, j2 in matcher.get_opcodes():
                if tag == 'equal':
                    tokens = escaped_old[i1:i2] if side == 'old' else escaped_new[j1:j2]
                    parts.append(" ".join(tokens))
                elif tag in ('delete', 'replace') and side == 'old':
                    tokens = " ".join(escaped_old[i1:i2])
                    if tokens:
                        parts.append(f"<mark class=\"o_knowledge_change_old\">{tokens}</mark>")
                elif tag in ('insert', 'replace') and side == 'new':
                    tokens = " ".join(escaped_new[j1:j2])
                    if tokens:
                        parts.append(f"<mark class=\"o_knowledge_change_new\">{tokens}</mark>")
            return " ".join([p for p in parts if p])

        old_text = _build_highlight('old')
        new_text = _build_highlight('new')

        old_prefix = "..." if old_start > 0 else ""
        old_suffix = "..." if old_end < len(old_tokens) else ""
        new_prefix = "..." if new_start > 0 else ""
        new_suffix = "..." if new_end < len(new_tokens) else ""

        old_text = f"{old_prefix}{old_text}{old_suffix}".strip()
        new_text = f"{new_prefix}{new_text}{new_suffix}".strip()

        return old_text, new_text

    def _build_change_diff(self, old_html, new_html):
        old_text = self._normalize_plain_text(old_html)
        new_text = self._normalize_plain_text(new_html)
        if not old_text and not new_text:
            return {"before": "", "after": ""}
        if not old_text:
            escaped = html_lib.escape(new_text, quote=True)
            return {"before": "", "after": self._truncate_text(escaped)}

        old_sentences = self._split_sentences(old_text)
        new_sentences = self._split_sentences(new_text)
        if not new_sentences:
            return {"before": "", "after": ""}

        new_sentence = next((s for s in new_sentences if s not in old_sentences), new_sentences[0])
        best_old = ""
        best_ratio = 0.0
        for sentence in old_sentences:
            ratio = difflib.SequenceMatcher(None, sentence, new_sentence).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_old = sentence
        if not best_old:
            best_old = old_sentences[0] if old_sentences else ""

        before, after = self._highlight_sentence_diff(best_old, new_sentence)
        return {
            "before": before,
            "after": after,
        }

    def track_article_view(self):
        self.ensure_one()
        if not self._can_read_article():
            return False
        View = self.env['knowledge.article.view'].sudo()
        now = fields.Datetime.now()
        view = View.search([
            ('user_id', '=', self.env.user.id),
            ('article_id', '=', self.id),
        ], limit=1)
        if view:
            view.write({
                'view_count': view.view_count + 1,
                'last_viewed': now,
            })
        else:
            View.create({
                'user_id': self.env.user.id,
                'article_id': self.id,
                'view_count': 1,
                'first_viewed': now,
                'last_viewed': now,
            })
        return True

    @api.model
    def get_dashboard_cards(self, limit=5):
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 5
        limit = max(1, min(limit, 20))

        user_id = self.env.user.id
        View = self.env['knowledge.article.view'].sudo()

        recent_views = View.search(
            [('user_id', '=', user_id)],
            order='last_viewed desc',
            limit=limit,
        )
        popular_views = View.search(
            [('user_id', '=', user_id)],
            order='view_count desc, last_viewed desc',
            limit=limit,
        )

        def _serialize_article(article, extra=None):
            update_user = article.write_uid
            return {
                'id': article.id,
                'name': article.name or '',
                'category_name': article.category_id.name or '',
                'responsible_name': article.responsible_id.name or '',
                'responsible_avatar': article.responsible_id.image_128 or False,
                'write_date': fields.Datetime.to_string(article.write_date) if article.write_date else '',
                'create_date': fields.Datetime.to_string(article.create_date) if article.create_date else '',
                'last_change_summary': article.last_change_summary or '',
                'update_user_name': update_user.name if update_user else '',
                'update_user_avatar': update_user.image_128 if update_user else False,
                **(extra or {}),
            }

        def _serialize_ordered(view_records, include_view=False):
            article_ids = view_records.mapped('article_id').ids
            articles = {a.id: a for a in self.browse(article_ids).exists() if a.active}
            result = []
            for view in view_records:
                article = articles.get(view.article_id.id)
                if not article:
                    continue
                extra = {}
                if include_view:
                    extra = {
                        'last_viewed': fields.Datetime.to_string(view.last_viewed) if view.last_viewed else '',
                        'view_count': view.view_count,
                    }
                result.append(_serialize_article(article, extra))
            return result

        recent_articles = _serialize_ordered(recent_views, include_view=True)
        popular_articles = _serialize_ordered(popular_views, include_view=False)

        revision_map = {}
        updated_articles = self.browse([])
        revisions = self.env['knowledge.article.revision'].sudo().search(
            [('article_id.active', '=', True)],
            order='create_date desc',
            limit=limit * 5,
        )
        for rev in revisions:
            article = self.browse(rev.article_id.id)
            if not article.exists() or not article.active:
                continue
            if not article._can_read_article():
                continue
            if article.id in revision_map:
                continue
            revision_map[article.id] = rev
            updated_articles += article
            if len(updated_articles) >= limit:
                break

        newest_articles = self.search([
            ('active', '=', True),
        ], order='create_date desc', limit=limit)

        return {
            'recent': recent_articles,
            'popular': popular_articles,
            'updated': [
                _serialize_article(a, {
                    'change_before': diff.get('before'),
                    'change_after': diff.get('after'),
                    'update_user_name': updater.name if updater else '',
                    'update_user_avatar': updater.image_128 if updater else False,
                })
                for a in updated_articles
                for rev in [revision_map.get(a.id)]
                for updater in [rev.create_uid if rev and rev.create_uid else a.write_uid]
                for diff in [self._build_change_diff(
                    revision_map.get(a.id).content if revision_map.get(a.id) else "",
                    a.content or "",
                )]
            ],
            'newest': [_serialize_article(a) for a in newest_articles],
        }
    def _can_manage_share(self, user=None):
        return self._can_edit_article(user=user)

    def _sync_shared_user_ids(self):
        for article in self:
            user_ids = article.share_member_ids.mapped('user_id').ids
            article.with_context(
                skip_share_member_sync=True,
                skip_article_access_check=True
            ).write({'shared_user_ids': [(6, 0, user_ids)]})

    def _ensure_members_from_shared_users(self):
        for article in self:
            shared_ids = set(article.shared_user_ids.ids)
            member_ids = set(article.share_member_ids.mapped('user_id').ids)
            missing_ids = shared_ids - member_ids
            for user_id in missing_ids:
                self.env['knowledge.article.member'].create({
                    'article_id': article.id,
                    'user_id': user_id,
                    'permission': article.default_share_permission or 'read',
                })

    def _prepare_share_members_payload(self):
        self.ensure_one()
        responsible = self.responsible_id
        members = []
        member_user_ids = set()
        for member in self.share_member_ids:
            member_user_ids.add(member.user_id.id)
            members.append({
                'member_id': member.id,
                'user_id': member.user_id.id,
                'name': member.user_id.name,
                'email': member.user_id.email or member.user_id.login or '',
                'permission': member.permission,
                'is_owner': responsible and member.user_id.id == responsible.id,
            })
        if responsible and responsible.id not in member_user_ids:
            members.insert(0, {
                'member_id': False,
                'user_id': responsible.id,
                'name': responsible.name,
                'email': responsible.email or responsible.login or '',
                'permission': 'edit',
                'is_owner': True,
            })
        return members

    def get_share_info(self):
        self.ensure_one()
        can_manage = self._can_manage_share()
        if can_manage:
            self._ensure_members_from_shared_users()
        return {
            'share_public': self.share_public,
            'share_link': self.share_link if self.share_public else False,
            'default_permission': self.default_share_permission,
            'members': self._prepare_share_members_payload(),
            'can_manage': can_manage,
            'category_name': self.category_id.name if self.category_id else _('Uncategorized'),
            'shared_user_ids': self.shared_user_ids.ids,
        }

    def set_share_public(self, is_public):
        self.ensure_one()
        if not self._can_manage_share():
            raise AccessError(_('You do not have permission to manage sharing for this article.'))
        self.share_public = bool(is_public)
        if self.share_public and not self.share_token:
            self.generate_share_token()
        return {
            'share_public': self.share_public,
            'share_link': self.share_link if self.share_public else False,
        }

    def set_default_share_permission(self, permission):
        self.ensure_one()
        if not self._can_manage_share():
            raise AccessError(_('You do not have permission to manage sharing for this article.'))
        if permission not in ('read', 'edit'):
            raise UserError(_('Invalid permission value.'))
        self.default_share_permission = permission
        return True

    def add_share_member(self, user_identifier, permission=None):
        self.ensure_one()
        if not self._can_manage_share():
            raise AccessError(_('You do not have permission to manage sharing for this article.'))
        if not user_identifier:
            raise UserError(_('Please provide a user name or email.'))
        permission = permission or self.default_share_permission or 'read'
        if permission not in ('read', 'edit'):
            raise UserError(_('Invalid permission value.'))

        user = self.env['res.users']
        if isinstance(user_identifier, int):
            user = self.env['res.users'].browse(user_identifier)
        else:
            identifier = str(user_identifier).strip()
            if identifier.isdigit():
                user = self.env['res.users'].browse(int(identifier))
            if not user or not user.exists():
                user = self.env['res.users'].search([
                    '&', '&', ('share', '=', False), ('active', '=', True),
                    '|', '|', ('login', '=', identifier), ('email', '=', identifier), ('partner_id.email', '=', identifier)
                ], limit=1)
            if not user:
                user = self.env['res.users'].search([
                    '&', '&', ('share', '=', False), ('active', '=', True),
                    ('name', 'ilike', identifier)
                ], limit=1)
        user = user.exists()
        if not user:
            raise UserError(_('User not found. Please choose an existing internal user.'))
        if user.share:
            raise UserError(_('Only internal users can be invited.'))
        if self.responsible_id and user.id == self.responsible_id.id:
            raise UserError(_('The owner already has full access.'))

        member = self.env['knowledge.article.member'].search([
            ('article_id', '=', self.id),
            ('user_id', '=', user.id)
        ], limit=1)
        if member:
            member.permission = permission
        else:
            self.env['knowledge.article.member'].create({
                'article_id': self.id,
                'user_id': user.id,
                'permission': permission,
            })

        self._sync_shared_user_ids()
        return True

    def update_share_member_permission(self, member_id, permission):
        self.ensure_one()
        if not self._can_manage_share():
            raise AccessError(_('You do not have permission to manage sharing for this article.'))
        if permission not in ('read', 'edit'):
            raise UserError(_('Invalid permission value.'))
        member = self.env['knowledge.article.member'].browse(member_id)
        if not member or member.article_id.id != self.id:
            raise UserError(_('Share member not found.'))
        if self.responsible_id and member.user_id.id == self.responsible_id.id:
            raise UserError(_('Cannot change owner permissions.'))
        member.permission = permission
        self._sync_shared_user_ids()
        return True

    def remove_share_member(self, member_id):
        self.ensure_one()
        if not self._can_manage_share():
            raise AccessError(_('You do not have permission to manage sharing for this article.'))
        member = self.env['knowledge.article.member'].browse(member_id)
        if not member or member.article_id.id != self.id:
            raise UserError(_('Share member not found.'))
        if self.responsible_id and member.user_id.id == self.responsible_id.id:
            raise UserError(_('Cannot remove the owner from sharing.'))
        member.unlink()
        self._sync_shared_user_ids()
        return True

    def _get_revision_tracked_fields(self):
        return {
            'name',
            'content',
            'category_id',
            'parent_id',
            'tag_ids',
        }

    def _should_create_revision(self, vals):
        tracked_fields = self._get_revision_tracked_fields()
        return bool(tracked_fields.intersection(vals.keys()))

    def _copy_attachments_to_revision(self, revision):
        Attachment = self.env['ir.attachment'].sudo()
        attachments = Attachment.search([
            ('res_model', '=', 'knowledge.article'),
            ('res_id', '=', self.id),
        ])
        for attachment in attachments:
            attachment.copy({
                'res_model': 'knowledge.article.revision',
                'res_id': revision.id,
            })

    def _create_revision_snapshot(self):
        self.ensure_one()
        revision = self.env['knowledge.article.revision'].create({
            'article_id': self.id,
            'name': self.name or '',
            'content': self.content or '',
            'category_id': self.category_id.id or False,
            'parent_id': self.parent_id.id or False,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
        })
        self._copy_attachments_to_revision(revision)
        return revision

    def write(self, vals):
        skip_change_summary = self.env.context.get('skip_change_summary')
        if not self.env.context.get('skip_article_access_check'):
            allowed_fields = {'favorite_user_ids'}
            for article in self:
                if not article._can_edit_article() and not (set(vals.keys()) <= allowed_fields):
                    raise AccessError(_('You do not have permission to edit this article.'))
        old_contents = {}
        if 'content' in vals:
            for article in self:
                old_contents[article.id] = article.content or ''
        if not self.env.context.get('skip_revision') and self._should_create_revision(vals):
            for article in self:
                article._create_revision_snapshot()
        res = super().write(vals)
        if 'content' in vals and not skip_change_summary:
            for article in self:
                summary = article._build_change_summary(old_contents.get(article.id), article.content or '')
                article.with_context(
                    skip_revision=True,
                    skip_article_access_check=True,
                    skip_change_summary=True,
                ).write({'last_change_summary': summary or False})
        return res
    
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
        
        This method checks if the current user has read access to the article
        before returning attachment information. It uses sudo() to read attachment
        metadata but ensures proper access control.
        
        Returns:
            dict: Attachment data with id, name, mimetype, and url, or empty dict if no PDF found
        """
        import logging
        _logger = logging.getLogger(__name__)
        
        self.ensure_one()
        
        # Check if current user has read access to this article
        if not self._can_read_article():
            _logger.warning(f"User {self.env.user.id} does not have read access to article {self.id}")
            return {}
        
        # Use sudo() to read attachment metadata (we've already checked article access)
        attachment_model = self.env['ir.attachment'].sudo()
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
        
        def _build_attachment_url(attachment, provided_access_token=None):
            """Build attachment URL with proper access handling
            
            This uses the knowledge controller endpoint which checks article read access
            before serving the attachment. This allows users with article read permissions
            to view PDF attachments even if they don't have direct attachment access.
            
            Args:
                attachment: ir.attachment record
                provided_access_token: Optional access token (if found in HTML content, etc.)
            
            Returns:
                tuple: (url, access_url)
            """
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            attachment_id = attachment.id
            article_id = self.id
            
            # Use the knowledge controller endpoint that checks article read access
            # This ensures users with article read permissions can view attachments
            url = f"{base_url}/knowledge/article/{article_id}/attachment/{attachment_id}?download=true"
            access_url = f"{base_url}/knowledge/article/{article_id}/attachment/{attachment_id}"
            
            return url, access_url
        
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        
        _logger.info(f"Getting PDF attachment for article {self.id} ({self.name}) - User: {self.env.user.id}")
        
        # First, check message_main_attachment_id if available (Odoo 13+)
        # This is the main attachment shown in chatter
        if hasattr(self, 'message_main_attachment_id') and self.message_main_attachment_id:
            main_attachment = self.message_main_attachment_id
            _logger.info(f"Found message_main_attachment_id: {main_attachment.id}, mimetype: {main_attachment.mimetype}")
            if _is_pdf_attachment(main_attachment):
                url, access_url = _build_attachment_url(main_attachment)
                result = {
                    'id': main_attachment.id,
                    'name': main_attachment.name,
                    'mimetype': main_attachment.mimetype or 'application/pdf',
                    'url': url,
                    'access_url': access_url,
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
            url, access_url = _build_attachment_url(attachment)
            result = {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype or 'application/pdf',
                'url': url,
                'access_url': access_url,
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
                    url, access_url = _build_attachment_url(attachment)
                    result = {
                        'id': attachment.id,
                        'name': attachment.name,
                        'mimetype': attachment.mimetype or 'application/pdf',
                        'url': url,
                        'access_url': access_url,
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
            url, access_url = _build_attachment_url(attachment)
            result = {
                'id': attachment.id,
                'name': attachment.name,
                'mimetype': attachment.mimetype or 'application/pdf',
                'url': url,
                'access_url': access_url,
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
                url, access_url = _build_attachment_url(attachment)
                result = {
                    'id': attachment.id,
                    'name': attachment.name,
                    'mimetype': attachment.mimetype or 'application/pdf',
                    'url': url,
                    'access_url': access_url,
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
                            url, access_url = _build_attachment_url(attachment, access_token)
                            result = {
                                'id': attachment.id,
                                'name': attachment.name or filename or f"Attachment {attachment.id}",
                                'mimetype': attachment.mimetype or 'application/pdf',
                                'url': url,
                                'access_url': access_url,
                            }
                            _logger.info(f"Returning PDF attachment found from embedded file ID: {result}")
                            return result
                    if access_token and has_access_token:
                        attachment = attachment_model.search([
                            ('access_token', '=', access_token),
                        ], limit=1)
                        if attachment and (is_pdf_hint or _is_pdf_attachment(attachment)):
                            url, access_url = _build_attachment_url(attachment, access_token)
                            result = {
                                'id': attachment.id,
                                'name': attachment.name or filename or f"Attachment {attachment.id}",
                                'mimetype': attachment.mimetype or 'application/pdf',
                                'url': url,
                                'access_url': access_url,
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
                        url, access_url = _build_attachment_url(attachment)
                        name_hint = candidate['file_hint'].strip() or candidate['text'].strip()
                        result = {
                            'id': attachment.id,
                            'name': attachment.name or name_hint or f"Attachment {attachment.id}",
                            'mimetype': attachment.mimetype or 'application/pdf',
                            'url': url,
                            'access_url': access_url,
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
                                url, access_url = _build_attachment_url(attachment)
                                result = {
                                    'id': attachment.id,
                                    'name': attachment.name,
                                    'mimetype': attachment.mimetype or 'application/pdf',
                                    'url': url,
                                    'access_url': access_url,
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
