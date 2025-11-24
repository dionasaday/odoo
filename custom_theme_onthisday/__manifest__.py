# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Custom Theme - On This Day',
    'version': '19.0.2.0.0',
    'category': 'Theme/Custom',
    'summary': 'Custom Theme สำหรับบริษัท On This Day',
    'description': """
Custom Theme Module
===================
โมดูลสำหรับปรับแต่งสีธีมของ Odoo ให้ตรงกับ Corporate Identity (CI) 
ของบริษัท On This Day

คุณสมบัติ:
----------
* เปลี่ยนสี Primary Color (สีหลัก)
* เปลี่ยนสี Navigation Bar
* เปลี่ยนสี Buttons
* ปรับแต่งสี UI Elements ต่างๆ
* รองรับการกำหนดสีผ่าน SCSS Variables

การใช้งาน:
----------
วิธีที่ 1: ปรับแต่งสีผ่าน Settings (แนะนำ)
1. ติดตั้งโมดูล
2. ไปที่ Settings > General Settings > Theme Colors
3. แก้ไขสี Primary Color, Secondary Color, และ Text Color
4. คลิก Save
5. Refresh browser (Ctrl+Shift+R) เพื่อดูการเปลี่ยนแปลง

วิธีที่ 2: แก้ไขสีใน SCSS File
1. แก้ไขสีในไฟล์ static/src/scss/custom_theme.scss
2. Upgrade โมดูล: odoo-bin -u custom_theme_onthisday
3. Restart Odoo และ Clear Browser Cache

สำหรับ Production:
==================
1. ติดตั้งหรือ Upgrade โมดูล
2. รันคำสั่ง: odoo-bin -u custom_theme_onthisday -d <database_name> --stop-after-init
3. Restart Odoo service
4. Clear asset cache ใน browser (Ctrl+Shift+R)
5. ถ้ายังไม่เห็นการเปลี่ยนแปลง ให้ clear asset bundle cache:
   - ไปที่ Settings > Technical > Assets > Clear Assets Cache
   - หรือ restart Odoo อีกครั้ง
    """,
    'author': 'On This Day',
    'website': 'https://www.example.com',
    'license': 'LGPL-3',
    'depends': ['web', 'base', 'sale'],
    # Optional dependency - will work even if spreadsheet_dashboard is not installed
    # 'depends': ['web', 'base', 'sale', 'spreadsheet_dashboard'],
    'data': [
        'views/assets.xml',
        'views/res_company_views.xml',
        'views/sales_menu_override.xml',
        # 'views/res_config_settings_views.xml',  # Commented out - using company form instead
    ],
    'assets': {
        'web.assets_backend': [
            'custom_theme_onthisday/static/src/scss/custom_theme.scss',
            'custom_theme_onthisday/static/src/scss/search_facet_overrides.scss',
            'custom_theme_onthisday/static/src/js/rpc_error_handler.js',  # Load first to catch errors early
            'custom_theme_onthisday/static/src/js/theme_color.js',
            'custom_theme_onthisday/static/src/js/product_type_ui.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'sequence': 100,
}

