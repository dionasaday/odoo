# -*- coding: utf-8 -*-
import logging
import pytz
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class HrLatenessLog(models.Model):
    _name = "hr.lateness.log"
    _description = "บันทึกการมาสาย (ต่อการลงเวลา)"
    _order = "date desc, id desc"
    _sql_constraints = [
        ('uniq_attendance', 'unique(attendance_id)', 'A lateness log already exists for this attendance.'),
    ]

    # บริษัท (รองรับหลายบริษัท และใช้กับการกรองรายงานได้)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
    )

    # ใคร / วันไหน / สายกี่นาที / อ้างอิง attendance
    employee_id   = fields.Many2one("hr.employee", required=True, index=True)
    date          = fields.Date(required=True, index=True)
    minutes       = fields.Integer(string="Lateness (min)", required=True)
    attendance_id = fields.Many2one("hr.attendance", ondelete="set null", index=True)

    # ผูกเข้ากับเคสที่ bundle แล้ว (legacy - Policy 002/2025 uses per-attendance cases)
    case_id = fields.Many2one(
        "hr.discipline.case",
        string="Discipline Case",
        ondelete="set null",
        index=True,
        help="Discipline case created for this lateness event (Policy 002/2025: one case per attendance)."
    )
    bundled = fields.Boolean(
        default=False,
        index=True,
        help="Legacy field: kept for backward compatibility. Policy 002/2025 uses per-attendance cases."
    )
    
    # --- Policy 002/2025: Notification fields ---
    notified_before_start = fields.Boolean(
        string="Notified Before Start",
        default=False,
        index=True,
        help="Whether employee notified manager before scheduled start time."
    )
    notified_at = fields.Datetime(
        string="Notification Time",
        help="Timestamp when employee notified manager (if notified_before_start is True)."
    )
    notified_channel = fields.Selection(
        [
            ("line", "LINE Group"),
            ("line_direct", "LINE Direct Message"),
            ("phone", "Phone Call"),
            ("email", "Email"),
            ("other", "Other"),
        ],
        string="Notification Channel",
        help="Channel used for notification (LINE, phone, email, etc.)."
    )
    manager_confirmed_notification = fields.Boolean(
        string="Manager Confirmed",
        default=False,
        help="Manager has confirmed receipt of notification."
    )
    token_deducted = fields.Integer(
        string="Tokens Deducted",
        default=0,
        help="Number of tokens deducted for this lateness event (computed during processing)."
    )
    verification_state = fields.Selection(
        [
            ("pending", "รอตรวจสอบ"),
            ("confirmed", "ยืนยันแล้ว"),
        ],
        string="สถานะการยืนยัน",
        compute="_compute_verification_state",
        store=True,
        help="สถานะการยืนยันข้อมูลการมาสายโดย HR/หัวหน้า",
    )

    @api.depends("case_id.status")
    def _compute_verification_state(self):
        for rec in self:
            if rec.case_id and rec.case_id.status in ("confirmed", "appeal", "resolved"):
                rec.verification_state = "confirmed"
            else:
                rec.verification_state = "pending"

    # Helper fields for email template
    check_in_time = fields.Char(
        string="Check-in Time",
        compute="_compute_attendance_times",
        store=False,
    )
    check_out_time = fields.Char(
        string="Check-out Time",
        compute="_compute_attendance_times",
        store=False,
    )

    @api.depends('attendance_id.check_in', 'attendance_id.check_out')
    def _compute_attendance_times(self):
        """Compute formatted check-in and check-out times for email template
        Convert to employee/user timezone before formatting
        """
        for log in self:
            if log.attendance_id and log.attendance_id.check_in:
                # Get check_in datetime (stored as UTC in DB)
                check_in_dt = fields.Datetime.to_datetime(log.attendance_id.check_in)
                if check_in_dt:
                    # Convert to employee timezone (or user timezone)
                    employee = log.employee_id or log.attendance_id.employee_id
                    tz_name = (employee and employee.tz) or (employee and employee.user_id and employee.user_id.tz) or self.env.user.tz or 'UTC'
                    tz = pytz.timezone(tz_name)
                    utc_tz = pytz.UTC
                    
                    # Convert UTC to local timezone
                    utc_dt = utc_tz.localize(check_in_dt) if check_in_dt.tzinfo is None else check_in_dt
                    local_dt = utc_dt.astimezone(tz)
                    log.check_in_time = local_dt.strftime('%H:%M')
                else:
                    log.check_in_time = '-'
            else:
                log.check_in_time = '-'
            
            if log.attendance_id and log.attendance_id.check_out:
                check_out_dt = fields.Datetime.to_datetime(log.attendance_id.check_out)
                if check_out_dt:
                    # Convert to employee timezone
                    employee = log.employee_id or log.attendance_id.employee_id
                    tz_name = (employee and employee.tz) or (employee and employee.user_id and employee.user_id.tz) or self.env.user.tz or 'UTC'
                    tz = pytz.timezone(tz_name)
                    utc_tz = pytz.UTC
                    
                    # Convert UTC to local timezone
                    utc_dt = utc_tz.localize(check_out_dt) if check_out_dt.tzinfo is None else check_out_dt
                    local_dt = utc_dt.astimezone(tz)
                    log.check_out_time = local_dt.strftime('%H:%M')
                else:
                    log.check_out_time = '-'
            else:
                log.check_out_time = '-'

    # ---------------------------------------------------------------------
    # Block creation before company.discipline_start_date (กันย้อนหลัง)
    # ---------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list=None):
        """Skip any lateness logs dated before the company's discipline_start_date."""
        # Handle empty/None case
        if vals_list is None:
            vals_list = []
        if not vals_list:
            return self.browse()
        
        # Handle single dict (backward compatibility)
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        Company = self.env['res.company'].sudo()
        allowed = []
        for vals in vals_list:
            # company อาจไม่ถูกส่งมา — ใช้บริษัทปัจจุบันเป็นค่าเริ่มต้น
            company_id = vals.get('company_id') or self.env.company.id
            comp = Company.browse(company_id)
            start = getattr(comp, 'discipline_start_date', False)

            d = fields.Date.to_date(vals.get('date') or fields.Date.context_today(self))
            if start and d < start:
                _logger.info(
                    "Skip lateness.log %s < start %s (emp=%s, company=%s)",
                    d, start, vals.get('employee_id'), company_id
                )
                continue

            # เติม company_id ให้เสมอ (ถ้ายังไม่ถูกกำหนดมา)
            if 'company_id' in self._fields and not vals.get('company_id'):
                vals['company_id'] = company_id

            allowed.append(vals)

        recs = super().create(allowed) if allowed else self.browse()
        # If notified_before_start is set, recompute case if exists
        for rec in recs:
            if rec.notified_before_start and rec.case_id:
                rec._recompute_case_on_notification_change()
        return recs
    
    def write(self, vals):
        """Override write to recompute case when notified_before_start changes."""
        res = super().write(vals)
        # If notified_before_start changed, recompute case if exists
        if "notified_before_start" in vals:
            for rec in self:
                if rec.case_id:
                    rec._recompute_case_on_notification_change()
        return res
    
    def _recompute_case_on_notification_change(self):
        """Recompute discipline case when notification status changes."""
        if not self.attendance_id:
            return
        
        try:
            # Find existing case
            existing_case = self.env["hr.discipline.case"].search([
                ("attendance_id", "=", self.attendance_id.id),
                ("is_attendance_auto", "=", True),
            ], limit=1)
            
            if existing_case and existing_case.status == "confirmed":
                # If case is confirmed, delete ledger entry directly (instead of creating reversal)
                # This prevents accumulation of reversal entries in the ledger
                Ledger = self.env["hr.discipline.point.ledger"].sudo()
                ledger_entries = Ledger.search([("case_id", "=", existing_case.id)])
                if ledger_entries:
                    # Also delete any reversal entries related to this case
                    # (in case there are multiple reversals from previous recomputations)
                    reversal_entries = Ledger.search([
                        ("case_id", "=", False),
                        ("employee_id", "=", existing_case.employee_id.id),
                        ("year", "=", existing_case.calendar_year),
                        ("reason", "ilike", f"%case {existing_case.name}%"),
                    ])
                    if reversal_entries:
                        _logger.info("Deleting %d reversal entries related to case %s", len(reversal_entries), existing_case.name)
                        reversal_entries.unlink()
                    
                    # Delete the original ledger entry
                    _logger.info("Deleting ledger entry for case %s", existing_case.name)
                    ledger_entries.unlink()
            
            # Delete old case
            if existing_case:
                existing_case.unlink()
            
            # Reset attendance to trigger recomputation
            self.attendance_id.write({
                "discipline_processed": False,
                "lateness_minutes": 0,
            })
            
            # Recompute lateness and discipline
            self.attendance_id._compute_lateness_and_discipline()
            
            # Link new case to log if exists
            new_case = self.env["hr.discipline.case"].search([
                ("attendance_id", "=", self.attendance_id.id),
                ("is_attendance_auto", "=", True),
            ], limit=1)
            if new_case:
                self.write({"case_id": new_case.id})
        except Exception as e:
            _logger.error("Error recomputing case for lateness log %s: %s", self.id, str(e))
