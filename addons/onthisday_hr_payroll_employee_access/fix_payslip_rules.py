#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Quick fix script to delete problematic security rules that block HR Managers
Run this script directly to fix the "Employee: Own Payslip Lines Only" issue

Usage:
    python3 fix_payslip_rules.py
    OR
    odoo-bin shell -d <database_name> < fix_payslip_rules.py
"""

import sys
import os

# Add Odoo to path if running standalone
if __name__ == '__main__':
    # Try to import odoo
    try:
        import odoo
        from odoo import api, SUPERUSER_ID
        
        # Get database name from environment or use default
        db_name = os.environ.get('DB_NAME', 'odoo')
        
        # Initialize Odoo
        odoo.tools.config.parse_config(['-d', db_name])
        registry = odoo.registry(db_name)
        
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            IrRule = env['ir.rule']
            
            # Find and delete the problematic rules
            rules_to_delete = IrRule.search([
                ('name', 'in', [
                    'Employee: Own Payslip Lines Only',
                    'Employee: Own Payslip Worked Days Only',
                    'Employee: Own Payslip Inputs Only'
                ])
            ])
            
            if rules_to_delete:
                print(f"Found {len(rules_to_delete)} rules to delete:")
                for rule in rules_to_delete:
                    print(f"  - {rule.name} (ID: {rule.id}, Model: {rule.model_id.model})")
                rules_to_delete.unlink()
                cr.commit()
                print("✅ Rules deleted successfully!")
                print("   Please refresh your browser and try 'Compute Sheet' again.")
            else:
                print("✅ No problematic rules found. The issue may already be fixed.")
                
    except ImportError:
        print("""
This script needs to be run within Odoo shell context.

Option 1: Run via Odoo shell:
    odoo-bin shell -d <database_name>
    >>> exec(open('addons/onthisday_hr_payroll_employee_access/fix_payslip_rules.py').read())

Option 2: Run SQL directly:
    DELETE FROM ir_rule 
    WHERE name IN (
        'Employee: Own Payslip Lines Only',
        'Employee: Own Payslip Worked Days Only',
        'Employee: Own Payslip Inputs Only'
    );

Option 3: Upgrade the module:
    Apps > Search "OnThisDay HR Payroll Employee Access" > Upgrade
        """)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
