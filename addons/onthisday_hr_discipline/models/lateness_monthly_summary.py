# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrLatenessMonthlySummary(models.Model):
    _name = "hr.lateness.monthly_summary"
    _description = "Monthly Lateness Summary"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "period_date desc, company_id"
    _rec_name = "period_display"

    # Core fields
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
        tracking=True,
    )
    period_date = fields.Date(
        required=True,
        string="Period (Month/Year)",
        help="เดือน/ปีของสรุป (ใช้วันที่ 1 ของเดือนนั้น)",
        index=True,
    )
    period_display = fields.Char(
        compute="_compute_period_display",
        store=True,
        string="Period",
    )
    date_from = fields.Date(required=True, string="From Date")
    date_to = fields.Date(required=True, string="To Date")

    # Summary statistics
    total_employees = fields.Integer(
        string="Total Employees",
        compute="_compute_summary_stats",
        store=True,
        help="จำนวนพนักงานทั้งหมดในเดือนนี้",
    )
    employees_with_lateness = fields.Integer(
        string="Employees with Lateness",
        compute="_compute_summary_stats",
        store=True,
        help="จำนวนพนักงานที่มีการมาสาย",
    )
    total_lateness_count = fields.Integer(
        string="Total Lateness Count",
        compute="_compute_summary_stats",
        store=True,
        help="จำนวนครั้งของการมาสายรวม",
    )
    total_lateness_minutes = fields.Integer(
        string="Total Lateness Minutes",
        compute="_compute_summary_stats",
        store=True,
        help="จำนวนนาทีรวมของการมาสาย",
    )
    avg_lateness_per_employee = fields.Float(
        string="Avg Lateness per Employee",
        compute="_compute_summary_stats",
        store=True,
        digits=(16, 2),
        help="ค่าเฉลี่ยการมาสายต่อพนักงาน",
    )

    # Line items (รายละเอียดตามพนักงาน)
    line_ids = fields.One2many(
        "hr.lateness.monthly_summary.line",
        "summary_id",
        string="Employee Details",
    )

    # Status
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("sent", "Email Sent"),
        ],
        default="draft",
        tracking=True,
        string="Status",
    )
    email_sent_date = fields.Datetime(
        string="Email Sent Date",
        readonly=True,
    )
    email_sent_to = fields.Char(
        string="Email Sent To",
        readonly=True,
    )

    # SQL constraint: ห้ามสร้างสรุปซ้ำสำหรับบริษัท/เดือนเดียวกัน
    _unique_company_period = models.UniqueIndex(
        "(company_id, period_date)",
        "Monthly summary for this company and period already exists!",
    )

    @api.depends("period_date")
    def _compute_period_display(self):
        """แสดงเป็น "เดือน ปี" เช่น "มกราคม 2025" """
        month_names = [
            "",
            "มกราคม",
            "กุมภาพันธ์",
            "มีนาคม",
            "เมษายน",
            "พฤษภาคม",
            "มิถุนายน",
            "กรกฎาคม",
            "สิงหาคม",
            "กันยายน",
            "ตุลาคม",
            "พฤศจิกายน",
            "ธันวาคม",
        ]
        for rec in self:
            if rec.period_date:
                month_num = rec.period_date.month
                year = rec.period_date.year
                rec.period_display = f"{month_names[month_num]} {year}"
            else:
                rec.period_display = False

    @api.depends("line_ids", "date_from", "date_to", "company_id")
    def _compute_summary_stats(self):
        """คำนวณสถิติจาก line_ids"""
        for rec in self:
            if not rec.line_ids:
                rec.total_employees = 0
                rec.employees_with_lateness = 0
                rec.total_lateness_count = 0
                rec.total_lateness_minutes = 0
                rec.avg_lateness_per_employee = 0.0
                continue

            rec.total_employees = len(rec.line_ids)
            rec.employees_with_lateness = len(
                rec.line_ids.filtered(lambda l: l.lateness_count > 0)
            )
            rec.total_lateness_count = sum(rec.line_ids.mapped("lateness_count"))
            rec.total_lateness_minutes = sum(
                rec.line_ids.mapped("lateness_minutes")
            )
            if rec.total_employees > 0:
                rec.avg_lateness_per_employee = (
                    rec.total_lateness_count / rec.total_employees
                )
            else:
                rec.avg_lateness_per_employee = 0.0

    # -------------------------------------------------------------------------
    # Business Logic
    # -------------------------------------------------------------------------
    def _generate_lines_from_logs(self):
        """สร้าง line_ids จาก hr.lateness.log"""
        self.ensure_one()
        Log = self.env["hr.lateness.log"].sudo()

        # ลบ line เดิม
        self.sudo().line_ids.unlink()

        # หา min_minutes ตาม company setting
        min_minutes = (
            self.company_id.lateness_alert_min_minutes
            or self.company_id.hr_lateness_grace
            or 0
        )

        # อ่าน logs ในช่วงนี้
        domain = [
            ("company_id", "=", self.company_id.id),
            ("date", ">=", self.date_from),
            ("date", "<=", self.date_to),
            ("minutes", ">=", min_minutes),
        ]

        # Group by employee
        results = Log.read_group(
            domain=domain,
            fields=["employee_id", "minutes:sum", "id:count"],
            groupby=["employee_id"],
        )

        # สร้าง lines
        Line = self.env["hr.lateness.monthly_summary.line"].sudo()
        for result in results:
            emp_id = result["employee_id"][0] if result["employee_id"] else False
            if not emp_id:
                continue

            emp = self.env["hr.employee"].browse(emp_id)
            Line.create(
                {
                    "summary_id": self.id,
                    "employee_id": emp_id,
                    "department_id": emp.department_id.id if emp.department_id else False,
                    "job_id": emp.job_id.id if emp.job_id else False,
                    "lateness_count": int(result.get("id_count") or 0),
                    "lateness_minutes": int(result.get("minutes_sum") or 0),
                }
            )

    @api.model
    def _get_monthly_summary_data(self, company=None, date_from=None, date_to=None):
        """
        ดึงข้อมูลสรุปรายเดือนแบบ real-time จาก lateness logs (ไม่ต้องสร้าง record)
        Returns: dict with summary statistics
        """
        if not company:
            company = self.env.company
        
        # คำนวณช่วงเวลา
        if not (date_from and date_to):
            today = fields.Date.context_today(self)
            first_this_month = date(today.year, today.month, 1)
            date_to = first_this_month - relativedelta(days=1)
            date_from = date_to.replace(day=1)
        
        # ดึงข้อมูลจาก lateness logs โดยตรง
        Log = self.env["hr.lateness.log"].sudo()
        domain = [
            ("company_id", "=", company.id),
            ("date", ">=", date_from),
            ("date", "<=", date_to),
        ]
        
        # Group by employee เพื่อคำนวณสถิติ
        results = Log.read_group(
            domain=domain,
            fields=["employee_id", "minutes:sum", "id:count"],
            groupby=["employee_id"],
        )
        
        # คำนวณสถิติ
        total_employees = len(results)
        employees_with_lateness = len([r for r in results if r.get("id_count", 0) > 0])
        total_lateness_count = sum([r.get("id_count", 0) for r in results])
        total_lateness_minutes = sum([int(r.get("minutes_sum", 0)) for r in results])
        avg_lateness_per_employee = (
            total_lateness_count / total_employees if total_employees > 0 else 0.0
        )
        
        # สร้าง period_display
        period_date = date_from.replace(day=1)
        month_names = [
            "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
            "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
        ]
        period_display = f"{month_names[period_date.month]} {period_date.year}"
        
        return {
            "period_date": period_date,
            "period_display": period_display,
            "date_from": date_from,
            "date_to": date_to,
            "company_id": company.id,
            "company_name": company.name,
            "total_employees": total_employees,
            "employees_with_lateness": employees_with_lateness,
            "total_lateness_count": total_lateness_count,
            "total_lateness_minutes": total_lateness_minutes,
            "avg_lateness_per_employee": round(avg_lateness_per_employee, 2),
            "line_data": results,  # ข้อมูลรายละเอียดตามพนักงาน
        }

    @api.model
    def _create_monthly_summary(self, company, date_from=None, date_to=None):
        """
        สร้างสรุปรายเดือนสำหรับบริษัท
        - date_from/date_to: ถ้าไม่ส่งมา จะใช้เดือนที่แล้ว
        """
        # คำนวณช่วงเวลา
        if not (date_from and date_to):
            today = fields.Date.context_today(self)
            first_this_month = date(today.year, today.month, 1)
            date_to = first_this_month - relativedelta(days=1)
            date_from = date_to.replace(day=1)
            period_date = date_from
        else:
            period_date = date_from.replace(day=1)

        # ตรวจสอบว่ามีสรุปแล้วหรือยัง
        existing = self.search(
            [
                ("company_id", "=", company.id),
                ("period_date", "=", period_date),
            ],
            limit=1,
        )
        if existing:
            _logger.info(
                "Monthly summary already exists for company %s, period %s",
                company.name,
                period_date,
            )
            return existing

        # สร้างสรุป
        summary = self.create(
            {
                "company_id": company.id,
                "period_date": period_date,
                "date_from": date_from,
                "date_to": date_to,
                "state": "draft",
            }
        )

        # สร้าง lines
        summary._generate_lines_from_logs()

        return summary

    @api.model
    def _get_or_refresh_current_month_summary(self, company=None):
        """สร้าง/รีเฟรชสรุปของเดือนปัจจุบันสำหรับมุมมองผู้จัดการ"""
        if not company:
            company = self.env.company

        today = fields.Date.context_today(self)
        date_from = date(today.year, today.month, 1)
        date_to = today
        period_date = date_from

        summary = self.search(
            [
                ("company_id", "=", company.id),
                ("period_date", "=", period_date),
            ],
            limit=1,
        )
        if summary:
            summary.sudo().write(
                {"date_from": date_from, "date_to": date_to, "state": summary.state}
            )
            summary.sudo()._generate_lines_from_logs()
            return summary

        summary = self.sudo().create(
            {
                "company_id": company.id,
                "period_date": period_date,
                "date_from": date_from,
                "date_to": date_to,
                "state": "draft",
            }
        )
        summary.sudo()._generate_lines_from_logs()
        return summary

    @api.model
    def action_open_monthly_summary(self):
        """Routing action: HR = pivot/graph, Manager = team list view."""
        user = self.env.user
        if user.has_group("onthisday_hr_discipline.group_discipline_hr"):
            return self._action_open_monthly_summary_hr()
        if user.has_group("onthisday_hr_discipline.group_discipline_manager"):
            return self._action_open_monthly_summary_manager()
        raise UserError(_("You do not have access to this report."))

    def _action_open_monthly_summary_hr(self):
        """Open HR pivot/graph for lateness logs."""
        action = self.env.ref(
            "onthisday_hr_discipline.action_hr_lateness_monthly_summary"
        ).read()[0]
        return action

    def _action_open_monthly_summary_manager(self):
        """Open manager list view (one row per subordinate)."""
        summary = self._get_or_refresh_current_month_summary()
        action = self.env.ref(
            "onthisday_hr_discipline.action_lateness_monthly_summary_manager_lines"
        ).read()[0]
        action.update(
            {
                "name": _("สรุปการมาสายรายเดือน (ทีมของฉัน)"),
                "domain": [("summary_id", "=", summary.id)],
                "context": {"default_summary_id": summary.id},
            }
        )
        return action

    def action_confirm(self):
        """ปุ่ม Confirm: เปลี่ยนสถานะเป็น confirmed"""
        self.write({"state": "confirmed"})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Confirmed"),
                "message": _("Monthly summary has been confirmed."),
                "sticky": False,
            },
        }

    def action_send_email(self):
        """ส่งอีเมลแจ้งหัวหน้า HR"""
        self.ensure_one()
        EmailLog = self.env["hr.discipline.email.log"]
        template = self.env.ref(
            "onthisday_hr_discipline.mail_template_lateness_monthly_summary",
            raise_if_not_found=False,
        )

        if not template:
            raise UserError(_("Email template not found!"))

        # หา email ของหัวหน้า HR หรือผู้ดูแลระบบ
        hr_managers = self.env["hr.employee"].sudo().search(
            [
                ("company_id", "=", self.company_id.id),
                ("job_id.name", "ilike", "HR"),
            ],
            limit=5,
        )

        emails = []
        for mgr in hr_managers:
            addr = getattr(mgr, "address_home_id", False) or getattr(mgr, "address_id", False)
            email = (
                mgr.work_email
                or (mgr.user_id and mgr.user_id.email)
                or (addr and addr.email)
            )
            if email:
                emails.append(email)

        # ถ้าไม่มี HR manager ให้ส่งไปที่ email ของ company
        if not emails:
            company_email = (
                self.company_id.email
                or self.company_id.partner_id.email
                or False
            )
            if company_email:
                emails.append(company_email)

        if not emails:
            raise UserError(_("No HR manager email found for company %s") % self.company_id.name)

        # ส่งอีเมล
        try:
            email_values = EmailLog._prepare_email_values(emails)
            template.sudo().send_mail(
                self.id,
                force_send=True,
                email_values=email_values,
            )
            self.write(
                {
                    "state": "sent",
                    "email_sent_date": fields.Datetime.now(),
                    "email_sent_to": email_values.get("email_to"),
                }
            )
            self.message_post(
                body=_("Email sent to: %s") % (email_values.get("email_to") or "")
            )
            EmailLog._log_email(
                "hr.lateness.monthly_summary",
                self.id,
                template,
                email_values.get("email_to"),
                email_values.get("email_cc"),
            )
        except Exception as e:
            _logger.error("Failed to send email: %s", str(e))
            EmailLog._log_email(
                "hr.lateness.monthly_summary",
                self.id,
                template,
                ",".join(emails),
                False,
                state="failed",
                error_message=str(e),
            )
            raise UserError(_("Failed to send email: %s") % str(e))

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Email Sent"),
                "message": _("Monthly summary email has been sent to HR managers."),
                "sticky": False,
            },
        }

    def action_view_lines(self):
        """เปิดดูรายละเอียดตามพนักงาน"""
        self.ensure_one()
        return {
            "name": _("Employee Lateness Details"),
            "type": "ir.actions.act_window",
            "res_model": "hr.lateness.monthly_summary.line",
            "view_mode": "tree,form",
            "domain": [("summary_id", "=", self.id)],
            "context": {"default_summary_id": self.id},
        }

    # -------------------------------------------------------------------------
    # Cron Entry
    # -------------------------------------------------------------------------
    @api.model
    def action_create_current_month_summary(self):
        """Action สำหรับสร้างสรุปเดือนปัจจุบัน (เรียกจาก server action หรือ button)"""
        company = self.env.company
        today = fields.Date.context_today(self)
        
        # สร้างสรุปสำหรับเดือนปัจจุบัน
        first_this_month = date(today.year, today.month, 1)
        date_from = first_this_month
        date_to = today  # ใช้วันปัจจุบันเป็น date_to
        
        try:
            summary = self._create_monthly_summary(company, date_from=date_from, date_to=date_to)
            if summary:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Monthly summary created for %s") % summary.period_display,
                        "type": "success",
                        "sticky": False,
                    },
                }
        except Exception as e:
            _logger.error("Failed to create monthly summary: %s", str(e))
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error"),
                    "message": _("Failed to create monthly summary: %s") % str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }
    
    @api.model
    def action_create_last_month_summary(self):
        """Action สำหรับสร้างสรุปเดือนที่แล้ว (เรียกจาก server action หรือ button)"""
        company = self.env.company
        
        try:
            summary = self._create_monthly_summary(company)  # ไม่ส่ง date_from/date_to = ใช้เดือนที่แล้ว
            if summary:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Success"),
                        "message": _("Monthly summary created for %s") % summary.period_display,
                        "type": "success",
                        "sticky": False,
                    },
                }
        except Exception as e:
            _logger.error("Failed to create monthly summary: %s", str(e))
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error"),
                    "message": _("Failed to create monthly summary: %s") % str(e),
                    "type": "danger",
                    "sticky": True,
                },
            }

    @api.model
    def _cron_create_monthly_summaries(self):
        """Entry point สำหรับ cron: สร้างสรุปรายเดือนสำหรับทุกบริษัท"""
        today = fields.Date.context_today(self)
        # รันต้นเดือน -> สร้างสรุปเดือนที่แล้ว
        if today.day != 1:
            return

        companies = self.env["res.company"].search([])
        for company in companies:
            try:
                summary = self._create_monthly_summary(company)
                if summary and summary.line_ids:
                    # Auto-confirm และส่งอีเมล
                    summary.action_confirm()
                    summary.action_send_email()
            except Exception as e:
                _logger.error(
                    "Failed to create monthly summary for company %s: %s",
                    company.name,
                    str(e),
                )


