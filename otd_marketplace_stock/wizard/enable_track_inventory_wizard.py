# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class EnableTrackInventoryWizard(models.TransientModel):
    _name = 'enable.track.inventory.wizard'
    _description = 'Wizard to Enable Track Inventory for Products'

    # Filter options
    filter_by_sku = fields.Boolean(
        string='Filter by SKU',
        default=True,
        help='Only update products that have SKU (likely synced from Zortout)'
    )
    
    filter_by_type = fields.Selection([
        ('all', 'All Types'),
        ('consu', 'Goods Only'),
        ('service', 'Service Only'),
    ], string='Product Type Filter', default='consu',
       help='Filter products by type')
    
    filter_tracking = fields.Selection([
        ('none', 'Not Tracking (none)'),
        ('all', 'All (including already tracking)'),
    ], string='Tracking Status Filter', default='all',
       help='Update all products or only those not tracking yet')
    
    limit = fields.Integer(
        string='Limit',
        default=0,
        help='Maximum number of products to update (0 = no limit)'
    )
    
    # Results (computed)
    estimated_count = fields.Integer(
        string='Estimated Products to Update',
        compute='_compute_estimated_count',
        readonly=True
    )
    
    @api.depends('filter_by_sku', 'filter_by_type', 'filter_tracking')
    def _compute_estimated_count(self):
        """Estimate how many products will be updated"""
        for wizard in self:
            domain = []
            
            if wizard.filter_by_sku:
                domain.append(('default_code', '!=', False))
            
            if wizard.filter_by_type == 'consu':
                domain.append(('type', '=', 'consu'))
            elif wizard.filter_by_type == 'service':
                domain.append(('type', '=', 'service'))
            
            if wizard.filter_tracking == 'none':
                domain.append(('tracking', 'in', ['none', False]))
            
            count = self.env['product.template'].search_count(domain)
            wizard.estimated_count = count
    
    def action_enable_track_inventory(self):
        """Enable Track Inventory for selected products"""
        self.ensure_one()
        
        _logger.warning(f'🚀 Starting bulk update to enable Track Inventory...')
        _logger.warning(f'   Filter by SKU: {self.filter_by_sku}')
        _logger.warning(f'   Filter by Type: {self.filter_by_type}')
        _logger.warning(f'   Filter Tracking: {self.filter_tracking}')
        _logger.warning(f'   Limit: {self.limit or "No limit"}')
        
        # Build domain
        domain = []
        
        if self.filter_by_sku:
            domain.append(('default_code', '!=', False))
        
        if self.filter_by_type == 'consu':
            domain.append(('type', '=', 'consu'))
        elif self.filter_by_type == 'service':
            domain.append(('type', '=', 'service'))
        
        if self.filter_tracking == 'none':
            domain.append(('tracking', 'in', ['none', False]))
        
        # Search products
        products = self.env['product.template'].sudo().search(domain, limit=self.limit or None)
        total_count = len(products)
        
        _logger.warning(f'📦 Found {total_count} products to update')
        
        if total_count == 0:
            raise UserError('No products found matching the criteria')
        
        # Update products
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for idx, product in enumerate(products, 1):
            try:
                # In Odoo 19, to enable "Track Inventory? By Quantity":
                # - tracking='none' → "By Quantity" (tracks by quantity, no lot/serial)
                # - tracking='lot' → "By Lots" (tracks by lot numbers)
                # - tracking='serial' → "By Serial Numbers" (tracks by serial numbers)
                # 
                # IMPORTANT: Checkbox visibility is controlled by 'is_storable' field
                # - If is_storable=False, checkbox will be HIDDEN
                # - We need to set is_storable=True to show the checkbox
                product.write({
                    'tracking': 'none',  # "By Quantity"
                    'is_storable': True,  # Show Track Inventory checkbox in UI
                })
                updated_count += 1
                
                # Commit every 100 products to avoid long transaction
                if updated_count % 100 == 0:
                    self.env.cr.commit()
                    _logger.warning(f'📊 Progress: {updated_count}/{total_count} products updated')
                
            except Exception as e:
                skipped_count += 1
                error_msg = f"Product {product.default_code or product.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg, exc_info=True)
        
        # Final commit
        self.env.cr.commit()
        
        _logger.warning(f'✅ Bulk update completed: {updated_count} updated, {skipped_count} skipped')
        
        # Prepare result message
        message_parts = []
        message_parts.append(f'<b>Bulk Update Completed:</b><br/>')
        message_parts.append(f'✅ Updated: {updated_count} products<br/>')
        if skipped_count > 0:
            message_parts.append(f'⚠️ Skipped: {skipped_count} products<br/>')
        if errors:
            message_parts.append(f'<br/><b>Errors ({min(len(errors), 10)} of {len(errors)}):</b><br/>')
            for error in errors[:10]:
                message_parts.append(f'• {error}<br/>')
        
        message = ''.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Update Completed',
                'message': message,
                'type': 'success' if skipped_count == 0 else 'warning',
                'sticky': True,
            }
        }

