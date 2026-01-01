# -*- coding: utf-8 -*-
from odoo import models, fields, api

class DisciplinePointLedger(models.Model):
    _name = "hr.discipline.point.ledger"
    _description = "Discipline Point Ledger"
    _order = "date desc, id desc"
    #_inherit = "hr.discipline.point.ledger"

    name = fields.Char(
        default=lambda self: self.env["ir.sequence"].next_by_code("hr.discipline.point.ledger") or "/",
        copy=False,
    )

    date = fields.Date(default=fields.Date.today, required=True)
    employee_id = fields.Many2one("hr.employee", required=True, index=True)
    points_change = fields.Integer(required=True)
    reason = fields.Char()
    case_id = fields.Many2one("hr.discipline.case", ondelete="set null")

    # หมวดความผิด (ไว้ group by/สรุป)
    category_id = fields.Many2one(
        "hr.discipline.offense.category",
        string="Category",
        related="case_id.offense_id.category_id",
        store=True,
    )

    # ปี (int) สำหรับ filter เร็ว ๆ
    year = fields.Integer(compute="_compute_year", store=True)

    @api.depends("date")
    def _compute_year(self):
        for rec in self:
            rec.year = (rec.date or fields.Date.today()).year
