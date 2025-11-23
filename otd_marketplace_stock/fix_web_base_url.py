# -*- coding: utf-8 -*-
"""
Script to fix web.base.url in Odoo
Run this in Odoo Shell or via command line

Usage in Odoo Shell:
1. Go to Settings > Technical > Database Structure > Odoo Shell
2. Copy and paste the code below
"""

# Get or set web.base.url
env = self.env
param = env['ir.config_parameter'].sudo()

# Get current value
current_url = param.get_param('web.base.url', '')
print(f"Current web.base.url: {current_url}")

# Set new URL (ngrok URL)
new_url = 'https://43276ed5d1e3.ngrok-free.app'
if current_url != new_url:
    param.set_param('web.base.url', new_url)
    print(f"✅ Updated web.base.url to: {new_url}")
else:
    print(f"✅ web.base.url already set to: {new_url}")

# Verify
updated_url = param.get_param('web.base.url', '')
print(f"\nVerification:")
print(f"  web.base.url: {updated_url}")
print(f"  OAuth Callback URL: {updated_url}/marketplace/oauth/callback/shopee")

# Test Shopee account if exists
account = env['marketplace.account'].search([('channel', '=', 'shopee')], limit=1)
if account:
    adapter = account._get_adapter()
    auth_url = adapter.get_authorize_url()
    print(f"\n✅ Test OAuth URL:")
    print(f"  {auth_url}")
    
    # Check if using HTTPS
    if 'https://' in auth_url:
        print("  ✅ Using HTTPS")
    else:
        print("  ⚠️  Not using HTTPS - may cause issues")