class HrLatenessMonthlySummaryLine(models.Model):
    _name = "hr.lateness.monthly_summary.line"
    _description = "Monthly Lateness Summary Line (per Employee)"
    _order = "lateness_count desc, lateness_minutes desc"

    summary_id = fields.Many2one(
        "hr.lateness.monthly_summary",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="summary_id.company_id",
        store=True,
        readonly=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        required=True,
        string="Employee",
    )
    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        related="employee_id.department_id",
        store=True,
    )
    job_id = fields.Many2one(
        "hr.job",
        string="Job Position",
        related="employee_id.job_id",
        store=True,
    )
    lateness_count = fields.Integer(
        string="Lateness Count",
        required=True,
        default=0,
        help="จำนวนครั้งของการมาสาย",
    )
    lateness_minutes = fields.Integer(
        string="Total Minutes",
        required=True,
        default=0,
        help="จำนวนนาทีรวมของการมาสาย",
    )
    avg_minutes_per_lateness = fields.Float(
        string="Avg Minutes",
        compute="_compute_avg_minutes",
        store=True,
        digits=(16, 1),
        help="ค่าเฉลี่ยนาทีต่อครั้ง",
    )
    current_token_balance = fields.Integer(
        related="employee_id.current_token_balance",
        string="Current Token Balance",
        store=False,
        readonly=True,
        help="Token ปัจจุบันของพนักงาน",
    )
    last_lateness_date = fields.Date(
        string="Last Lateness",
        compute="_compute_last_lateness_date",
        store=False,
        help="วันที่มาสายล่าสุดในงวดนี้",
    )

    @api.depends("lateness_count", "lateness_minutes")
    def _compute_avg_minutes(self):
        for rec in self:
            if rec.lateness_count > 0:
                rec.avg_minutes_per_lateness = (
                    rec.lateness_minutes / rec.lateness_count
                )
            else:
                rec.avg_minutes_per_lateness = 0.0

    @api.depends("employee_id", "summary_id.date_from", "summary_id.date_to")
    def _compute_last_lateness_date(self):
        Log = self.env["hr.lateness.log"]
        for rec in self:
            rec.last_lateness_date = False
            if not rec.employee_id or not rec.summary_id:
                continue

            min_minutes = (
                rec.summary_id.company_id.lateness_alert_min_minutes
                or rec.summary_id.company_id.hr_lateness_grace
                or 0
            )
            domain = [
                ("employee_id", "=", rec.employee_id.id),
                ("company_id", "=", rec.summary_id.company_id.id),
                ("date", ">=", rec.summary_id.date_from),
                ("date", "<=", rec.summary_id.date_to),
                ("minutes", ">=", min_minutes),
            ]
            last_log = Log.search(domain, order="date desc", limit=1)
            rec.last_lateness_date = last_log.date if last_log else False

    def action_view_lateness_logs(self):
        """เปิดดู lateness logs ของพนักงานนี้"""
        self.ensure_one()
        return {
            "name": _("Lateness Logs"),
            "type": "ir.actions.act_window",
            "res_model": "hr.lateness.log",
            "view_mode": "tree,form",
            "domain": [
                ("employee_id", "=", self.employee_id.id),
                ("date", ">=", self.summary_id.date_from),
                ("date", "<=", self.summary_id.date_to),
            ],
            "context": {"default_employee_id": self.employee_id.id},
        }
