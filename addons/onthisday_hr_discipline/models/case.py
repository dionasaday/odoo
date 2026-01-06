# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class DisciplineCase(models.Model):
    _name = "hr.discipline.case"
    _description = "กรณีความผิด"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"

    # -------------------------------------------------------------------------
    # Core fields
    # -------------------------------------------------------------------------
    name = fields.Char(
        string="Case No.",
        required=True,
        copy=False,
        index=True,
        tracking=True,
        default=lambda self: self._default_case_name(),
    )
    employee_id = fields.Many2one("hr.employee", required=True, tracking=True)

    # sync บริษัทตามพนักงาน (store เพื่อค้น/กรองเร็ว)
    company_id = fields.Many2one(
        "res.company",
        related="employee_id.company_id",
        store=True,
        readonly=True,
        index=True,
    )

    date = fields.Date(default=fields.Date.today, required=True, tracking=True)

    offense_id = fields.Many2one("hr.discipline.offense", required=True)

    # เดิมเคย related -> เปลี่ยนเป็น compute แบบปลอดภัย
    severity = fields.Char(
        string="Severity",
        compute="_compute_offense_meta",
        store=True,
        readonly=False,
    )
    points = fields.Integer(
        string="Points",
        compute="_compute_offense_meta",
        store=True,
        readonly=False,
    )

    description = fields.Text()
    is_attendance_auto = fields.Boolean(default=False, index=True)
    attendance_id = fields.Many2one(
        "hr.attendance",
        string="Attendance",
        ondelete="set null",
        index=True,
        help="Linked attendance record (Policy 002/2025: one case per attendance for idempotency)."
    )
    lateness_minutes = fields.Integer()
    lateness_alert_sent = fields.Boolean(default=False)

    # ต้องมี field case_id บน hr.lateness.log แล้ว
    lateness_log_ids = fields.One2many(
        "hr.lateness.log", "case_id", string="Bundled Lateness Logs", readonly=True
    )

    status = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("appeal", "Appeal"),
            ("resolved", "Resolved"),
        ],
        default="draft",
        tracking=True,
    )

    calendar_year = fields.Integer(compute="_compute_year", store=True)

    # คะแนนรวมจริง จะถูกบันทึกตอนกด Confirm
    total_points_before = fields.Integer(string="Total Points Before", readonly=True, default=0)
    total_points_after = fields.Integer(string="Total Points After", readonly=True, default=0)

    # ผู้ใช้เลือก/แก้บทลงโทษเองได้
    action_suggested_id = fields.Many2one(
        "hr.discipline.action",
        string="Action Suggested",
        help="ค่าเริ่มต้นจะคำนวณให้โดยอัตโนมัติ แต่สามารถเปลี่ยนได้",
    )
    action_taken_id = fields.Many2one("hr.discipline.action", string="Action Taken")
    reset_points = fields.Boolean(readonly=True)
    
    # --- Policy 002/2025: HR Confirmation for late > 10 min with notification ---
    hr_confirmed_notification = fields.Boolean(
        string="ยืนยันว่าแจ้งล่วงหน้า",
        default=False,
        tracking=True,
        help="ติ๊กเพื่อยืนยันว่าพนักงานแจ้งล่วงหน้า (ถ้าไม่ติ๊กจะถือว่าไม่แจ้งเมื่อกดยืนยันเคส)."
    )
    hr_confirmed_by = fields.Many2one(
        "res.users",
        string="ยืนยันโดย",
        readonly=True,
        tracking=True,
        help="HR user who confirmed the notification status."
    )
    hr_confirmed_at = fields.Datetime(
        string="เวลาที่ยืนยัน",
        readonly=True,
        tracking=True,
        help="Timestamp when HR confirmed the notification status."
    )
    confirmed_by = fields.Many2one(
        "res.users",
        string="ยืนยันเคสโดย",
        readonly=True,
        tracking=True,
        help="User who confirmed the case (separate from notification confirmation)."
    )
    confirmed_at = fields.Datetime(
        string="เวลาที่ยืนยันเคส",
        readonly=True,
        tracking=True,
        help="Timestamp when the case was confirmed."
    )
    punishment_by = fields.Many2one(
        "res.users",
        string="บันทึกบทลงโทษโดย",
        readonly=True,
        tracking=True,
        help="User who recorded the punishment."
    )
    punishment_at = fields.Datetime(
        string="เวลาบันทึกบทลงโทษ",
        readonly=True,
        tracking=True,
        help="Timestamp when the punishment was recorded."
    )
    punishment_note = fields.Text(
        string="ข้อความเพิ่มเติม",
        help="ข้อความเพิ่มเติมสำหรับการสรุปบทลงโทษ (จะแสดงในอีเมลแจ้งพนักงาน)",
    )
    requires_hr_confirmation = fields.Boolean(
        compute="_compute_requires_hr_confirmation",
        store=False,
        help="True เมื่อเคสต้องให้ HR ยืนยันการแจ้งล่วงหน้า (มาสายเกินเกณฑ์และระบุว่าแจ้งล่วงหน้า).",
    )

    # --------- Preview (โชว์ตอน draft) ----------
    preview_points_before = fields.Integer(
        string="Total Points Before (Preview)",
        compute="_compute_preview_totals",
        store=False,
    )
    preview_points_after = fields.Integer(
        string="Total Points After (Preview)",
        compute="_compute_preview_totals",
        store=False,
    )

    # -------------------------------------------------------------------------
    # Default methods
    # -------------------------------------------------------------------------
    def _default_case_name(self):
        """Generate default Case No. using sequence with company_id support"""
        company_id = False
        # Try to get company_id from employee_id if available
        if hasattr(self, 'employee_id') and self.employee_id:
            company_id = self.employee_id.company_id.id if self.employee_id.company_id else False
        # Fallback to company_id field if available
        elif hasattr(self, 'company_id') and self.company_id:
            company_id = self.company_id.id
        # Fallback to current user's company
        elif hasattr(self, 'env') and hasattr(self.env, 'company_id'):
            company_id = self.env.company.id if self.env.company else False
        
        return self.env["ir.sequence"].with_company(company_id).next_by_code("hr.discipline.case") or "/"

    # -------------------------------------------------------------------------
    # Computes / Onchange
    # -------------------------------------------------------------------------
    @api.depends(
        "is_attendance_auto",
        "attendance_id",
        "lateness_minutes",
        "employee_id.company_id.lateness_tier1_max_minutes",
    )
    def _compute_requires_hr_confirmation(self):
        Log = self.env["hr.lateness.log"].sudo()
        attendance_ids = [rec.attendance_id.id for rec in self if rec.attendance_id]
        logs_by_att = {}
        if attendance_ids:
            logs = Log.search([("attendance_id", "in", attendance_ids)])
            logs_by_att = {log.attendance_id.id: log for log in logs}
        for rec in self:
            if not rec.is_attendance_auto or not rec.attendance_id:
                rec.requires_hr_confirmation = False
                continue
            tier1_max = rec.employee_id.company_id.lateness_tier1_max_minutes or 10
            log = logs_by_att.get(rec.attendance_id.id)
            late_minutes = rec.lateness_minutes or (log.minutes if log else 0)
            if not late_minutes or late_minutes <= tier1_max:
                rec.requires_hr_confirmation = False
                continue
            rec.requires_hr_confirmation = bool(log and log.notified_before_start)

    @api.depends("date")
    def _compute_year(self):
        for rec in self:
            rec.calendar_year = (rec.date or fields.Date.today()).year

    def _sum_points(self, employee, year):
        """รวมคะแนนสะสมจากสมุดคะแนนของพนักงาน/ปีนั้น ๆ"""
        Ledger = self.env["hr.discipline.point.ledger"].sudo()
        return sum(
            Ledger.search(
                [("employee_id", "=", employee.id), ("year", "=", year)]
            ).mapped("points_change")
        )

    @api.depends("employee_id", "calendar_year", "offense_id")
    def _compute_preview_totals(self):
        for rec in self:
            if not (rec.employee_id and rec.calendar_year):
                rec.preview_points_before = 0
                rec.preview_points_after = rec.points or 0
                continue
            before = rec._sum_points(rec.employee_id, rec.calendar_year)
            rec.preview_points_before = before
            rec.preview_points_after = before + (rec.points or 0)

    @api.depends("offense_id")
    def _compute_offense_meta(self):
        """คำนวณ points/severity จาก offense_id แบบปลอดภัย (ไม่พึ่ง related)"""
        for rec in self:
            pts = 0
            sev = rec.severity  # คงค่าเดิมถ้าไม่มีข้อมูลใหม่
            off = rec.offense_id
            if off:
                if "points" in off._fields:
                    pts = off.points or 0
                # ใช้ชื่อของหมวดเป็น severity ถ้ามี
                if "category_id" in off._fields and off.category_id:
                    if "name" in off.category_id._fields:
                        sev = off.category_id.name or sev
            rec.points = pts
            rec.severity = sev

    @api.onchange("employee_id", "calendar_year", "offense_id")
    def _onchange_fill_action_suggested(self):
        for rec in self:
            if not (rec.employee_id and rec.calendar_year and rec.offense_id):
                rec.action_suggested_id = False
                continue
            after = rec._sum_points(rec.employee_id, rec.calendar_year) + (rec.points or 0)
            rule = (
                rec.env["hr.discipline.action"]
                .search(
                    [("min_points", "<=", after), ("max_points", ">=", after)],
                    order="min_points desc",
                    limit=1,
                )
            )
            rec.action_suggested_id = rule.id

    # -------------------------------------------------------------------------
    # Utilities / Guards
    # -------------------------------------------------------------------------
    def _check_backdate_guard(self, *, company, case_date, is_auto=False):
        """Raise/Skip if case_date is before company's discipline_start_date.
        - manual (is_auto=False): raise UserError
        - auto (is_auto=True)   : return False (ให้ caller ข้าม)
        """
        start = getattr(company, "discipline_start_date", False)
        if start and case_date < start:
            if is_auto or self.env.context.get("skip_backdate_error"):
                _logger.info(
                    "Skip discipline case before start date: %s < %s (company=%s)",
                    case_date, start, company.id,
                )
                return False
            raise UserError(
                _("Cannot create/alter discipline case dated %s before company start date %s.")
                % (case_date, start)
            )
        return True

    def _get_confirmation_lateness_minutes(self):
        """Resolve lateness minutes for confirmation logic (case or linked log)."""
        self.ensure_one()
        if self.lateness_minutes:
            return self.lateness_minutes
        if self.attendance_id:
            log = self.env["hr.lateness.log"].sudo().search(
                [("attendance_id", "=", self.attendance_id.id)],
                limit=1,
            )
            if log:
                return log.minutes or 0
        return 0

    # -------------------------------------------------------------------------
    # Side effects (Confirm)
    # -------------------------------------------------------------------------
    def _do_confirm_side_effects(self):
        """สร้างเลดเจอร์ + บันทึกคะแนนรวมก่อน/หลัง (ทำครั้งเดียวต่อเคส)"""
        Ledger = self.env["hr.discipline.point.ledger"].sudo()
        for rec in self:
            # Check if ledger entry already exists
            existing_ledger = Ledger.search([("case_id", "=", rec.id)], limit=1)
            if existing_ledger:
                _logger.info("Ledger entry already exists for case %s (ID=%s), skipping", rec.name, rec.id)
                # Still update total_points_before and total_points_after if not set
                if not rec.total_points_before and not rec.total_points_after:
                    before = rec._sum_points(rec.employee_id, rec.calendar_year)
                    after = before + (rec.points or 0)
                    rec.write({"total_points_before": before, "total_points_after": after})
                continue
            
            before = rec._sum_points(rec.employee_id, rec.calendar_year)
            after = before + (rec.points or 0)
            ledger_vals = {
                "date": rec.date,
                "year": rec.calendar_year,
                "employee_id": rec.employee_id.id,
                "points_change": rec.points,  # This is negative for token deductions (e.g., -1, -3)
                "reason": _("Offense: %s") % (rec.offense_id.name or ""),
                "case_id": rec.id,
            }
            try:
                ledger_entry = Ledger.create(ledger_vals)
                _logger.info("Created ledger entry ID=%s for case %s (ID=%s): date=%s, points_change=%d, employee_id=%s",
                            ledger_entry.id, rec.name, rec.id, rec.date, rec.points, rec.employee_id.id)
                rec.write({"total_points_before": before, "total_points_after": after})
                rec.message_post(body=_("Confirmed. Points %s → %s") % (before, after))
                
                # Force recompute token balance for the employee
                try:
                    rec.employee_id._compute_current_token_balance()
                    _logger.info("Triggered token balance recompute for employee %s (ID=%s)", rec.employee_id.name, rec.employee_id.id)
                except Exception as e:
                    _logger.error("Failed to recompute token balance for employee %s: %s", rec.employee_id.id, str(e))
            except Exception as e:
                _logger.error("Failed to create ledger entry for case %s (ID=%s): %s", rec.name, rec.id, str(e))
                raise

    # -------------------------------------------------------------------------
    # Email helpers
    # -------------------------------------------------------------------------
    def _manager_partner(self):
        self.ensure_one()
        return self.employee_id.parent_id.user_id.partner_id

    def _get_manager_email(self):
        self.ensure_one()
        mgr = self.employee_id.parent_id.sudo()
        if not mgr:
            return False
        if mgr.work_email:
            return mgr.work_email
        if mgr.user_id and mgr.user_id.email:
            return mgr.user_id.email
        addr = getattr(mgr, "address_home_id", False) or getattr(mgr, "address_id", False)
        if addr and addr.email:
            return addr.email
        return False

    def _notify_on_confirm(self):
        """ส่งอีเมลแจ้งหัวหน้า/พนักงานเมื่อเคสถูกยืนยัน"""
        self.ensure_one()
        Log = self.env["hr.discipline.email.log"]
        if self.lateness_log_ids:
            xmlid_mgr = "onthisday_hr_discipline.mail_tmpl_lateness_bundle_to_manager"
            xmlid_emp = "onthisday_hr_discipline.mail_tmpl_lateness_bundle_to_employee"
        else:
            xmlid_mgr = "onthisday_hr_discipline.mail_tmpl_case_confirmed_to_manager"
            xmlid_emp = "onthisday_hr_discipline.mail_tmpl_points_to_employee"

        tmpl_mgr = self.env.ref(xmlid_mgr, raise_if_not_found=False)
        if tmpl_mgr:
            mgr = self.employee_id.parent_id.sudo()
            addr = getattr(mgr, "address_home_id", False) or getattr(mgr, "address_id", False)
            mgr_email = (
                mgr.work_email
                or (mgr.user_id and mgr.user_id.email)
                or (addr and addr.email)
            )
            if mgr_email:
                email_values = Log._prepare_email_values(mgr_email, manager=mgr)
                try:
                    tmpl_mgr.send_mail(self.id, force_send=True, email_values=email_values)
                    Log._log_email(
                        "hr.discipline.case",
                        self.id,
                        tmpl_mgr,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                    )
                except Exception as e:
                    _logger.error("Failed to send email to manager %s for case %s: %s", 
                                  mgr_email, self.id, str(e))
                    Log._log_email(
                        "hr.discipline.case",
                        self.id,
                        tmpl_mgr,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                        state="failed",
                        error_message=str(e),
                    )

        tmpl_emp = self.env.ref(xmlid_emp, raise_if_not_found=False)
        if tmpl_emp:
            emp = self.employee_id.sudo()
            emp_addr = getattr(emp, "address_home_id", False) or getattr(emp, "address_id", False)
            emp_email = (
                emp.work_email
                or (emp.user_id and emp.user_id.email)  # safe fallback
                or (emp_addr and emp_addr.email)
            )
            if emp_email:
                manager = emp.parent_id.sudo()
                email_values = Log._prepare_email_values(emp_email, manager=manager)
                try:
                    tmpl_emp.send_mail(self.id, force_send=True, email_values=email_values)
                    Log._log_email(
                        "hr.discipline.case",
                        self.id,
                        tmpl_emp,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                    )
                except Exception as e:
                    _logger.error("Failed to send email to employee %s for case %s: %s", 
                                  emp_email, self.id, str(e))
                    Log._log_email(
                        "hr.discipline.case",
                        self.id,
                        tmpl_emp,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                        state="failed",
                        error_message=str(e),
                    )

    def _notify_on_punishment(self):
        """ส่งอีเมลแจ้งพนักงานหลังสรุปบทลงโทษ"""
        self.ensure_one()
        Log = self.env["hr.discipline.email.log"]
        tmpl = self.env.ref(
            "onthisday_hr_discipline.mail_tmpl_punishment_to_employee",
            raise_if_not_found=False,
        )
        if not tmpl:
            return False
        emp = self.employee_id.sudo()
        emp_addr = getattr(emp, "address_home_id", False) or getattr(emp, "address_id", False)
        emp_email = (
            emp.work_email
            or (emp.user_id and emp.user_id.email)
            or (emp_addr and emp_addr.email)
        )
        if not emp_email:
            return False
        manager = emp.parent_id.sudo()
        email_values = Log._prepare_email_values(emp_email, manager=manager)
        if self.punishment_note and "punishment_note" not in (tmpl.body_html or ""):
            rendered = tmpl._render_field("body_html", [self.id]).get(self.id) or ""
            rendered = str(rendered)
            note_html = (
                "<p><b>ข้อความเพิ่มเติม:</b></p>"
                "<div style=\"white-space: pre-wrap; padding: 8px; border: 1px solid #bdc3c7; "
                "background-color: #f8f9fa;\">%s</div>"
            ) % (self.punishment_note or "")
            if "</div>" in rendered:
                rendered = rendered.replace("</div>", f"{note_html}</div>", 1)
            else:
                rendered = f"{rendered}{note_html}"
            email_values["body_html"] = rendered
        try:
            tmpl.sudo().send_mail(self.id, force_send=True, email_values=email_values)
            Log._log_email(
                "hr.discipline.case",
                self.id,
                tmpl,
                email_values.get("email_to"),
                email_values.get("email_cc"),
            )
        except Exception as e:
            _logger.error("Failed to send punishment email to employee %s for case %s: %s", 
                          emp_email, self.id, str(e))
            Log._log_email(
                "hr.discipline.case",
                self.id,
                tmpl,
                email_values.get("email_to"),
                email_values.get("email_cc"),
                state="failed",
                error_message=str(e),
            )
            return False
        return True

    # -------------------------------------------------------------------------
    # ORM overrides
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list=None):
        """
        รองรับทั้ง:
          - dict เดี่ยว -> แปลงเป็น [dict]
          - list ของ dict -> ใช้ตามปกติ
          - None หรือ empty -> return empty recordset
        และกันย้อนหลังก่อน company.discipline_start_date
        
        Note: ใช้ vals_list=None เพื่อรองรับกรณีที่ decorator ไม่ทำงาน
        แต่ใน Odoo 16 decorator จะแปลง dict เป็น [dict] ให้อัตโนมัติ
        """
        # Handle empty/None case (fallback for edge cases)
        if vals_list is None:
            vals_list = []
        if not vals_list:
            return self.browse()
        
        # Handle single dict (backward compatibility)
        # Note: @api.model_create_multi should handle this, but we keep for safety
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        allowed = []
        Emp = self.env["hr.employee"].sudo()
        for vals in vals_list:
            emp = Emp.browse(vals.get("employee_id")) if vals.get("employee_id") else False
            company = (emp and emp.company_id) or self.env.company
            case_date = fields.Date.to_date(vals.get("date") or fields.Date.context_today(self))
            is_auto = bool(vals.get("is_attendance_auto")) or bool(self.env.context.get("skip_backdate_error"))
            if not self._check_backdate_guard(company=company, case_date=case_date, is_auto=is_auto):
                continue
            allowed.append(vals)

        recs = super(DisciplineCase, self).create(allowed) if allowed else self.browse()
        # Note: Case No. (name) is generated by default function in field definition
        # If name is still "/" after create, it means sequence doesn't exist yet
        # We'll update it later via post_init_hook or manual update
        for rec in recs:
            _logger.info("Created case ID=%s, name=%s (after create)", rec.id, rec.name)
            # Try to generate name if still "/" or False
            if not rec.name or rec.name == "/":
                try:
                    # ตรวจสอบว่า sequence มีอยู่หรือไม่
                    company_id = rec.company_id.id if rec.company_id else False
                    sequence_domain = [
                        ("code", "=", "hr.discipline.case"),
                        "|",
                        ("company_id", "=", company_id),
                        ("company_id", "=", False),
                    ]
                    sequence = self.env["ir.sequence"].search(sequence_domain, limit=1)
                    if not sequence:
                        # ถ้าไม่มี sequence ให้สร้างใหม่
                        _logger.warning("Sequence 'hr.discipline.case' not found. Creating...")
                        sequence_vals = {
                            "name": "Discipline Case",
                            "code": "hr.discipline.case",
                            "prefix": "DISC/%(year)s/",
                            "padding": 4,
                            "number_next": 1,
                            "number_increment": 1,
                        }
                        if company_id:
                            sequence_vals["company_id"] = company_id
                        sequence = self.env["ir.sequence"].create(sequence_vals)
                        _logger.info(
                            "Created sequence 'hr.discipline.case' with ID=%s (company_id=%s)",
                            sequence.id,
                            company_id,
                        )
                    
                    # สร้าง Case No. - ใช้ next_by_code() พร้อม company_id เพื่อรองรับ multi-company
                    new_name = self.env["ir.sequence"].with_company(company_id).next_by_code("hr.discipline.case") or "/"
                    if new_name != "/":
                        rec.write({"name": new_name})
                        _logger.info("Updated case ID=%s (company_id=%s) name from '/' to '%s'", rec.id, company_id, new_name)
                    else:
                        _logger.warning("Sequence 'hr.discipline.case' returned '/' for case ID=%s", rec.id)
                except Exception as e:
                    _logger.error("Error generating Case No. for case ID=%s: %s", rec.id, str(e))
        # subscribe หัวหน้าให้ติดตามเคส
        for rec in recs:
            partner = rec._manager_partner()
            if partner:
                rec.message_subscribe(partner_ids=[partner.id])
        return recs

    def write(self, vals):
        """กันแก้ไขย้อนหลังข้าม start date (เช่นเปลี่ยน employee/date)"""
        if any(k in vals for k in ("date", "employee_id")):
            Emp = self.env["hr.employee"].sudo()
            for rec in self:
                new_emp = Emp.browse(vals["employee_id"]) if "employee_id" in vals else rec.employee_id
                new_company = new_emp.company_id or rec.company_id or self.env.company
                new_date = fields.Date.to_date(vals.get("date") or rec.date or fields.Date.context_today(self))
                self._check_backdate_guard(company=new_company, case_date=new_date, is_auto=False)

        if "hr_confirmed_notification" not in vals:
            will_be_confirmed = (
                "status" in vals
                and vals["status"] == "confirmed"
                and any(r.status != "confirmed" for r in self)
            )
            res = super().write(vals)
            if will_be_confirmed:
                self.filtered(lambda r: r.status == "confirmed")._do_confirm_side_effects()
            return res

        is_manager = self.env.user.has_group("onthisday_hr_discipline.group_discipline_manager")
        is_hr = self.env.user.has_group("onthisday_hr_discipline.group_discipline_hr")
        Ledger = self.env["hr.discipline.point.ledger"].sudo()
        res = True
        for rec in self:
            if is_manager and not is_hr and rec.status != "draft":
                raise UserError(_("ผู้จัดการสามารถยืนยันได้เฉพาะเคสที่อยู่สถานะรอตรวจสอบเท่านั้น"))

            old_confirm = rec.hr_confirmed_notification
            rec_vals = dict(vals)
            late_minutes = rec._get_confirmation_lateness_minutes()
            if (
                rec.is_attendance_auto
                and late_minutes
                and late_minutes > (rec.employee_id.company_id.lateness_tier1_max_minutes or 10)
            ):
                company = rec.employee_id.company_id
                if rec_vals["hr_confirmed_notification"]:
                    new_tokens = company.tokens_tier2 or 2
                    offense_xmlid = "onthisday_hr_discipline.offense_late_tier2"
                else:
                    new_tokens = company.tokens_no_notice or 3
                    offense_xmlid = "onthisday_hr_discipline.offense_late_no_notice"

                offense = self.env.ref(offense_xmlid, raise_if_not_found=False)
                if offense:
                    rec_vals["offense_id"] = offense.id
                    rec_vals["points"] = -new_tokens

                rec_vals["hr_confirmed_by"] = self.env.user.id
                rec_vals["hr_confirmed_at"] = fields.Datetime.now()

                if rec.attendance_id:
                    log = self.env["hr.lateness.log"].search(
                        [("attendance_id", "=", rec.attendance_id.id)],
                        limit=1,
                    )
                    if log:
                        log.write({"token_deducted": new_tokens})

            was_confirmed = rec.status == "confirmed"
            will_be_confirmed = rec_vals.get("status") == "confirmed" and not was_confirmed
            res = super(DisciplineCase, rec).write(rec_vals) and res

            if (
                rec.status == "confirmed"
                and old_confirm != rec.hr_confirmed_notification
                and rec.is_attendance_auto
                and late_minutes
                and late_minutes > (rec.employee_id.company_id.lateness_tier1_max_minutes or 10)
            ):
                rec.message_post(
                    body=_("มีการเปลี่ยนสถานะการแจ้งล่วงหน้า ระบบจะคำนวณเลดเจอร์ใหม่")
                )
                ledger_entries = Ledger.search([("case_id", "=", rec.id)])
                if ledger_entries:
                    ledger_entries.unlink()
                rec._do_confirm_side_effects()

            if will_be_confirmed:
                rec._do_confirm_side_effects()

        return res

    # -------------------------------------------------------------------------
    # Buttons
    # -------------------------------------------------------------------------
    def action_confirm(self):
        """ปุ่ม Confirm: เปลี่ยนสถานะ + side-effects + ส่งอีเมล (ยกเว้นเคส Attendance ที่ context ขอให้ข้ามเมล)"""
        already_confirmed = []
        for rec in self:
            if not rec._check_backdate_guard(
                company=rec.company_id or self.env.company,
                case_date=rec.date,
                is_auto=bool(rec.is_attendance_auto),
            ):
                continue

            was_confirmed = rec.status == "confirmed"
            if rec.requires_hr_confirmation and not rec.hr_confirmed_at:
                rec.write({"hr_confirmed_notification": bool(rec.hr_confirmed_notification)})

            # Always call _do_confirm_side_effects even if already confirmed
            # This ensures ledger entry is created if it doesn't exist
            if not was_confirmed:
                rec.write(
                    {
                        "status": "confirmed",
                        "confirmed_by": self.env.user.id,
                        "confirmed_at": fields.Datetime.now(),
                    }
                )
            elif not rec.confirmed_at:
                rec.write(
                    {
                        "confirmed_by": self.env.user.id,
                        "confirmed_at": fields.Datetime.now(),
                    }
                )
            rec._do_confirm_side_effects()

            if not was_confirmed and not (
                rec.is_attendance_auto and rec.env.context.get("skip_case_email")
            ):
                rec._notify_on_confirm()
            if was_confirmed:
                already_confirmed.append(rec.name or str(rec.id))

        if already_confirmed and len(already_confirmed) == len(self):
            message = _("เคสนี้ยืนยันแล้ว ระบบไม่ส่งอีเมลซ้ำ")
        elif already_confirmed:
            message = _("ยืนยันเคสเรียบร้อย (เคสที่ยืนยันแล้วจะไม่ส่งอีเมลซ้ำ)")
        else:
            message = _("ยืนยันเคสเรียบร้อย")
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Confirmed"),
                "message": message,
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_apply_punishment(self):
        """ปุ่ม Apply Punishment: ถ้าไม่เลือก Action Taken ให้ใช้ Suggested และ reset คะแนนเมื่อ rule ระบุ"""
        Ledger = self.env["hr.discipline.point.ledger"].sudo()
        for rec in self:
            if not self.env.user.has_group("onthisday_hr_discipline.group_discipline_hr"):
                raise UserError(_("เฉพาะ HR เท่านั้นที่สรุปบทลงโทษได้"))
            if rec.status not in ("confirmed", "appeal"):
                raise UserError(_("Case must be Confirmed or in Appeal before applying punishment."))

            if not rec.action_taken_id:
                rec.action_taken_id = rec.action_suggested_id

            if rec.action_taken_id and rec.action_taken_id.auto_reset:
                total = rec._sum_points(rec.employee_id, rec.calendar_year)
                if total:
                    Ledger.create(
                        {
                            "date": fields.Date.today(),
                            "year": rec.calendar_year,
                            "employee_id": rec.employee_id.id,
                            "points_change": -total,
                            "reason": _("Reset after punishment for case %s") % rec.name,
                            "case_id": rec.id,
                        }
                    )
                    rec.reset_points = True

            rec.write(
                {
                    "status": "resolved",
                    "punishment_by": self.env.user.id,
                    "punishment_at": fields.Datetime.now(),
                }
            )
            rec.message_post(
                body=_("Punishment applied: %s") % (rec.action_taken_id.name or _("(none)"))
            )
            if rec.action_taken_id and rec.action_taken_id.send_punishment_email:
                rec._notify_on_punishment()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Done"),
                "message": _("บันทึกบทลงโทษเรียบร้อย"),
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_open_punishment_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group("onthisday_hr_discipline.group_discipline_hr"):
            raise UserError(_("เฉพาะ HR เท่านั้นที่สรุปบทลงโทษได้"))
        if self.status not in ("confirmed", "appeal"):
            raise UserError(_("เคสต้องอยู่สถานะ Confirmed หรือ Appeal ก่อน"))
        return {
            "type": "ir.actions.act_window",
            "name": _("สรุปบทลงโทษ"),
            "res_model": "hr.discipline.punishment.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_case_id": self.id,
                "default_action_taken_id": self.action_taken_id.id or self.action_suggested_id.id,
            },
        }
