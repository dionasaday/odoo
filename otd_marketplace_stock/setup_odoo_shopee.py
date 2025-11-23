#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to setup Odoo for Shopee integration
Run this script in Odoo shell or via command line
"""

import sys
import os

# Instructions for running this script
print("""
╔══════════════════════════════════════════════════════════════╗
║     Odoo Shopee Integration Setup Script                    ║
╚══════════════════════════════════════════════════════════════╝

This script helps you configure Odoo for Shopee integration.

To run this script, use one of these methods:

Method 1: Via Odoo Shell
-------------------------
1. Go to Odoo: Settings > Technical > Database Structure > Odoo Shell
2. Copy and paste the code below
3. Replace YOUR_NGROK_URL with your actual ngrok URL

Method 2: Via Command Line
---------------------------
docker compose exec odoo python3 << 'EOF'
# Paste the code below
EOF

Method 3: Direct Python Execution
----------------------------------
python3 -c "exec(open('setup_odoo_shopee.py').read())"
""")

print("\n" + "="*60)
print("STEP 1: Set web.base.url")
print("="*60)
print("""
# Get or set web.base.url
env = self.env
param = env['ir.config_parameter'].sudo()
base_url = param.get_param('web.base.url', '')
print(f"Current web.base.url: {base_url}")

# Set new URL (replace with your ngrok URL)
new_url = 'https://43276ed5d1e3.ngrok-free.app'
if base_url != new_url:
    param.set_param('web.base.url', new_url)
    print(f"✅ Updated web.base.url to: {new_url}")
else:
    print(f"✅ web.base.url already set to: {new_url}")
""")

print("\n" + "="*60)
print("STEP 2: Create Marketplace Account")
print("="*60)
print("""
# Create Shopee Marketplace Account
env = self.env
account = env['marketplace.account'].create({
    'name': 'Shopee Thailand',
    'channel': 'shopee',
    'company_id': env.company.id,
    'client_id': 'YOUR_PARTNER_ID',  # Replace with your Partner ID
    'client_secret': 'YOUR_PARTNER_KEY',  # Replace with your Partner Key
    'sync_enabled': True,
})
print(f"✅ Created Marketplace Account: {account.name} (ID: {account.id})")
print(f"   Channel: {account.channel}")
print(f"   Client ID: {account.client_id}")
""")

print("\n" + "="*60)
print("STEP 3: Verify Configuration")
print("="*60)
print("""
# Verify all settings
env = self.env

# Check web.base.url
base_url = env['ir.config_parameter'].sudo().get_param('web.base.url', '')
print(f"📋 web.base.url: {base_url}")

# Check OAuth callback URL
callback_url = f"{base_url}/marketplace/oauth/callback/shopee"
print(f"📋 OAuth Callback URL: {callback_url}")

# Check accounts
accounts = env['marketplace.account'].search([('channel', '=', 'shopee')])
print(f"📋 Shopee Accounts: {len(accounts)}")
for acc in accounts:
    print(f"   - {acc.name} (ID: {acc.id})")
    print(f"     Client ID: {acc.client_id}")
    print(f"     Has Access Token: {'Yes' if acc.access_token else 'No'}")
""")

print("\n" + "="*60)
print("STEP 4: Test OAuth Connection")
print("="*60)
print("""
# Get account and test OAuth URL generation
env = self.env
account = env['marketplace.account'].search([('channel', '=', 'shopee')], limit=1)

if account:
    adapter = account._get_adapter()
    auth_url = adapter.get_authorize_url()
    print(f"✅ OAuth URL generated successfully!")
    print(f"📋 Authorization URL: {auth_url}")
    print(f"\\n🔗 Copy this URL and open in browser to authorize")
else:
    print("❌ No Shopee account found. Please create one first.")
""")

print("\n" + "="*60)
print("STEP 5: Create Shop (After OAuth)")
print("="*60)
print("""
# Create Shop after OAuth is complete
env = self.env
account = env['marketplace.account'].search([('channel', '=', 'shopee')], limit=1)

if account:
    shop = env['marketplace.shop'].create({
        'name': 'Shopee Shop 1',
        'account_id': account.id,
        'external_shop_id': 'YOUR_SHOP_ID',  # Replace with your Shop ID from Shopee
        'timezone': 'Asia/Bangkok',
    })
    print(f"✅ Created Shop: {shop.name} (ID: {shop.id})")
    print(f"   External Shop ID: {shop.external_shop_id}")
else:
    print("❌ No Shopee account found. Please create one first.")
""")

print("\n" + "="*60)
print("Manual Setup Instructions")
print("="*60)
print("""
If you prefer to set up manually through Odoo UI:

1. Set web.base.url:
   - Go to: Settings > Technical > Parameters > System Parameters
   - Search for: web.base.url
   - Update value to: https://43276ed5d1e3.ngrok-free.app

2. Create Marketplace Account:
   - Go to: Marketplace > Accounts
   - Click Create
   - Fill in:
     * Account Name: Shopee Thailand
     * Channel: Shopee
     * Client ID: Your Partner ID from Shopee
     * Client Secret: Your Partner Key from Shopee

3. Connect OAuth:
   - Open the Marketplace Account
   - Click "Connect OAuth" button
   - Authorize in Shopee
   - Verify access token is saved

4. Create Shop:
   - Go to: Marketplace > Shops
   - Click Create
   - Fill in:
     * Shop Name: Your shop name
     * Account: Select Shopee account
     * External Shop ID: Your Shop ID from Shopee
""")

