#!/bin/bash
# Full debug monitor for Zortout API calls

echo "🔍 Full Debug Monitor for Zortout API"
echo "======================================"
echo ""
echo "This script will monitor:"
echo "  - 🔘 Button click"
echo "  - 🔧 Adapter creation"
echo "  - 📋 Payload and warehouse_code"
echo "  - 🌐 API Request (URL, Params, Headers)"
echo "  - 📥 API Response (Status, JSON)"
echo "  - ✅/❌ Success/Error messages"
echo ""
echo "Press Ctrl+C to stop"
echo ""
echo "Starting monitor..."
echo ""

# Monitor logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | while IFS= read -r line; do
    # Check for relevant patterns
    if echo "$line" | grep -qE "(🔘|🔧|📋|🔍|🔄|📄|📦|📥|✅|⚠️|📍|⏭️|📊|❌|🌐|Zortout|zortout|marketplace|stock|sync|warehouse|WHNON|API Request|API Response|Response Status|Response JSON|Button clicked|action_sync|cron_run_jobs|WARNING.*otd|ERROR.*otd)"; then
        timestamp=$(date '+%H:%M:%S')
        echo "[$timestamp] $line"
    fi
done

