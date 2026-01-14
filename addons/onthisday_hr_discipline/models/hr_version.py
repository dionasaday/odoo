# models/hr_version.py
from odoo import models, fields


class HrVersion(models.Model):
    _inherit = "hr.version"

    date_version = fields.Date(
        required=True,
        default=fields.Date.today,
        tracking=True,
        groups="hr.group_hr_user,onthisday_hr_discipline.group_discipline_hr,onthisday_hr_discipline.group_discipline_manager",
    )
