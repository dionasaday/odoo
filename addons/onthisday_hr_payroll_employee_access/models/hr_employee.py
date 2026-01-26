# -*- coding: utf-8 -*-
from odoo import fields, models


class HREmployee(models.Model):
    _inherit = "hr.employee"

    # Allow employees to read their own bank accounts for payslip printing
    bank_account_ids = fields.Many2many(
        'res.partner.bank',
        relation='employee_bank_account_rel',
        column1='employee_id',
        column2='bank_account_id',
        domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        groups="base.group_user,hr.group_hr_user",
        tracking=True,
        string='Bank Accounts',
        help='Employee bank accounts to pay salaries'
    )
