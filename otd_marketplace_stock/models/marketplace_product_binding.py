# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MarketplaceProductBinding(models.Model):
    _name = 'marketplace.product.binding'
    _description = 'Marketplace Product Binding'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'product_id, shop_id'

    product_id = fields.Many2one(
        'product.product', string='Product', required=True,
        ondelete='cascade', tracking=True
    )
    product_template_id = fields.Many2one(
        related='product_id.product_tmpl_id', string='Product Template',
        readonly=True, store=True
    )
    shop_id = fields.Many2one(
        'marketplace.shop', string='Shop', required=True,
        ondelete='cascade', tracking=True
    )
    account_id = fields.Many2one(
        related='shop_id.account_id', string='Account',
        readonly=True, store=True
    )
    channel = fields.Selection(
        related='shop_id.channel', string='Channel', readonly=True
    )
    company_id = fields.Many2one(
        related='product_id.company_id', string='Company', readonly=True
    )
    
    # External marketplace identifiers
    external_sku = fields.Char(
        string='External SKU', required=True, tracking=True,
        help='SKU on marketplace platform'
    )
    external_product_id = fields.Char(
        string='External Product ID', tracking=True,
        help='Product ID on marketplace platform'
    )
    
    # Sync settings
    active = fields.Boolean(string='Active', default=True, tracking=True)
    exclude_push = fields.Boolean(
        string='Exclude from Push', default=False,
        help='Exclude this product from stock push'
    )
    
    # Override sync rules
    buffer_qty_override = fields.Integer(
        string='Buffer Override',
        help='Override account buffer for this product (empty = use account default)'
    )
    min_qty_override = fields.Integer(
        string='Min Qty Override',
        help='Override account min qty for this product'
    )
    
    # Statistics
    last_stock_push_at = fields.Datetime(string='Last Stock Push', readonly=True)
    current_online_qty = fields.Integer(
        string='Current Online Qty', readonly=True,
        help='Last pushed quantity to marketplace'
    )

    display_name = fields.Char(
        string='Display Name', compute='_compute_display_name', store=True
    )

    @api.depends('product_id', 'shop_id', 'external_sku')
    def _compute_display_name(self):
        for binding in self:
            if binding.product_id and binding.shop_id:
                binding.display_name = f'{binding.product_id.name} - {binding.shop_id.name} ({binding.external_sku})'
            else:
                binding.display_name = binding.external_sku or 'New'

    @api.constrains('external_sku', 'shop_id')
    def _check_unique_sku(self):
        for binding in self:
            duplicate = self.search([
                ('external_sku', '=', binding.external_sku),
                ('shop_id', '=', binding.shop_id.id),
                ('id', '!=', binding.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'SKU {binding.external_sku} already exists for shop {binding.shop_id.name}'
                )

    @api.constrains('product_id', 'shop_id')
    def _check_company_match(self):
        for binding in self:
            if binding.product_id.company_id and binding.shop_id.company_id:
                if binding.product_id.company_id != binding.shop_id.company_id:
                    raise ValidationError(
                        'Product and Shop must belong to the same company'
                    )

    def action_push_stock(self):
        """Manually push stock for this binding"""
        self.ensure_one()
        if not self.active:
            raise ValidationError('Binding is not active')
        if self.exclude_push:
            raise ValidationError('This product is excluded from push')
        if self.shop_id and self.shop_id.channel == 'zortout':
            raise ValidationError('Zortout is inbound-only. Stock push to Zortout is disabled.')
        
        # Queue job
        self.env['marketplace.job'].sudo().create({
            'name': f'Push stock for {self.display_name}',
            'job_type': 'push_stock',
            'priority': 'medium',  # Stock push is medium priority
            'payload': {
                'binding_ids': [self.id],
            },
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Stock Push Queued',
                'message': f'Stock push job queued for {self.display_name}',
                'type': 'success',
                'sticky': False,
            }
        }

