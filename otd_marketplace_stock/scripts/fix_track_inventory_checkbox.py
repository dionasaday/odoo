#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to fix Track Inventory checkbox for products in Odoo 19
This script will update products to ensure tracking='lot' is set correctly
"""

import logging

_logger = logging.getLogger(__name__)


def fix_track_inventory_checkbox(env, limit=None):
    """
    Fix Track Inventory checkbox for products by ensuring tracking='lot' is set
    
    Args:
        env: Odoo environment
        limit: Maximum number of products to update (None = all)
    
    Returns:
        dict with update statistics
    """
    _logger.warning('🔧 Starting fix for Track Inventory checkbox...')
    
    # Find products that:
    # 1. Have SKU (default_code) - likely synced from Zortout
    # 2. Type is 'consu' (Goods)
    # 3. Tracking is not 'lot' (need to fix)
    domain = [
        ('type', '=', 'consu'),  # Goods type
        ('default_code', '!=', False),  # Has SKU
        ('tracking', '!=', 'lot'),  # Not tracking='lot' yet
    ]
    
    products = env['product.template'].sudo().search(domain, limit=limit)
    total_count = len(products)
    
    _logger.warning(f'📦 Found {total_count} products to fix')
    
    if total_count == 0:
        _logger.warning('✅ All products already have tracking=\'lot\' set')
        return {
            'total_found': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
    
    # Update products to tracking='lot'
    updated_count = 0
    skipped_count = 0
    errors = []
    
    for idx, product in enumerate(products, 1):
        try:
            # Force update tracking to 'lot'
            # This should enable the Track Inventory checkbox
            product.write({'tracking': 'lot'})
            
            # Also ensure type is 'consu' (Goods)
            if product.type != 'consu':
                product.write({'type': 'consu'})
            
            updated_count += 1
            
            # Log progress every 100 products
            if updated_count % 100 == 0:
                _logger.warning(f'📊 Progress: {updated_count}/{total_count} products fixed')
                env.cr.commit()  # Commit periodically to avoid long transaction
            
        except Exception as e:
            skipped_count += 1
            error_msg = f"Product {product.default_code or product.name}: {str(e)}"
            errors.append(error_msg)
            _logger.error(error_msg, exc_info=True)
    
    # Final commit
    env.cr.commit()
    
    _logger.warning(f'✅ Fix completed: {updated_count} updated, {skipped_count} skipped')
    
    return {
        'total_found': total_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': errors[:50]  # Limit errors to first 50
    }


# For direct execution in Odoo shell
if __name__ == '__main__':
    # This will be executed when run in Odoo shell
    # Usage: python3 -c "exec(open('fix_track_inventory_checkbox.py').read())"
    pass

