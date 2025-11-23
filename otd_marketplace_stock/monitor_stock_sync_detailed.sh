#!/bin/bash
# Detailed real-time monitor for stock sync

echo "🔍 Detailed Stock Sync Monitoring"
echo "=================================="
echo ""
echo "This script will monitor Odoo logs for stock sync activity"
echo "Press Ctrl+C to stop"
echo ""
echo "Looking for:"
echo "  - 🚀 Job start"
echo "  - 🔧 Adapter creation"
echo "  - 📋 Payload info"
echo "  - 🔍 Filters and params"
echo "  - 🔄 Syncing stock"
echo "  - 📄 Fetching pages"
echo "  - 📦 Fetched products"
echo "  - 📥 API Response"
echo "  - 📍 Warehouse info"
echo "  - ⏭️ Skipped products"
echo "  - ✅ Stock sync completed"
echo "  - ❌ Errors"
echo ""
echo "Starting monitor..."
echo ""

# Monitor logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | while IFS= read -r line; do
    # Check for relevant patterns
    if echo "$line" | grep -qE "(🚀|🔧|📋|🔍|🔄|📄|📦|📥|✅|⚠️|📍|⏭️|📊|❌|Starting.*stock|Syncing.*stock|Fetched.*products|Stock sync completed|marketplace|zortout|WARNING.*otd|ERROR.*otd)"; then
        timestamp=$(date '+%H:%M:%S')
        echo "[$timestamp] $line"
    fi
done

