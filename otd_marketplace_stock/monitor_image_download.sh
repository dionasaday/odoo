#!/bin/bash
# Real-time monitor for image download activity

echo "🔍 Monitoring image download activity in real-time..."
echo "Press Ctrl+C to stop"
echo ""

# Watch logs in real-time with better filtering
docker compose logs -f --tail=0 odoo 2>&1 | grep --line-buffered -E "(📥|✅|⚠️|💾|🔄|🔍|📷|Syncing|Downloading|Downloaded|images_|products_)" | while read line; do
    echo "[$(date '+%H:%M:%S')] $line"
done

