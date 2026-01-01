# -*- coding: utf-8 -*-
from odoo import models, fields, tools, _

class HrDisciplineMySummary(models.Model):
    _name = 'hr.discipline.my.summary'
    _description = 'สรุปคะแนนของฉัน (รายกรณีความผิด)'
    _auto = False
    _order = 'year desc, offense_name'

    employee_id = fields.Many2one('hr.employee', readonly=True)
    employee_user_id = fields.Many2one('res.users', readonly=True)
    offense_id = fields.Many2one('hr.discipline.offense', string='กรณีความผิด', readonly=True)
    offense_name = fields.Char(string='ชื่อกรณีความผิด', readonly=True)
    year = fields.Integer(string='ปี', readonly=True)
    total_points = fields.Integer(string='คะแนนรวม', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, 'hr_discipline_my_summary')
        self._cr.execute("""
            CREATE OR REPLACE VIEW hr_discipline_my_summary AS
            SELECT
                MIN(pl.id) AS id,
                pl.employee_id,
                e.user_id AS employee_user_id,
                dc.offense_id AS offense_id,
                o.name AS offense_name,
                EXTRACT(YEAR FROM pl.date)::int AS year,
                SUM(pl.points_change)::int AS total_points
            FROM hr_discipline_point_ledger pl
            LEFT JOIN hr_employee            e  ON e.id = pl.employee_id
            LEFT JOIN hr_discipline_case     dc ON dc.id = pl.case_id
            LEFT JOIN hr_discipline_offense  o  ON o.id = dc.offense_id
            WHERE
                COALESCE(dc.status, 'open') NOT IN ('resolved','done','cancel','cancelled','closed')
            GROUP BY
                pl.employee_id, e.user_id, dc.offense_id, o.name, EXTRACT(YEAR FROM pl.date)
            HAVING
                SUM(pl.points_change) <> 0
        """)

    def action_open_details(self):
        self.ensure_one()
        domain = [
            ('employee_id', '=', self.employee_id.id),
            ('offense_id', '=', self.offense_id.id),
            ('calendar_year', '=', self.year),
            ('status', 'not in', ['resolved', 'done', 'cancel', 'cancelled', 'closed']),
        ]
        Case = self.env['hr.discipline.case'].search(domain, order='date desc, id desc')
        tree_view = self.env.ref('onthisday_hr_discipline.view_case_tree', raise_if_not_found=False)
        form_view = self.env.ref('onthisday_hr_discipline.view_case_form', raise_if_not_found=False)
        views = []
        if tree_view:
            views.append((tree_view.id, 'list'))
        if form_view:
            views.append((form_view.id, 'form'))
        if len(Case) == 1:
            action = {
                'name': _('รายละเอียด'),
                'type': 'ir.actions.act_window',
                'res_model': 'hr.discipline.case',
                'view_mode': 'form',
                'res_id': Case.id,
                'target': 'current',
            }
            if form_view:
                action['view_id'] = form_view.id
            if views:
                action['views'] = views
            return action
        return {
            'name': _('รายละเอียด'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.discipline.case',
            'view_mode': 'list,form',
            'domain': domain,
            'context': {},
            'views': views or False,
        }
