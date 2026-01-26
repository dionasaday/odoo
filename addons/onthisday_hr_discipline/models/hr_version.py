# models/hr_version.py
from odoo import models, fields


class HrVersion(models.Model):
    _inherit = "hr.version"

    date_version = fields.Date(
        required=True,
        default=fields.Date.today,
        tracking=True,
        groups="base.group_user,hr.group_hr_user,onthisday_hr_discipline.group_discipline_hr,onthisday_hr_discipline.group_discipline_manager",
    )

    identification_id = fields.Char(
        string='Identification No',
        help="Enter the employee's National Identification Number issued by the government (e.g., Aadhaar, SIN, NIN). This is used for official records and statutory compliance.",
        groups="base.group_user,hr.group_hr_user,onthisday_hr_discipline.group_discipline_hr,onthisday_hr_discipline.group_discipline_manager",
        tracking=True,
    )
