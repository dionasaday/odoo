# -*- coding: utf-8 -*-
from datetime import date, datetime, time
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
import pytz
import logging
_logger = logging.getLogger(__name__)

AWARD_DEFAULT_CODE = "ATT_AWARD"

# =========================================================
# Company Config + Auto-provision payroll objects
# =========================================================
class ResCompany(models.Model):
    _inherit = 'res.company'

    attendance_award_amount = fields.Monetary(string="Attendance Award Amount", default=500.0)
    attendance_award_announce_dom = fields.Integer(string="Announce Day of Month", default=1)
    attendance_award_tie_policy = fields.Selection([
        ('all', 'Award all qualified'),
        ('single_best', 'Only the single best'),
    ], default='all')
    attendance_award_disqualify_leave_types = fields.Many2many(
        'hr.leave.type', string="Disqualifying Leave Types")
    attendance_award_create_payslip_input = fields.Boolean(string="Create Payslip Input")
    attendance_award_salary_rule_code = fields.Char(string="Salary Rule Code", default=AWARD_DEFAULT_CODE)

    def ensure_award_payroll_config(self):
        """Ensure Input Type + Salary Rule exist and rule is in all structures.
           Salary Rule style = เหมือน Overtime: inputs.CODE / inputs.CODE.amount
        """
        for company in self:
            if not company.attendance_award_create_payslip_input:
                continue

            code = company.attendance_award_salary_rule_code or AWARD_DEFAULT_CODE
            name = _("Attendance Award")

            # (optional) Input Type
            itype = False
            if 'hr.payslip.input.type' in self.env:
                InputType = self.env['hr.payslip.input.type'].with_company(company).sudo()
                itype = InputType.search([('code', '=', code)], limit=1)
                if not itype:
                    vals_it = {'name': name, 'code': code}
                    if 'company_id' in InputType._fields:
                        vals_it['company_id'] = company.id
                    itype = InputType.create(vals_it)

            # Salary Rule
            if 'hr.salary.rule' in self.env:
                Rule = self.env['hr.salary.rule'].with_company(company).sudo()
                Cat = self.env['hr.salary.rule.category'].with_company(company).sudo()
                cat = (Cat.search([('code', '=', 'ALW')], limit=1)
                       or Cat.search([('name', '=', 'Allowance')], limit=1)
                       or Cat.create({'name': 'Allowance', 'code': 'ALW'}))

                rule = Rule.search([('code', '=', code)], limit=1)
                cond_py = f"result = inputs.{code}"
                amt_py  = f"result = inputs.{code}.amount"

                if not rule:
                    vals = {
                        'name': name,
                        'code': code,
                        'category_id': cat.id,
                        'sequence': 2000,
                        'appears_on_payslip': True,
                    }
                    if 'condition_select' in Rule._fields:
                        vals['condition_select'] = 'python'
                    if 'condition_python' in Rule._fields:
                        vals['condition_python'] = cond_py
                    if 'amount_select' in Rule._fields:
                        vals['amount_select'] = 'code'
                    if 'amount_python_compute' in Rule._fields:
                        vals['amount_python_compute'] = amt_py
                    if 'company_id' in Rule._fields:
                        vals['company_id'] = company.id
                    rule = Rule.create(vals)
                else:
                    fix_vals = {'appears_on_payslip': True}
                    if 'condition_select' in Rule._fields:
                        fix_vals['condition_select'] = 'python'
                    if 'condition_python' in Rule._fields:
                        fix_vals['condition_python'] = cond_py
                    if 'amount_select' in Rule._fields:
                        fix_vals['amount_select'] = 'code'
                    if 'amount_python_compute' in Rule._fields:
                        fix_vals['amount_python_compute'] = amt_py
                    rule.write(fix_vals)

                # add rule into all structures
                if 'hr.payroll.structure' in self.env:
                    Struct = self.env['hr.payroll.structure'].with_company(company).sudo()
                    structures = Struct.search([('company_id', '=', company.id)]) or Struct.search([])
                    for s in structures:
                        if rule.id not in s.rule_ids.ids:
                            s.write({'rule_ids': [(4, rule.id)]})

            _logger.info("Award payroll config OK for %s (rule code=%s, itype_id=%s)",
                         company.display_name, code, getattr(itype, 'id', False))
        return True

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ['attendance_award_create_payslip_input', 'attendance_award_salary_rule_code']):
            self.filtered('attendance_award_create_payslip_input').ensure_award_payroll_config()
        return res


