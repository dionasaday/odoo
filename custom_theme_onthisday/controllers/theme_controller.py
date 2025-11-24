# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import http
from odoo.http import request


class ThemeController(http.Controller):

    @http.route('/custom_theme/get_colors', type='json', auth='user')
    def get_theme_colors(self):
        """Get theme colors from company (preferred) or config_parameter (fallback)"""
        try:
            # Default values
            primary_color = '#232222'
            secondary_color = '#623412'
            text_color = '#FFFFFF'
            
            # Try to get from company first (preferred source)
            try:
                company = request.env.company
                if company and hasattr(company, 'theme_primary_color'):
                    if company.theme_primary_color:
                        primary_color = company.theme_primary_color
                    if company.theme_secondary_color:
                        secondary_color = company.theme_secondary_color
                    if company.theme_text_color:
                        text_color = company.theme_text_color
            except Exception:
                # If company fields don't exist, fallback to config_parameter
                try:
                    ICP = request.env['ir.config_parameter'].sudo()
                    primary_color = ICP.get_param(
                        'custom_theme_onthisday.theme_primary_color',
                        default='#232222'
                    )
                    secondary_color = ICP.get_param(
                        'custom_theme_onthisday.theme_secondary_color',
                        default='#623412'
                    )
                    text_color = ICP.get_param(
                        'custom_theme_onthisday.theme_text_color',
                        default='#FFFFFF'
                    )
                except Exception:
                    # Use defaults if both fail
                    pass
            
            return {
                'theme_primary_color': primary_color,
                'theme_secondary_color': secondary_color,
                'theme_text_color': text_color,
            }
        except Exception:
            # Return defaults if any error occurs
            return {
                'theme_primary_color': '#232222',
                'theme_secondary_color': '#623412',
                'theme_text_color': '#FFFFFF',
            }

