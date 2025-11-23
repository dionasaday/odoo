#!/bin/bash
# Check stock sync logs

echo "🔍 Checking stock sync logs..."
echo ""

echo "📊 Recent stock sync activity (last 2000 lines):"
docker compose logs --tail=2000 odoo 2>&1 | grep -E "(🚀|🔄|📦|✅|⚠️|📍|⏭️|📊|Starting.*stock|Syncing.*stock|Fetched.*products|Stock sync completed)" | tail -30
echo ""

echo "📋 All recent logs with WARNING/ERROR (last 5000 lines):"
docker compose logs --tail=5000 odoo 2>&1 | grep -E "(WARNING|ERROR)" | grep -i "zortout\|stock\|sync\|marketplace" | tail -20
echo ""

echo "⏰ Recent logs (last 2 minutes):"
docker compose logs --since 2m odoo 2>&1 | tail -30
echo ""

echo "✅ Done checking logs"


