#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to update menu name directly in database
Run this from Odoo shell or via: python3 odoo-bin shell -d odoo19 < scripts/update_menu_name.py
"""

import sys
import os

# Add Odoo path
sys.path.insert(0, '/usr/lib/python3/dist-packages')

try:
    from odoo import api, SUPERUSER_ID
    import odoo
    
    # Parse config
    odoo.tools.config.parse_config(['-c', '/etc/odoo/odoo.conf'])
    
    # Connect to database
    db = odoo.sql_db.db_connect('odoo19')
    cr = db.cursor()
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    # Find menu
    menu_data = env['ir.model.data'].search([
        ('module', '=', 'onthisday_hr_discipline'),
        ('name', '=', 'menu_hr_discipline_root'),
        ('model', '=', 'ir.ui.menu')
    ], limit=1)
    
    if menu_data:
        menu = env['ir.ui.menu'].browse(menu_data.res_id)
        print(f'Found menu: ID={menu.id}, Current name: {menu.name}')
        
        # Update menu name
        menu.write({'name': 'วินัยและมาตรฐานการทำงาน'})
        env.cr.commit()
        
        # Verify
        menu.refresh()
        print(f'Menu name updated successfully! New name: {menu.name}')
    else:
        print('Menu not found in ir.model.data')
    
    cr.close()
    
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

