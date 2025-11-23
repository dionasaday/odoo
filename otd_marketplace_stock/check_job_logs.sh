#!/bin/bash
# Script to check marketplace job logs

echo "🔍 Checking Marketplace Job Logs..."
echo ""

# Check for job activity
echo "📋 Recent Job Activity:"
docker compose exec odoo tail -200 /var/log/odoo/odoo.log 2>&1 | grep -E "(Import Products from Zortout|Sync Stock from Zortout|Job.*completed|Job.*failed|In Progress|Done)" | tail -10

echo ""
echo "📦 Product Sync Activity:"
docker compose exec odoo tail -200 /var/log/odoo/odoo.log 2>&1 | grep -E "(Zortout.*Fetch|Syncing.*products|products_fetched|products_created|products_updated|images_downloaded)" | tail -10

echo ""
echo "📊 Stock Sync Activity:"
docker compose exec odoo tail -200 /var/log/odoo/odoo.log 2>&1 | grep -E "(Syncing stock|stocks_updated|products_synced|products_skipped)" | tail -10

echo ""
echo "❌ Errors (if any):"
docker compose exec odoo tail -200 /var/log/odoo/odoo.log 2>&1 | grep -E "(ERROR|Exception|Failed|Access Denied)" | tail -10
