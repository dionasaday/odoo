#!/bin/bash
# Script to fix Case No. for cases that still have "/" as name
# Usage: ./fix_case_numbers_manual.sh

echo "🔧 Fixing Case No. for cases with '/' name..."
echo ""

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "❌ Error: docker-compose or docker compose not found"
    exit 1
fi

# Run Python script in Odoo shell
echo "Running fix script in Odoo shell..."
$COMPOSE_CMD exec odoo odoo-bin shell -d odoo19 << 'EOF'
Case = env['hr.discipline.case']
cases = Case.search([('name', '=', '/')])
print(f"Found {len(cases)} cases without Case No.\n")

if cases:
    # Group by company
    cases_by_company = {}
    for case in cases:
        company_id = case.company_id.id if case.company_id else False
        if company_id not in cases_by_company:
            cases_by_company[company_id] = []
        cases_by_company[company_id].append(case)
    
    # Process each company
    for company_id, company_cases in cases_by_company.items():
        print(f"Processing {len(company_cases)} cases for company_id={company_id}")
        
        # Find or create sequence
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
            print(f"  ✅ Created sequence ID={sequence.id}")
        
        # Update cases
        for case in company_cases:
            try:
                new_name = env['ir.sequence'].with_company(company_id).next_by_code('hr.discipline.case') or "/"
                if new_name != "/":
                    case.write({'name': new_name})
                    employee_name = case.employee_id.name if case.employee_id else 'N/A'
                    print(f"  ✅ Case ID={case.id} ({employee_name}): '{new_name}'")
                else:
                    print(f"  ❌ Failed to generate Case No. for case ID={case.id}")
            except Exception as e:
                print(f"  ❌ Error updating case ID={case.id}: {e}")
        
        env.cr.commit()
    
    print(f"\n✅ Completed! Updated {len(cases)} cases.")
else:
    print("✅ No cases found without Case No.")
EOF

echo ""
echo "✅ Done! Please check the output above."

