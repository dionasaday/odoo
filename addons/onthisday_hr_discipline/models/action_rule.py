# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from odoo.tools.translate import _

class DisciplineAction(models.Model):
    _name = "hr.discipline.action"
    _description = "Discipline Action Threshold"

    name = fields.Char(required=True)
    min_points = fields.Integer(required=True, default=1)
    max_points = fields.Integer(required=True, default=1)
    auto_reset = fields.Boolean(
        default=True,
        help="เมื่อลงโทษตามรายการนี้แล้ว จะตัดคะแนนสะสมของปีนั้นให้เป็น 0 โดยอัตโนมัติ",
    )
    send_punishment_email = fields.Boolean(
        string="ส่งอีเมลหลังสรุปบทลงโทษ",
        default=False,
        help="ถ้าเลือก ระบบจะส่งอีเมลแจ้งผลการบันทึกบทลงโทษให้พนักงานอัตโนมัติ",
    )
    note = fields.Text()

    @api.constrains('min_points', 'max_points')
    def _check_points_range(self):
        """Validate that min_points <= max_points"""
        for rec in self:
            if rec.min_points > rec.max_points:
                raise ValidationError(_("Min points (%s) must be less than or equal to Max points (%s)") % 
                                     (rec.min_points, rec.max_points))
            if rec.min_points < 0 or rec.max_points < 0:
                raise ValidationError(_("Points cannot be negative"))
