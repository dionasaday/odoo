-- Script to delete security rules that block Payroll Officer/Manager from creating payslip lines
-- Run this SQL script to fix the "Employee: Own Payslip Lines Only" rule issue

-- Delete the problematic security rules
DELETE FROM ir_rule 
WHERE name IN (
    'Employee: Own Payslip Lines Only',
    'Employee: Own Payslip Worked Days Only',
    'Employee: Own Payslip Inputs Only'
);

-- Verify deletion
SELECT id, name, model_id, domain_force 
FROM ir_rule 
WHERE name IN (
    'Employee: Own Payslip Lines Only',
    'Employee: Own Payslip Worked Days Only',
    'Employee: Own Payslip Inputs Only'
);
