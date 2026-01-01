#!/bin/bash
# Script สำหรับ upgrade module onthisday_hr_discipline

cd /Users/nattaphonsupa/odoo-16

echo "Upgrading module: onthisday_hr_discipline"
echo "Database: nt"
echo ""

python3 odoo-bin -u onthisday_hr_discipline -d nt --stop-after-init

echo ""
echo "Upgrade completed!"
echo "Please restart Odoo server if it's not running in the background."

