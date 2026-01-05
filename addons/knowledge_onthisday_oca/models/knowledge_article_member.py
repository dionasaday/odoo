# -*- coding: utf-8 -*-

from odoo import api, models, fields


class KnowledgeArticleMember(models.Model):
    _name = 'knowledge.article.member'
    _description = 'Knowledge Article Share Member'
    _order = 'create_date desc'
    _sql_constraints = [
        ('knowledge_article_member_unique', 'unique(article_id, user_id)', 'User already has access to this article.'),
    ]

    article_id = fields.Many2one(
        comodel_name='knowledge.article',
        string='Article',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
    )
    permission = fields.Selection(
        selection=[('read', 'Can read'), ('edit', 'Can edit')],
        string='Permission',
        default='read',
        required=True,
    )
    user_email = fields.Char(
        string='Email',
        related='user_id.email',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        for vals in vals_list:
            if not vals.get('permission') and vals.get('article_id'):
                article = self.env['knowledge.article'].browse(vals['article_id'])
                if article and article.default_share_permission:
                    vals['permission'] = article.default_share_permission
        records = super().create(vals_list)
        records.mapped('article_id')._sync_shared_user_ids()
        return records

    def write(self, vals):
        res = super().write(vals)
        self.mapped('article_id')._sync_shared_user_ids()
        return res

    def unlink(self):
        articles = self.mapped('article_id')
        res = super().unlink()
        articles._sync_shared_user_ids()
        return res