# =========================================================
# Attendance Award (Header)
# =========================================================
class HrAttendanceAward(models.Model):
    _name = 'hr.attendance.award'
    _description = 'Monthly Attendance Award'
    _order = 'date_from desc, company_id'

    company_id = fields.Many2one('res.company', required=True, default=lambda s: s.env.company)
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)
    amount = fields.Monetary(required=True)
    state = fields.Selection([('draft','Draft'),('announced','Announced')], default='draft')
    line_ids = fields.One2many('hr.attendance.award.line', 'award_id')

    _unique_period_company = models.UniqueIndex(
        "(company_id, date_from, date_to)",
        "Award for this company and period already exists.",
    )

    def action_recompute(self):
        for rec in self:
            rec.line_ids.unlink()
            rec._compute_lines()
        return True

    def action_mark_winners(self):
        for rec in self:
            rec._mark_winners()
        return True

    def action_send_announcement(self):
        for rec in self:
            rec._send_announce_mail()
        return True

    @api.model
    def _last_month_range(self):
        today = fields.Date.context_today(self)
        first_this = date(today.year, today.month, 1)
        last_prev = first_this - relativedelta(days=1)
        first_prev = date(last_prev.year, last_prev.month, 1)
        return first_prev, last_prev

    @api.model
    def cron_compute_and_announce(self):
        """Cron job: สร้างและประกาศผลรางวัล Attendance Award ประจำเดือน
        รันทุกวันและเช็คว่าเป็นวันที่ที่กำหนดไว้ใน company.attendance_award_announce_dom หรือไม่
        """
        today = fields.Date.context_today(self)
        _logger.info("Attendance Award Cron: Running on %s (day %d)", today, today.day)
        
        for company in self.env['res.company'].search([]):
            announce_dom = company.attendance_award_announce_dom or 1
            if announce_dom != today.day:
                _logger.debug(
                    "Attendance Award Cron: Skipping company %s (day %d != announce_dom %d)",
                    company.name, today.day, announce_dom
                )
                continue
            
            _logger.info(
                "Attendance Award Cron: Processing company %s (day %d matches announce_dom %d)",
                company.name, today.day, announce_dom
            )
            try:
                self._compute_and_announce_for_company(company)
                _logger.info("Attendance Award Cron: Successfully processed company %s", company.name)
            except Exception as e:
                _logger.error(
                    "Attendance Award Cron: Failed to process company %s: %s",
                    company.name, str(e), exc_info=True
                )

    @api.model
    def _compute_and_announce_for_company(self, company, date_from=None, date_to=None):
        if not (date_from and date_to):
            date_from, date_to = self._last_month_range()
        company.ensure_award_payroll_config()
        award = self.create({
            'company_id': company.id,
            'date_from': date_from,
            'date_to': date_to,
            'amount': company.attendance_award_amount or 500.0,
        })
        award._compute_lines()
        award._mark_winners()
        award._send_announce_mail()
        award.state = 'announced'
        return award

    # ----------------- compute participants -----------------
    def _compute_lines(self):
        self.ensure_one()
        Company = self.company_id
        tzname = (Company.partner_id.tz or self.env.user.tz or 'UTC')
        tz = pytz.timezone(tzname)

        Employee = self.env['hr.employee'].sudo()
        employees = Employee.search([('company_id','=',Company.id), ('active','=',True)])

        def to_local(dt_utc_naive):
            if not dt_utc_naive:
                return None
            return pytz.utc.localize(dt_utc_naive).astimezone(tz)

        def to_utc_naive(dt_local_aware):
            return dt_local_aware.astimezone(pytz.utc).replace(tzinfo=None)

        start_local = tz.localize(datetime.combine(self.date_from, time.min))
        end_local   = tz.localize(datetime.combine(self.date_to,   time.max))
        start_utc_naive = to_utc_naive(start_local)
        end_utc_naive   = to_utc_naive(end_local)

        disq_types = Company.attendance_award_disqualify_leave_types.ids
        vals = []
        for emp in employees:
            cal = emp.resource_calendar_id or Company.resource_calendar_id
            if not cal or not emp.resource_id:
                continue

            # eligibility
            start_date = None
            if 'first_contract_date' in emp._fields and emp.first_contract_date:
                start_date = emp.first_contract_date
            elif 'joining_date' in emp._fields and getattr(emp, 'joining_date', False):
                start_date = emp.joining_date
            elif emp.create_date:
                start_date = fields.Datetime.to_datetime(emp.create_date).date()
            end_employment = getattr(emp, 'departure_date', None) if 'departure_date' in emp._fields else None

            eligible_full_month = bool(
                start_date and start_date <= self.date_from and
                (not end_employment or end_employment >= self.date_to)
            )

            intervals_map = cal._work_intervals_batch(
                start_local, end_local, resources=emp.resource_id, tz=tz
            )
            emp_intervals = intervals_map.get(emp.resource_id.id, [])
            scheduled_dates = set()
            for iv in emp_intervals:
                iv_start = iv[0]
                if iv_start.tzinfo is None:
                    iv_start = pytz.utc.localize(iv_start)
                scheduled_dates.add(iv_start.astimezone(tz).date())
            scheduled_days = len(scheduled_dates)

            attendances = self.env['hr.attendance'].sudo().search([
                ('employee_id','=', emp.id),
                ('check_in','>=', start_utc_naive),
                ('check_in','<=', end_utc_naive),
            ])
            attendance_dates = set(to_local(a.check_in).date() for a in attendances if a.check_in)
            worked_days = len(scheduled_dates & attendance_dates)

            leave_domain = [
                ('employee_id','=', emp.id),
                ('state','=','validate'),
                ('request_date_from','<=', self.date_to),
                ('request_date_to','>=', self.date_from),
            ]
            if disq_types:
                leave_domain.append(('holiday_status_id','in', disq_types))
            leaves = self.env['hr.leave'].sudo().search(leave_domain)
            leave_days = int(sum(l.number_of_days for l in leaves))

            late_cnt = self.env['hr.lateness.log'].sudo().search_count([
                ('employee_id','=', emp.id),
                ('company_id','=', Company.id),
                ('date','>=', self.date_from),
                ('date','<=', self.date_to),
                ('minutes','>', 0),
            ])

            vals.append({
                'award_id': self.id,
                'employee_id': emp.id,
                'scheduled_days': scheduled_days,
                'worked_days': worked_days,
                'leave_days': leave_days,
                'lateness_count': late_cnt,
                'avg_on_time_delta_minutes': 0.0,   # ไม่ใช้คะแนนเวลาในรุ่นนี้
                'eligible_full_month': eligible_full_month,
            })
        if vals:
            self.env['hr.attendance.award.line'].create(vals)

    def _mark_winners(self):
        self.ensure_one()
        quals = self.line_ids.filtered(
            lambda l: l.eligible_full_month and l.lateness_count == 0
                      and l.leave_days == 0 and l.worked_days == l.scheduled_days
        )
        if self.company_id.attendance_award_tie_policy == 'single_best' and quals:
            quals = quals.sorted(lambda l: (l.avg_on_time_delta_minutes, -l.worked_days))[:1]
        quals.write({'is_winner': True})

    def _send_announce_mail(self):
        self.ensure_one()
        tpl = self.env.ref('onthisday_hr_discipline.mail_template_attendance_award_monthly', raise_if_not_found=False)
        if tpl:
            tpl.sudo().send_mail(self.id, force_send=True)


