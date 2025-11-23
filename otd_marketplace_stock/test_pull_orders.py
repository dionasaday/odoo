#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick test script to pull orders from Shopee
Run this in Odoo shell or via docker compose exec
"""

def test_pull_orders():
    """Test pulling orders from Shopee"""
    # Get Shopee account
    account = env['marketplace.account'].search([
        ('channel', '=', 'shopee'),
        ('active', '=', True),
    ], limit=1)
    
    if not account:
        print("❌ No Shopee account found")
        return
    
    print(f"✅ Found account: {account.name}")
    
    # Get shop
    shop = env['marketplace.shop'].search([
        ('account_id', '=', account.id),
        ('active', '=', True),
    ], limit=1)
    
    if not shop:
        print("❌ No active shop found")
        return
    
    print(f"✅ Found shop: {shop.name} (Shop ID: {shop.external_shop_id})")
    
    # Create job
    job = env['marketplace.job'].create({
        'name': f'Test Pull Orders - {shop.name}',
        'job_type': 'pull_order',
        'account_id': account.id,
        'shop_id': shop.id,
        'payload': {
            'since': '2024-11-01T00:00:00',
            'until': None,
        },
        'state': 'pending',
    })
    
    print(f"✅ Created job: {job.name} (ID: {job.id})")
    print(f"   Job Type: {job.job_type}")
    print(f"   State: {job.state}")
    
    # Process job immediately
    print("\n🔄 Processing job...")
    job.cron_run_jobs()
    
    # Refresh job
    job.refresh()
    
    print(f"\n📊 Job Status:")
    print(f"   State: {job.state}")
    print(f"   Retries: {job.retries}")
    if job.last_error:
        print(f"   Error: {job.last_error}")
    if job.result:
        print(f"   Result: {job.result[:200]}...")
    
    # Check orders
    orders = env['marketplace.order'].search([
        ('shop_id', '=', shop.id),
    ])
    
    print(f"\n📦 Orders found: {len(orders)}")
    for order in orders[:5]:  # Show first 5
        print(f"   - {order.name}: {order.state}")

if __name__ == '__main__':
    # This script should be run in Odoo shell
    print("""
    To use this script:
    1. docker compose exec odoo python3 -c "
       from odoo import api, SUPERUSER_ID
       from odoo.api import Environment
       
       db = 'odoo'
       with api.Environment.manage():
           env = api.Environment(odoo.registry(db), SUPERUSER_ID, {})
           exec(open('/mnt/extra-addons/otd_marketplace_stock/test_pull_orders.py').read())
    """)

