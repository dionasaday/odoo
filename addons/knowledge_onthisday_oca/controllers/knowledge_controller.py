# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.http import request, Response
from odoo.exceptions import AccessError, MissingError
from odoo.tools import str2bool


_logger = logging.getLogger(__name__)


class KnowledgeController(http.Controller):

    @http.route('/knowledge/article/<string:token>', type='http', auth='public', website=True, csrf=False)
    def view_shared_article(self, token, **kwargs):
        """Public view for shared knowledge article"""
        try:
            article = request.env['knowledge.article'].sudo().search([
                ('share_token', '=', token),
                ('share_public', '=', True),
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
            article_icon = article.icon or category_icon or '📝'

            values = {
                'article': article,
                'category_name': category_name,
                'category_icon': category_icon,
                'article_icon': article_icon,
                'base_url': request.env['ir.config_parameter'].sudo().get_param('web.base.url'),
            }

            return request.render('knowledge_onthisday_oca.article_public_view', values)

        except Exception as e:
            _logger.exception("Error rendering shared article with token %s", token)
            return request.render('knowledge_onthisday_oca.article_not_found', {
                'error_message': 'An error occurred while loading the article.'
            })

    @http.route('/knowledge/article/<int:article_id>/attachment/<int:attachment_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_article_attachment(self, article_id, attachment_id, **kwargs):
        """Get attachment for an article
        
        This endpoint checks if the user has read access to the article before
        serving the attachment. This allows users with article read permissions
        to view PDF attachments even if they don't have direct attachment access.
        
        Args:
            article_id: ID of the knowledge article
            attachment_id: ID of the attachment to retrieve
        
        Returns:
            HTTP response with attachment content or 403/404 error
        """
        try:
            # Get article and check read access
            article = request.env['knowledge.article'].browse(article_id)
            if not article.exists():
                return request.not_found("Article not found")
            
            # Check if user has read access to the article
            if not article._can_read_article():
                _logger.warning(f"User {request.env.user.id} denied access to article {article_id} attachment {attachment_id}")
                return request.forbidden("You do not have permission to access this article's attachments")
            
            # Get attachment - use sudo() since we've already checked article access
            attachment = request.env['ir.attachment'].sudo().browse(attachment_id)
            if not attachment.exists():
                return request.not_found("Attachment not found")
            
            # Verify attachment is related to the article
            # Check if attachment is linked to article directly or via messages
            is_linked = False
            if attachment.res_model == 'knowledge.article' and attachment.res_id == article_id:
                is_linked = True
            elif attachment.res_model == 'mail.message':
                # Check if message belongs to this article
                if hasattr(article, 'message_ids') and attachment.res_id in article.message_ids.ids:
                    is_linked = True
            elif hasattr(article, 'message_main_attachment_id') and article.message_main_attachment_id.id == attachment_id:
                is_linked = True
            
            if not is_linked:
                # Also check if attachment is referenced in article content
                if article.content and str(attachment_id) in article.content:
                    is_linked = True
            
            if not is_linked:
                _logger.warning(f"Attachment {attachment_id} is not linked to article {article_id}")
                return request.forbidden("This attachment does not belong to the specified article")
            
            # Serve the attachment using ir.binary streaming (Odoo 19+)
            try:
                stream = request.env['ir.binary']._get_stream_from(
                    attachment,
                    field_name='raw',
                    filename_field='name',
                    mimetype=attachment.mimetype,
                )
                download = str2bool(kwargs.get('download', False))
                return stream.get_response(as_attachment=download)
            except Exception as e:
                _logger.error(f"Error streaming attachment {attachment_id}: {e}")
                return Response("Error retrieving attachment", status=500)
            
        except AccessError:
            _logger.warning(f"Access denied for article {article_id} attachment {attachment_id} by user {request.env.user.id}")
            return request.forbidden("Access denied")
        except Exception as e:
            _logger.exception(f"Error serving article {article_id} attachment {attachment_id}")
            return Response("An error occurred while retrieving the attachment", status=500)
