# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class BulkBindingWizard(models.TransientModel):
    _name = 'marketplace.bulk.binding.wizard'
    _description = 'Bulk Product Binding Wizard'

    shop_id = fields.Many2one(
        'marketplace.shop', string='Shop', required=True
    )
    product_ids = fields.Many2many(
        'product.product', string='Products', required=True
    )
    auto_sku = fields.Boolean(
        string='Auto-generate SKU',
        default=True,
        help='Generate external SKU from product default code'
    )
    sku_prefix = fields.Char(
        string='SKU Prefix',
        help='Prefix for auto-generated SKU (optional)'
    )

    def action_create_bindings(self):
        """Create bindings for selected products"""
        self.ensure_one()
        
        if not self.product_ids:
            raise UserError('Please select at least one product')
        
        created = 0
        skipped = 0
        
        for product in self.product_ids:
            # Check if binding already exists
            existing = self.env['marketplace.product.binding'].search([
                ('product_id', '=', product.id),
                ('shop_id', '=', self.shop_id.id),
            ], limit=1)
            
            if existing:
                skipped += 1
                continue
            
            # Generate SKU
            if self.auto_sku:
                external_sku = product.default_code or f'PROD-{product.id}'
                if self.sku_prefix:
                    external_sku = f'{self.sku_prefix}-{external_sku}'
            else:
                external_sku = product.default_code or f'PROD-{product.id}'
            
            # Create binding
            self.env['marketplace.product.binding'].create({
                'product_id': product.id,
                'shop_id': self.shop_id.id,
                'external_sku': external_sku,
            })
            created += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bindings Created',
                'message': f'{created} bindings created, {skipped} skipped',
                'type': 'success',
                'sticky': False,
            }
        }

