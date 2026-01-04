# -*- coding: utf-8 -*-

from odoo import models, fields, api


class KnowledgeArticleCategory(models.Model):
    """Knowledge Article Category Model
    
    Represents a category for organizing knowledge articles.
    """
    _name = 'knowledge.article.category'
    _description = 'Knowledge Article Category'
    _inherit = ['mail.thread']
    _order = 'sequence, name'

    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        help='Name of the category'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='Internal code for the category (e.g., sop, product, system)'
    )
    
    description = fields.Text(
        string='Description',
        translate=True,
        help='Description of the category'
    )
    
    icon = fields.Char(
        string='Icon',
        default='📝',
        help='Emoji or icon character to display for this category'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence number for ordering categories'
    )
    
    color = fields.Integer(
        string='Color',
        default=0,
        help='Color index for kanban view'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='If unchecked, it will allow you to hide the category without removing it.'
    )

    default_share_permission = fields.Selection(
        selection=[('read', 'Can read'), ('edit', 'Can edit')],
        string='Default Access Rights',
        default='read',
        help='Default access rights for new shares in this category'
    )
    
    article_count = fields.Integer(
        string='Article Count',
        compute='_compute_article_count',
        store=False,
        help='Number of articles in this category'
    )
    
    @api.depends('name')
    def _compute_article_count(self):
        """Compute the number of articles in this category"""
        for category in self:
            category.article_count = self.env['knowledge.article'].search_count([
                ('category_id', '=', category.id),
                ('active', '=', True)
            ])
