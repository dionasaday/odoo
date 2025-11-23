#!/bin/bash
# Real-time OAuth log watcher

echo "🔍 Watching Odoo logs for Shopee OAuth debug messages..."
echo "📋 Instructions:"
echo "   1. Go to Odoo > Marketplace > Accounts > Shopee Thailand"
echo "   2. Click 'Connect OAuth' button"
echo "   3. Watch for debug messages below"
echo ""
echo "Waiting for OAuth request... (Press Ctrl+C to stop)"
echo "=========================================="
echo ""

docker compose logs -f odoo 2>&1 | grep --line-buffered -i -E "(shopee|oauth|debug|partner|signature|client|warning.*shopee|error.*shopee)" || true

