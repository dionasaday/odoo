#!/bin/bash
# Monitor marketplace job execution in real-time

echo "🔍 Monitoring marketplace job execution..."
echo "Press Ctrl+C to stop"
echo ""

# Watch logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | grep --line-buffered -E "(🎯|🚀|🔄|🔍|📷|📥|✅|⚠️|⏭️|Processing|Syncing|marketplace|zortout|WARNING.*otd)" || echo "No matching logs found"

