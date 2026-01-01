#!/bin/bash
# Script to clear Python cache for onthisday_hr_discipline module

echo "Clearing Python cache for onthisday_hr_discipline..."

# Find and remove __pycache__ directories
find . -type d -name __pycache__ -exec rm -r {} + 2>/dev/null || true

# Find and remove .pyc files
find . -name "*.pyc" -delete

# Find and remove .pyo files
find . -name "*.pyo" -delete

echo "✅ Cache cleared!"
echo ""
echo "Next steps:"
echo "1. Restart Odoo: docker compose restart odoo"
echo "2. Update Apps List in Odoo UI"
echo "3. Try installing the module again"

