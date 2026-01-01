# onthisday_hr_discipline/models/lateness_rule.py
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class HrDisciplineLatenessRule(models.Model):
    _name = "hr.discipline.lateness.rule"
    _description = "Lateness to points mapping"
    _order = "min_minute asc"

    name = fields.Char(required=True, default=lambda self: _("Lateness Rule"))
    min_minute = fields.Integer(required=True, help="Inclusive lower bound (minutes)")
    max_minute = fields.Integer(required=True, help="Inclusive upper bound (minutes)")
    offense_xmlid = fields.Char(
        help="External ID (XML-ID) of hr.discipline.offense to use when the lateness falls in this band."
    )
    active = fields.Boolean(default=True)

    _check_range = models.Constraint(
        "CHECK(min_minute >= 0 AND max_minute >= min_minute)",
        "Invalid minute range.",
    )


class ResCompany(models.Model):
    _inherit = "res.company"

    hr_lateness_grace = fields.Integer(
        string="Grace Minutes (Late)",
        default=5,
        help="Minutes allowed before counting as late.",
    )
        # เกณฑ์ส่งอีเมลเตือนการมาสาย
    lateness_alert_min_minutes = fields.Integer(
        string="Alert when late over (min)",
        default=10,
        help="Only count lateness >= this number of minutes."
    )
    lateness_alert_every_n = fields.Integer(
        string="Alert every N occurrences",
        default=5,
        help="Send a warning email on every N-th qualifying lateness."
    )
