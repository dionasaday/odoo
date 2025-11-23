#!/bin/bash
# Script to check Odoo logs for Shopee OAuth debug messages

echo "🔍 Checking Odoo logs for Shopee OAuth debug messages..."
echo ""

# Check recent logs
echo "=== Recent Shopee OAuth Logs (last 200 lines) ==="
docker compose logs --tail=200 odoo 2>&1 | grep -i -E "(shopee.*oauth|oauth.*shopee|shopee.*debug|partner.*id|client.*secret|signature)" | tail -50

echo ""
echo "=== All Recent Logs (last 50 lines) ==="
docker compose logs --tail=50 odoo 2>&1

echo ""
echo "💡 To see real-time logs:"
echo "   docker compose logs -f odoo | grep -i shopee"
echo ""
echo "💡 To see all OAuth related logs:"
echo "   docker compose logs -f odoo | grep -i oauth"

