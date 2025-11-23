#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to fix is_storable field for all Zortout products
This will set is_storable=True so that Track Inventory checkbox is visible
"""

import logging

_logger = logging.getLogger(__name__)


def fix_is_storable_all_products(env, limit=None):
    """
    Fix is_storable field for all Zortout products
    
    Args:
        env: Odoo environment
        limit: Maximum number of products to update (None = all)
    
    Returns:
        dict with update statistics
    """
    _logger.warning('🔧 Starting fix for is_storable field...')
    
    # Find all products with SKU (likely from Zortout) that are Goods type
    domain = [
        ('type', '=', 'consu'),  # Goods type
        ('default_code', '!=', False),  # Has SKU
    ]
    
    all_products = env['product.template'].sudo().search(domain, limit=limit)
    
    # Filter products that need fixing (is_storable=False OR tracking != 'lot')
    products = all_products.filtered(lambda p: not p.is_storable or p.tracking != 'lot')
    total_count = len(products)
    
    _logger.warning(f'📦 Found {total_count} products that need fixing')
    _logger.warning(f'   Total products: {len(all_products)}')
    _logger.warning(f'   Products with is_storable=False: {len(all_products.filtered(lambda p: not p.is_storable))}')
    _logger.warning(f'   Products with tracking != lot: {len(all_products.filtered(lambda p: p.tracking != "lot"))}')
    
    if total_count == 0:
        _logger.warning('✅ All products already have is_storable=True and tracking=lot')
        return {
            'total_found': len(all_products),
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
    
    # Update products
    updated_count = 0
    skipped_count = 0
    errors = []
    
    for idx, product in enumerate(products, 1):
        try:
            update_vals = {}
            
            # Set is_storable=True to show checkbox
            if not product.is_storable:
                update_vals['is_storable'] = True
            
            # Set tracking='lot' to enable checkbox
            if product.tracking != 'lot':
                update_vals['tracking'] = 'lot'
            
            if update_vals:
                product.write(update_vals)
                updated_count += 1
                
                # Log progress every 100 products
                if updated_count % 100 == 0:
                    _logger.warning(f'📊 Progress: {updated_count}/{total_count} products updated')
                    env.cr.commit()  # Commit periodically to avoid long transaction
            else:
                skipped_count += 1
            
        except Exception as e:
            skipped_count += 1
            error_msg = f"Product {product.default_code or product.name}: {str(e)}"
            errors.append(error_msg)
            _logger.error(error_msg, exc_info=True)
    
    # Final commit
    env.cr.commit()
    
    _logger.warning(f'✅ Fix completed: {updated_count} updated, {skipped_count} skipped')
    
    return {
        'total_found': len(all_products),
        'updated': updated_count,
        'skipped': skipped_count,
        'errors': errors[:50]  # Limit errors to first 50
    }


# For direct execution in Odoo shell
if __name__ == '__main__':
    # This will be executed when run in Odoo shell
    # Usage: python3 -c "exec(open('fix_is_storable_all_products.py').read())"
    pass

