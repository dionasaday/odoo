# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessError, MissingError


class KnowledgeController(http.Controller):

    @http.route('/knowledge/article/<string:token>', type='http', auth='public', website=True, csrf=False)
    def view_shared_article(self, token, **kwargs):
        """Public view for shared knowledge article"""
        try:
            article = request.env['knowledge.article'].sudo().search([
                ('share_token', '=', token),
                ('active', '=', True)
            ], limit=1)

            if not article:
                return request.render('knowledge_onthisday_oca.article_not_found', {
                    'error_message': 'Article not found or link has expired.'
                })

            # Get category info
            category_name = 'Uncategorized'
            category_icon = '📝'
            if article.category_id:
                category_name = article.category_id.name
                category_icon = article.category_id.icon or '📝'

            values = {
                'article': article,
                'category_name': category_name,
                'category_icon': category_icon,
                'base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            }

            return request.render('knowledge_onthisday_oca.article_public_view', values)

        except Exception as e:
            return request.render('knowledge_onthisday_oca.article_not_found', {
                'error_message': f'An error occurred: {str(e)}'
            })

