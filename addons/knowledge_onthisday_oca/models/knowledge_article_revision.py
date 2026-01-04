# -*- coding: utf-8 -*-

from odoo import models, fields, _
from odoo.exceptions import AccessError, UserError


class KnowledgeArticleRevision(models.Model):
    _name = 'knowledge.article.revision'
    _description = 'Knowledge Article Revision'
    _order = 'create_date desc'
    _rec_name = 'name'

    article_id = fields.Many2one(
        comodel_name='knowledge.article',
        string='Article',
        required=True,
        ondelete='cascade',
        index=True
    )
    name = fields.Char(
        string='Title',
        required=True
    )
    content = fields.Html(
        string='Previous Content'
    )
    category_id = fields.Many2one(
        comodel_name='knowledge.article.category',
        string='Previous Category'
    )
    parent_id = fields.Many2one(
        comodel_name='knowledge.article',
        string='Previous Parent'
    )
    tag_ids = fields.Many2many(
        comodel_name='knowledge.article.tag',
        relation='knowledge_article_revision_tag_rel',
        column1='revision_id',
        column2='tag_id',
        string='Previous Tags'
    )
    attachment_ids = fields.One2many(
        comodel_name='ir.attachment',
        inverse_name='res_id',
        domain=[('res_model', '=', 'knowledge.article.revision')],
        string='Previous Attachments'
    )

    def action_restore_revision(self):
        self.ensure_one()
        article = self.article_id
        if not article or not article.exists():
            raise UserError(_('Article not found.'))
        if not article._can_edit_article():
            raise AccessError(_('You do not have permission to restore this revision.'))

        vals = {
            'name': self.name or '',
            'content': self.content or '',
            'category_id': self.category_id.id or False,
            'parent_id': self.parent_id.id or False,
            'tag_ids': [(6, 0, self.tag_ids.ids)],
        }
        article.with_context(
            skip_revision=True,
            skip_article_access_check=True
        ).write(vals)

        Attachment = self.env['ir.attachment'].sudo()
        current_attachments = Attachment.search([
            ('res_model', '=', 'knowledge.article'),
            ('res_id', '=', article.id),
        ])
        if current_attachments:
            current_attachments.unlink()
        for attachment in self.attachment_ids:
            attachment.copy({
                'res_model': 'knowledge.article',
                'res_id': article.id,
            })

        if hasattr(article, 'message_main_attachment_id'):
            main_attachment = Attachment.search([
                ('res_model', '=', 'knowledge.article'),
                ('res_id', '=', article.id),
            ], limit=1)
            article.with_context(
                skip_revision=True,
                skip_article_access_check=True
            ).write({'message_main_attachment_id': main_attachment.id or False})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'knowledge.article',
            'res_id': article.id,
            'view_mode': 'form',
            'views': [[False, 'form']],
            'target': 'current',
        }
