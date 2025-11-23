#!/bin/bash
# Real-time monitor for image download activity (fixed - reads from log file)

echo "🔍 Monitoring image download activity in real-time..."
echo "Reading from: /var/log/odoo/odoo.log"
echo "Press Ctrl+C to stop"
echo ""

# Watch log file directly
docker compose exec -T odoo tail -f /var/log/odoo/odoo.log 2>&1 | grep --line-buffered -E "(📥|✅.*image|⚠️.*image|💾|🔄|🔍|📷|Downloading|Downloaded|images_|products_|Committed batch)" | while read line; do
    echo "[$(date '+%H:%M:%S')] $line"
done


