#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to apply inventory adjustment for all products with inventory_quantity != 0
This will update quantity field from inventory_quantity
"""

import logging

_logger = logging.getLogger(__name__)


def apply_inventory_all_products(env, limit=None):
    """
    Apply inventory adjustment for all products with inventory_quantity != 0
    
    Args:
        env: Odoo environment
        limit: Maximum number of products to update (None = all)
    
    Returns:
        dict with update statistics
    """
    _logger.warning('🔧 Starting inventory adjustment for all products...')
    
    # Find all quants with inventory_quantity != 0
    domain = [
        ('inventory_quantity', '!=', 0),
    ]
    
    quants = env['stock.quant'].sudo().search(domain, limit=limit)
    total_count = len(quants)
    
    _logger.warning(f'📦 Found {total_count} quants with inventory_quantity != 0')
    
    if total_count == 0:
        _logger.warning('✅ No quants need inventory adjustment')
        return {
            'total_found': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
    
    # Apply inventory adjustment
    updated_count = 0
    skipped_count = 0
    errors = []
    
    for idx, quant in enumerate(quants, 1):
        try:
            # Apply inventory adjustment
            quant.action_apply_inventory()
            updated_count += 1
            
            # Commit every 100 products to avoid long transaction
            if updated_count % 100 == 0:
                env.cr.commit()
                _logger.warning(f'📊 Progress: {updated_count}/{total_count} quants updated')
            
        except Exception as e:
            skipped_count += 1
            error_msg = f"Quant {quant.product_id.default_code or quant.product_id.name} at {quant.location_id.complete_name}: {str(e)}"
            errors.append(error_msg)
            _logger.error(error_msg, exc_info=True)
    
    # Final commit
    env.cr.commit()
    
    _logger.warning(f'✅ Inventory adjustment completed: {updated_count} updated, {skipped_count} skipped')
    
    return {
        'total_found': total_count,
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': errors[:50]  # Limit errors to first 50
    }


# For direct execution in Odoo shell
if __name__ == '__main__':
    # This will be executed when run in Odoo shell
    # Usage: python3 -c "exec(open('apply_inventory_all_products.py').read())"
    pass

