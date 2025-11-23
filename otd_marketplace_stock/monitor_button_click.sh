#!/bin/bash
# Monitor button click and job execution

echo "🔍 Monitoring Button Click and Job Execution"
echo "============================================"
echo ""
echo "This script will monitor:"
echo "  - 🔘 Button click"
echo "  - ✅ Validation"
echo "  - 📝 Job creation"
echo "  - 💾 Transaction commit"
echo "  - 🚀 Cron trigger"
echo "  - ⏰ cron_run_jobs"
echo "  - 🔄 Job execution"
echo ""
echo "Press Ctrl+C to stop"
echo ""
echo "Starting monitor..."
echo ""

# Monitor logs in real-time
docker compose logs -f --tail=0 odoo 2>&1 | while IFS= read -r line; do
    # Check for relevant patterns
    if echo "$line" | grep -qE "(🔘|✅|❌|📝|💾|🚀|⏰|🔄|📋|🔍|Button clicked|action_sync_stock|cron_run_jobs|marketplace|zortout|WARNING.*otd|ERROR.*otd)"; then
        timestamp=$(date '+%H:%M:%S')
        echo "[$timestamp] $line"
    fi
done