# =========================================================
# Payslip integration (for manual & automatic_payroll)
# =========================================================
# Note: hr.payslip model may not exist if hr_payroll_community is not installed
# We use _register = False to prevent registration if base model doesn't exist
# and check at runtime whether the model is available
def _apply_payslip_award(slip):
    """Helper function to apply attendance award to a payslip.
    Called from payslip's compute_sheet if hr.payslip exists."""
    company = slip.company_id or slip.employee_id.company_id
    if not (company and company.attendance_award_create_payslip_input and company.attendance_award_salary_rule_code):
        return

    code = company.attendance_award_salary_rule_code
    # หา award รอบเดียวกันกับสลิป
    award = slip.env['hr.attendance.award'].sudo().search([
        ('company_id', '=', company.id),
        ('date_from', '=', slip.date_from),
        ('date_to',   '=', slip.date_to),
    ], limit=1)
    if not award:
        return

    is_winner = award.line_ids.filtered(lambda l: l.employee_id.id == slip.employee_id.id and l.is_winner)
    if not is_winner:
        return

    company.ensure_award_payroll_config()
    Inputs = slip.env['hr.payslip.input'].with_company(company).sudo()

    # หา/สร้างบนสลิปนี้
    itype_id = False
    if 'hr.payslip.input.type' in slip.env and 'input_type_id' in Inputs._fields:
        itype = slip.env['hr.payslip.input.type'].sudo().search([('code', '=', code)], limit=1)
        itype_id = itype.id if itype else False

    dom = []
    if 'payslip_id' in Inputs._fields:
        dom.append(('payslip_id', '=', slip.id))
    elif 'contract_id' in Inputs._fields and slip.contract_id:
        dom.append(('contract_id', '=', slip.contract_id.id))
    elif 'employee_id' in Inputs._fields:
        dom.append(('employee_id', '=', slip.employee_id.id))

    if 'code' in Inputs._fields:
        dom.append(('code', '=', code))
    elif 'input_type_id' in Inputs._fields and itype_id:
        dom.append(('input_type_id', '=', itype_id))

    if 'company_id' in Inputs._fields:
        dom.append(('company_id', '=', company.id))

    input_rec = Inputs.search(dom, limit=1) if dom else False

    vals = {
        'name': _("Attendance Award %s-%s") % (award.date_from, award.date_to),
        'amount': award.amount,
    }
    if 'payslip_id' in Inputs._fields:
        vals['payslip_id'] = slip.id
    if 'contract_id' in Inputs._fields and slip.contract_id:
        vals['contract_id'] = slip.contract_id.id
    if 'employee_id' in Inputs._fields:
        vals['employee_id'] = slip.employee_id.id
    if 'code' in Inputs._fields:
        vals['code'] = code
    if 'input_type_id' in Inputs._fields and itype_id:
        vals['input_type_id'] = itype_id
    if 'company_id' in Inputs._fields:
        vals['company_id'] = company.id

    if input_rec:
        input_rec.write(vals)
    else:
        Inputs.create(vals)

# Only register this class if hr.payslip exists in registry
# We'll use a post-init hook or check in __init__.py to register it conditionally
# For now, comment it out to prevent errors when hr_payroll_community is not installed
# 
# If hr.payslip exists, you can uncomment this and register it:
# class HrPayslip(models.Model):
#     _inherit = 'hr.payslip'
#     
#     def _award_push_inputs(self):
#         for slip in self:
#             _apply_payslip_award(slip)
#     
#     def compute_sheet(self):
#         self._award_push_inputs()
#         return super().compute_sheet()


# =========================================================
# Lines
# =========================================================
class HrAttendanceAwardLine(models.Model):
    _name = 'hr.attendance.award.line'
    _description = 'Attendance Award Line'
    _order = 'is_winner desc, avg_on_time_delta_minutes asc'

    award_id = fields.Many2one('hr.attendance.award', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='award_id.company_id', store=True)
    employee_id = fields.Many2one('hr.employee', required=True)
    scheduled_days = fields.Integer()
    worked_days = fields.Integer()
    leave_days = fields.Integer()
    lateness_count = fields.Integer()
    avg_on_time_delta_minutes = fields.Float()
    eligible_full_month = fields.Boolean(default=False)
    is_winner = fields.Boolean(default=False)
