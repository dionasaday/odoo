# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models


class HrEmployee(models.Model):
    """Inherit hr_employee for getting Payslip Counts and Attendance Counts"""
    _inherit = 'hr.employee'
    _description = 'Employee'

    slip_ids = fields.One2many('hr.payslip',
                               'employee_id', string='Payslips',
                               readonly=True,
                               help="Choose Payslip for Employee")
    payslip_count = fields.Integer(compute='_compute_payslip_count',
                                   string='Payslip Count',
                                   help="Set Payslip Count")
    attendance_count = fields.Integer(compute='_compute_attendance_count',
                                      string='Attendance Count',
                                      help="Number of attendance records")

    def _compute_payslip_count(self):
        """Function for count Payslips"""
        payslip_data = self.env['hr.payslip'].sudo().read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'], ['employee_id'])
        result = dict(
            (data['employee_id'][0], data['employee_id_count']) for data in
            payslip_data)
        for employee in self:
            employee.payslip_count = result.get(employee.id, 0)

    def _compute_attendance_count(self):
        """Compute the number of attendance records for each employee"""
        if 'hr.attendance' in self.env:
            attendance_data = self.env['hr.attendance'].sudo().read_group(
                [('employee_id', 'in', self.ids)],
                ['employee_id'], ['employee_id'])
            result = dict(
                (data['employee_id'][0], data['employee_id_count']) for data in
                attendance_data)
            for employee in self:
                employee.attendance_count = result.get(employee.id, 0)
        else:
            for employee in self:
                employee.attendance_count = 0

    def action_view_attendance(self):
        """Open attendance records for this employee"""
        self.ensure_one()
        action = {
            'name': 'Attendances',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'tree,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'search_default_employee_id': self.id,
            },
        }
        # Try to use the standard hr_attendance action if available
        try:
            action_id = self.env.ref('hr_attendance.action_hr_attendance_view_employee_attendance').id
            action['id'] = action_id
        except:
            pass
        return action
