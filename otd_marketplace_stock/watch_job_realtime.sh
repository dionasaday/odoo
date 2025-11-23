#!/bin/bash
# Script to watch marketplace job logs in real-time

echo "👀 Watching Marketplace Job Logs (Press Ctrl+C to stop)..."
echo ""

docker compose exec odoo tail -f /var/log/odoo/odoo.log 2>&1 | grep --line-buffered -E "(Import Products from Zortout|Sync Stock from Zortout|Sync Products from Zortout|Zortout.*Fetch|Syncing.*products|products_fetched|products_created|products_updated|stocks_updated|Job.*completed|Job.*failed|In Progress|Done|ERROR.*marketplace|Exception.*marketplace)"
