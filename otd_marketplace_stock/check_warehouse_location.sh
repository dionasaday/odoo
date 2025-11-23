#!/bin/bash
# Check warehouse and location configuration

echo "🔍 Checking Warehouse and Location Configuration"
echo "================================================"
echo ""
echo "This script will help verify:"
echo "  1. If Stock Location 'WHNON/Stock' exists"
echo "  2. If it has a warehouse_id"
echo "  3. What warehouse_code will be used"
echo ""
echo "After clicking the button, check the logs below for:"
echo "  - 🔍 Checking stock_location_id"
echo "  - Location name and complete_name"
echo "  - Location warehouse_id"
echo "  - Warehouse name and code"
echo "  - Extracted warehouse_code"
echo ""
echo "Starting monitor..."
echo ""

# Monitor logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | while IFS= read -r line; do
    # Check for relevant patterns
    if echo "$line" | grep -qE "(🔍|Checking stock_location|Location name|Location complete_name|Location warehouse_id|Warehouse name|Warehouse code|Extracted warehouse_code|❌.*warehouse|❌.*location|marketplace|zortout|WARNING.*otd|ERROR.*otd)"; then
        timestamp=$(date '+%H:%M:%S')
        echo "[$timestamp] $line"
    fi
done

