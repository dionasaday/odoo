# -*- coding: utf-8 -*-

from odoo import models, fields


class KnowledgeArticleView(models.Model):
    _name = 'knowledge.article.view'
    _description = 'Knowledge Article View'
    _order = 'last_viewed desc'
    _rec_name = 'article_id'

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
    view_count = fields.Integer(
        string='View Count',
        default=0,
        required=True,
    )
    last_viewed = fields.Datetime(
        string='Last Viewed',
        default=fields.Datetime.now,
        required=True,
    )
    first_viewed = fields.Datetime(
        string='First Viewed',
        default=fields.Datetime.now,
        required=True,
    )

    _sql_constraints = [
        ('knowledge_article_view_user_unique', 'unique(article_id, user_id)', 'View record must be unique per user and article.'),
    ]
