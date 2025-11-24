# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    """Extend res.config.settings to add theme color fields in Settings"""
    _inherit = 'res.config.settings'

    # Theme Color Fields - use computed fields to avoid database columns
    # These fields are stored in ir.config_parameter, not in database columns
    theme_primary_color = fields.Char(
        string='Theme Primary Color',
        compute='_compute_theme_colors',
        inverse='_inverse_theme_colors',
        help='Primary color for theme (Hex code, e.g., #232222). This will be applied to Navigation Bar, Buttons, and other UI elements.'
    )
    
    theme_secondary_color = fields.Char(
        string='Theme Secondary Color',
        compute='_compute_theme_colors',
        inverse='_inverse_theme_colors',
        help='Secondary color for theme (Hex code, e.g., #623412). This will be used for hover states and active elements.'
    )
    
    theme_text_color = fields.Char(
        string='Theme Text Color',
        compute='_compute_theme_colors',
        inverse='_inverse_theme_colors',
        help='Text color for theme (Hex code, e.g., #FFFFFF). This will be used for text on primary color background.'
    )
    
    @api.depends()
    def _compute_theme_colors(self):
        """Compute theme colors from config_parameter"""
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            record.theme_primary_color = ICP.get_param(
                'custom_theme_onthisday.theme_primary_color',
                default='#232222'
            )
            record.theme_secondary_color = ICP.get_param(
                'custom_theme_onthisday.theme_secondary_color',
                default='#623412'
            )
            record.theme_text_color = ICP.get_param(
                'custom_theme_onthisday.theme_text_color',
                default='#FFFFFF'
            )
    
    def _inverse_theme_colors(self):
        """Inverse theme colors to config_parameter"""
        ICP = self.env['ir.config_parameter'].sudo()
        for record in self:
            ICP.set_param('custom_theme_onthisday.theme_primary_color', record.theme_primary_color or '#232222')
            ICP.set_param('custom_theme_onthisday.theme_secondary_color', record.theme_secondary_color or '#623412')
            ICP.set_param('custom_theme_onthisday.theme_text_color', record.theme_text_color or '#FFFFFF')
            
            # Sync to company if fields exist
            try:
                company = self.env.company
                if company and hasattr(company, 'theme_primary_color'):
                    company.theme_primary_color = record.theme_primary_color or '#232222'
                    company.theme_secondary_color = record.theme_secondary_color or '#623412'
                    company.theme_text_color = record.theme_text_color or '#FFFFFF'
            except Exception:
                # Ignore errors if fields don't exist yet
                pass

