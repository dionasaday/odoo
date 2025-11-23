# -*- coding: utf-8 -*-
"""
Script to fix action contexts manually
Run this in Odoo shell: python3 -c "exec(open('/mnt/extra-addons/otd_marketplace_stock/fix_context.py').read())"
Or run via: odoo-bin shell -d <database> < /mnt/extra-addons/otd_marketplace_stock/fix_context.py
"""

# This will be executed when running in Odoo shell
env = self.env

# Find all marketplace actions with active_id in context
actions = env['ir.actions.act_window'].search([
    ('context', 'ilike', '%active_id%')
])

print(f'Found {len(actions)} actions with active_id in context:')

fixed_count = 0
for action in actions:
    print(f'\n  - {action.name} (ID: {action.id})')
    print(f'    Model: {action.res_model}')
    print(f'    Old context: {action.context}')
    
    # Clear context
    action.write({'context': None})
    fixed_count += 1
    print(f'    ✅ Context cleared')

print(f'\n\n✅ Fixed {fixed_count} actions')
print('Please refresh your browser and try again!')

