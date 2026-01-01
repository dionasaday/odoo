#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script to fix Case No. for cases that still have "/" as name
Run this from Odoo shell: python3 odoo-bin shell -d odoo19 < scripts/fix_case_numbers.py
Or via: docker exec -it odoo19 odoo-bin shell -d odoo19 < addons/onthisday_hr_discipline/scripts/fix_case_numbers.py
"""

import sys
import os

# This script is meant to be run in Odoo shell context
# In shell context, 'env' is already available

try:
    import logging
    _logger = logging.getLogger(__name__)
    
    # Find cases without Case No.
    Case = env['hr.discipline.case']
    cases_without_name = Case.search([
        '|', ('name', '=', '/'), ('name', '=', False)
    ])
    
    print(f"Found {len(cases_without_name)} cases without Case No.")
    
    if cases_without_name:
        # Group by company
        cases_by_company = {}
        for case in cases_without_name:
            company_id = case.company_id.id if case.company_id else False
            if company_id not in cases_by_company:
                cases_by_company[company_id] = []
            cases_by_company[company_id].append(case)
        
        # Process each company
        for company_id, cases in cases_by_company.items():
            print(f"\nProcessing {len(cases)} cases for company_id={company_id}")
            
            # Find or create sequence for this company
            sequence = env['ir.sequence'].search([
                ('code', '=', 'hr.discipline.case'),
                '|',
                ('company_id', '=', company_id),
                ('company_id', '=', False)
            ], limit=1)
            
            if not sequence:
                print(f"  Creating sequence for company_id={company_id}")
                sequence_vals = {
                    'name': 'Discipline Case',
                    'code': 'hr.discipline.case',
                    'prefix': 'DISC/%(year)s/',
                    'padding': 4,
                    'number_next': 1,
                    'number_increment': 1,
                }
                if company_id:
                    sequence_vals['company_id'] = company_id
                sequence = env['ir.sequence'].create(sequence_vals)
                env.cr.commit()
                print(f"  Created sequence ID={sequence.id}")
            
            # Update cases
            for case in cases:
                try:
                    new_name = env['ir.sequence'].with_company(company_id).next_by_code('hr.discipline.case') or "/"
                    if new_name != "/":
                        case.write({'name': new_name})
                        employee_name = case.employee_id.name if case.employee_id else 'N/A'
                        print(f"  ✅ Case ID={case.id} ({employee_name}): '{case.name}'")
                    else:
                        print(f"  ❌ Failed to generate Case No. for case ID={case.id}")
                except Exception as e:
                    print(f"  ❌ Error updating case ID={case.id}: {e}")
            
            env.cr.commit()
        
        print(f"\n✅ Completed! Updated {len(cases_without_name)} cases.")
    else:
        print("No cases found without Case No.")
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

