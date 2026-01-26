# -*- coding: utf-8 -*-
"""
Script to delete security rules that block Payroll Officer/Manager from creating payslip lines
Run this script to fix the "Employee: Own Payslip Lines Only" rule issue
"""
import sys
import os

# Add Odoo to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

def delete_payslip_line_rules():
    """Delete security rules that block Payroll Officer/Manager"""
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
                    print(f"  - {rule.name} (ID: {rule.id})")
                rules_to_delete.unlink()
                cr.commit()
                print("✅ Rules deleted successfully!")
            else:
                print("✅ No rules found to delete")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    delete_payslip_line_rules()
