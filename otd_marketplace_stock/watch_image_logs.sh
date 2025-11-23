#!/bin/bash
# Real-time log watcher for image downloading

echo "🔍 Watching Odoo logs for image download activity..."
echo "Press Ctrl+C to stop"
echo ""

docker compose logs -f --tail=0 odoo 2>&1 | grep --line-buffered -E "(📥|✅.*image|⚠️.*image|Downloading image|Downloaded.*image|Syncing.*product|products_fetched|products_created|products_updated|imagepath|imageList)"

