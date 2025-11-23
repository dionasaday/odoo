#!/bin/bash
# Check if product is synced from Zortout

echo "🔍 Product Sync Checker"
echo "======================"
echo ""
echo "This script helps check:"
echo "  1. If product SKU matches between Odoo and Zortout"
echo "  2. If product was synced from Zortout"
echo "  3. If stock sync is working"
echo ""
echo "To use this script:"
echo "  1. Note the product's default_code (SKU) from Odoo"
echo "  2. Check if this SKU exists in Zortout"
echo "  3. Check logs for sync activity"
echo ""
echo "Common issues:"
echo "  - SKU mismatch: Odoo default_code ≠ Zortout SKU"
echo "  - Product not synced: Product exists in Zortout but not in Odoo"
echo "  - Stock not synced: Product exists but stock is 0"
echo ""
echo "Starting monitor for sync activity..."
echo ""

# Monitor logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | while IFS= read -r line; do
    # Check for relevant patterns
    if echo "$line" | grep -qE "(⏭️|Product with SKU|not found in Odoo|Fetched.*products|Stock sync|products_synced|stocks_updated|marketplace|zortout|WARNING.*otd|ERROR.*otd)"; then
        timestamp=$(date '+%H:%M:%S')
        echo "[$timestamp] $line"
    fi
done

