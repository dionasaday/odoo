# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError


class OrderRepairWizard(models.TransientModel):
    _name = 'marketplace.order.repair.wizard'
    _description = 'Order Repair Wizard'

    order_id = fields.Many2one(
        'marketplace.order', string='Order', required=True
    )
    action = fields.Selection([
        ('retry_sync', 'Retry Sync'),
        ('create_so', 'Create Sale Order'),
        ('update_lines', 'Update Order Lines'),
    ], string='Action', required=True, default='retry_sync')

    def action_repair(self):
        """Repair the order"""
        self.ensure_one()
        
        if self.action == 'retry_sync':
            self.order_id._sync_to_sale_order()
            message = 'Order sync retried'
        elif self.action == 'create_so':
            if self.order_id.sale_order_id:
                raise UserError('Sale order already exists')
            self.order_id._create_sale_order()
            message = 'Sale order created'
        elif self.action == 'update_lines':
            # Update order lines with product bindings
            for line in self.order_id.order_line_ids:
                if not line.product_binding_id:
                    # Try to find binding
                    binding = self.env['marketplace.product.binding'].search([
                        ('external_sku', '=', line.external_sku),
                        ('shop_id', '=', self.order_id.shop_id.id),
                    ], limit=1)
                    if binding:
                        line.product_binding_id = binding.id
            message = 'Order lines updated'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Repair Complete',
                'message': message,
                'type': 'success',
                'sticky': False,
            }
        }

