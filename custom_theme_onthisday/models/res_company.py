# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class ResCompany(models.Model):
    """Extend res.company to add theme color fields"""
    _inherit = 'res.company'

    # Theme Color Fields
    theme_primary_color = fields.Char(
        string='Theme Primary Color',
        default='#232222',
        help='Primary color for theme (Hex code, e.g., #232222). Changes will apply after page refresh.'
    )
    
    theme_secondary_color = fields.Char(
        string='Theme Secondary Color',
        default='#623412',
        help='Secondary color for theme (Hex code, e.g., #623412). Changes will apply after page refresh.'
    )
    
    theme_text_color = fields.Char(
        string='Theme Text Color',
        default='#FFFFFF',
        help='Text color for theme (Hex code, e.g., #FFFFFF). Changes will apply after page refresh.'
    )
    
    def write(self, vals):
        """Override write to ensure theme colors are validated"""
        # Validate hex color format if provided
        if 'theme_primary_color' in vals and vals['theme_primary_color']:
            if not vals['theme_primary_color'].startswith('#'):
                vals['theme_primary_color'] = '#' + vals['theme_primary_color']
        
        if 'theme_secondary_color' in vals and vals['theme_secondary_color']:
            if not vals['theme_secondary_color'].startswith('#'):
                vals['theme_secondary_color'] = '#' + vals['theme_secondary_color']
        
        if 'theme_text_color' in vals and vals['theme_text_color']:
            if not vals['theme_text_color'].startswith('#'):
                vals['theme_text_color'] = '#' + vals['theme_text_color']
        
        return super().write(vals)

