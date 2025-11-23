#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to enable Track Inventory for products synced from Zortout
Usage: Run this script in Odoo shell or as a scheduled action
"""

import logging

_logger = logging.getLogger(__name__)


def enable_track_inventory_for_zortout_products(env, limit=None):
    """
    Enable Track Inventory for products synced from Zortout
    
    Args:
        env: Odoo environment
        limit: Maximum number of products to update (None = all)
    
    Returns:
        dict with update statistics
    """
    _logger.warning('🚀 Starting bulk update to enable Track Inventory for Zortout products...')
    
    # Find products that:
    # 1. Have SKU (default_code) - likely synced from Zortout
    # 2. Type is 'consu' (Goods)
    # 3. Tracking is 'none' or not set (need to enable)
    domain = [
        ('type', '=', 'consu'),  # Goods type
        ('default_code', '!=', False),  # Has SKU
        ('tracking', 'in', ['none', False]),  # Not tracking yet
    ]
    
    products = env['product.template'].sudo().search(domain, limit=limit)
    total_count = len(products)
    
    _logger.warning(f'📦 Found {total_count} products to update')
    
    if total_count == 0:
        _logger.warning('⚠️ No products found to update')
        return {
            'total_found': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
    
    # Update products to enable tracking
    updated_count = 0
    skipped_count = 0
    errors = []
    
    for idx, product in enumerate(products, 1):
        try:
            # In Odoo 19, to enable "Track Inventory?" checkbox:
            # - tracking='none' → checkbox is UNCHECKED (no tracking)
            # - tracking='lot' → checkbox is CHECKED with "By Lots" option
            # 
            # Use tracking='lot' to enable the checkbox (it still tracks by quantity)
            product.write({'tracking': 'lot'})  # Enable Track Inventory checkbox
            updated_count += 1
            
            # Log progress every 100 products
            if updated_count % 100 == 0:
                _logger.warning(f'📊 Progress: {updated_count}/{total_count} products updated')
                env.cr.commit()  # Commit periodically to avoid long transaction
            
        except Exception as e:
            skipped_count += 1
            error_msg = f"Product {product.default_code or product.name}: {str(e)}"
            errors.append(error_msg)
            _logger.error(error_msg, exc_info=True)
    
    # Final commit
    env.cr.commit()
    
    _logger.warning(f'✅ Bulk update completed: {updated_count} updated, {skipped_count} skipped')
    
    return {
        'total_found': total_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': errors[:50]  # Limit errors to first 50
    }


# For direct execution in Odoo shell
if __name__ == '__main__':
    # This will be executed when run in Odoo shell
    # Usage: python3 -c "exec(open('enable_track_inventory.py').read())"
    pass

