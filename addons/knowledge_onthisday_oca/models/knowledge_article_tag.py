# -*- coding: utf-8 -*-

from odoo import models, fields, api


class KnowledgeArticleTag(models.Model):
    """Knowledge Article Tag Model
    
    Represents a tag/label for categorizing and organizing knowledge articles.
    """
    _name = 'knowledge.article.tag'
    _description = 'Knowledge Article Tag'
    _order = 'name'

    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True,
        help='Name of the tag'
    )
    
    color = fields.Integer(
        string='Color Index',
        default=0,
        help='Color index for tag display (0-11)'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, it will allow you to hide the tag without removing it.'
    )
    
    article_count = fields.Integer(
        string='Article Count',
        compute='_compute_article_count',
        store=False,
        help='Number of articles with this tag'
    )
    
    @api.depends('name')
    def _compute_article_count(self):
        """Compute the number of articles with this tag"""
        for tag in self:
            # Only compute if tag has a real ID (not NewId)
            if tag.id and isinstance(tag.id, int):
                tag.article_count = self.env['knowledge.article'].search_count([
                    ('tag_ids', 'in', [tag.id]),
                    ('active', '=', True)
                ])
            else:
                # For new tags (NewId), set count to 0
                tag.article_count = 0

