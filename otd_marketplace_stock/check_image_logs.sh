#!/bin/bash
# Script to check Odoo logs for image downloading activity

echo "🔍 Checking Odoo logs for image downloading activity..."
echo ""

# Check recent logs for image-related messages
echo "📥 Recent image download logs:"
docker compose logs --tail=5000 odoo 2>&1 | grep -E "(📥|✅.*image|⚠️.*image|Downloading image|Downloaded.*image|imagepath|imageList)" | tail -20

echo ""
echo "📊 Recent product sync logs:"
docker compose logs --tail=5000 odoo 2>&1 | grep -E "(Syncing.*product|products_fetched|products_created|products_updated)" | tail -10

echo ""
echo "🔄 Recent Zortout API calls:"
docker compose logs --tail=5000 odoo 2>&1 | grep -E "(Zortout Fetch Products|Zortout.*API)" | tail -10

echo ""
echo "✅ Done checking logs"

