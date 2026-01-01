# -*- coding: utf-8 -*-
"""
Patch module เพื่อแก้ไข error: Missing field string information 
สำหรับ field license_report_user_ids จากโมดูล onthisday_lot_license_v107 
ที่ถูก disable แล้วแต่ field ยังอยู่ใน database
"""
from odoo import models, fields


class ResCompany(models.Model):
    """เพิ่ม field ใน res.company เพื่อให้ related field ทำงานได้"""
    _inherit = "res.company"

    license_report_user_ids = fields.Many2many(
        "res.users",
        "res_company_license_report_user_rel",
        "company_id",
        "user_id",
        string="License Report Recipients",
        help="ผู้รับอีเมลสำหรับรายงาน License (เก็บไว้เพื่อป้องกัน error หลัง disable โมดูล)",
    )
    
    # เพิ่ม fields จากโมดูล om_fiscal_year ที่ถูก disable แล้ว
    fiscalyear_last_month = fields.Selection(
        [
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string="Fiscalyear Last Month",
        help="Last month of the fiscal year",
    )
    fiscalyear_last_day = fields.Integer(
        string="Fiscalyear Last Day",
        help="Last day of the fiscal year",
    )
    fiscalyear_lock_date = fields.Date(
        string="Fiscalyear Lock Date",
        help="Fiscal year lock date",
    )
    
    # เพิ่ม field จากโมดูล account/om_account_accountant
    anglo_saxon_accounting = fields.Boolean(
        string="Use anglo-saxon accounting",
        help="Use anglo-saxon accounting method",
    )


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    # เพิ่ม field กลับมาพร้อม string เพื่อแก้ error
    # Field นี้มาจากโมดูล onthisday_lot_license_v107 ที่ถูก disable แล้ว
    # ใช้ related เพื่อเชื่อมกับ company_id
    # สำหรับ Many2many related field ไม่ต้องระบุ relation/column1/column2
    # เพราะ Odoo จะใช้ metadata จาก base field (company_id.license_report_user_ids) อัตโนมัติ
    license_report_user_ids = fields.Many2many(
        comodel_name="res.users",
        string="License Report Recipients",
        help="ผู้รับอีเมลสำหรับรายงาน License (เก็บไว้เพื่อป้องกัน error หลัง disable โมดูล)",
        related="company_id.license_report_user_ids",
        readonly=False,
    )

    # เพิ่ม fields จากโมดูล knowsystem ที่ถูก skip แล้ว
    # เพื่อแก้ error "Missing field string information"
    module_knowsystem_website = fields.Boolean(
        string="Publish to portal and website",
        help="Publish KnowSystem articles to portal and website",
    )

    # เพิ่ม fields จากโมดูล helpdesk_mgmt ที่ถูก skip แล้ว
    # เพื่อแก้ error "Missing field string information"
    helpdesk_mgmt_portal_select_team = fields.Boolean(
        string="Select team in Helpdesk portal",
        help="Allow selecting team in Helpdesk portal",
    )
    helpdesk_mgmt_portal_team_id_required = fields.Boolean(
        string="Team Required in Portal",
        help="Require team selection in Helpdesk portal",
    )
    helpdesk_mgmt_portal_category_id_required = fields.Boolean(
        string="Category Required in Portal",
        help="Require category selection in Helpdesk portal",
    )

    # เพิ่ม fields จากโมดูล om_fiscal_year ที่ถูก disable แล้ว
    # เพื่อแก้ error "Missing field string information"
    fiscalyear_last_month = fields.Selection(
        [
            ('1', 'January'),
            ('2', 'February'),
            ('3', 'March'),
            ('4', 'April'),
            ('5', 'May'),
            ('6', 'June'),
            ('7', 'July'),
            ('8', 'August'),
            ('9', 'September'),
            ('10', 'October'),
            ('11', 'November'),
            ('12', 'December'),
        ],
        string="Fiscalyear Last Month",
        related="company_id.fiscalyear_last_month",
        readonly=False,
        help="Last month of the fiscal year",
    )
    fiscalyear_last_day = fields.Integer(
        string="Fiscalyear Last Day",
        related="company_id.fiscalyear_last_day",
        readonly=False,
        help="Last day of the fiscal year",
    )
    fiscalyear_lock_date = fields.Date(
        string="Fiscalyear Lock Date",
        related="company_id.fiscalyear_lock_date",
        readonly=False,
        help="Fiscal year lock date",
    )

    # เพิ่ม fields จากโมดูล account/om_account_accountant ที่ถูก skip แล้ว
    # เพื่อแก้ error "Missing field string information"
    anglo_saxon_accounting = fields.Boolean(
        string="Use anglo-saxon accounting",
        related="company_id.anglo_saxon_accounting",
        readonly=False,
        help="Use anglo-saxon accounting method",
    )

    # เพิ่ม fields จากโมดูล payroll localization ที่ถูก skip แล้ว
    # เพื่อแก้ error "Missing field string information"
    module_l10n_fr_hr_payroll = fields.Boolean(
        string="French Payroll",
        help="Enable French Payroll module",
    )
    module_l10n_be_hr_payroll = fields.Boolean(
        string="Belgian Payroll",
        help="Enable Belgian Payroll module",
    )
    module_l10n_in_hr_payroll = fields.Boolean(
        string="Indian Payroll",
        help="Enable Indian Payroll module",
    )
    module_l10n_eu_oss = fields.Boolean(
        string="EU OSS",
        help="Enable EU One Stop Shop module",
    )

