# onthisday_hr_discipline/models/attendance_hook.py
# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta, date as date_class
import pytz
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = "hr.attendance"

    lateness_minutes = fields.Integer(string="Lateness (min)", readonly=True)
    discipline_processed = fields.Boolean(default=False, readonly=True)
    lateness_log_count = fields.Integer(
        string="Lateness Log Count",
        compute="_compute_lateness_log_count",
    )

    def _compute_lateness_log_count(self):
        """Compute count of lateness logs for this attendance."""
        # Initialize first
        for att in self:
            att.lateness_log_count = 0
        
        # Only compute if model exists
        try:
            if 'hr.lateness.log' not in self.env:
                return
        except (AttributeError, KeyError, Exception):
            return
        
        try:
            for att in self:
                try:
                    if not att.id:
                        continue
                    att.lateness_log_count = self.env["hr.lateness.log"].search_count([
                        ("attendance_id", "=", att.id),
                    ])
                except Exception:
                    att.lateness_log_count = 0
        except Exception:
            # Silently fail - defaults already set
            pass

    def action_view_lateness_log(self):
        """Open lateness log for this attendance."""
        self.ensure_one()
        log = self.env["hr.lateness.log"].search([("attendance_id", "=", self.id)], limit=1)
        if not log:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Lateness Log"),
                    "message": _("No lateness log found for this attendance."),
                    "sticky": False,
                },
            }
        return {
            "type": "ir.actions.act_window",
            "name": _("Lateness Log"),
            "res_model": "hr.lateness.log",
            "res_id": log.id,
            "view_mode": "form",
            "target": "current",
        }

    def _is_leave_or_public_holiday(self, employee, dt_from, dt_to=None):
        """
        คืนค่า True ถ้าเวลาที่ให้มาตัดกับ
        1) ใบลา (hr.leave) ที่อนุมัติแล้ว ของพนักงาน
        2) วันหยุด/Global Time Off (resource.calendar.leaves) ของปฏิทิน/บริษัท
        """
        if not employee or not dt_from:
            return False
        if not dt_to:
            dt_to = dt_from

        # --- 1) ใบลาอนุมัติแล้ว ของพนักงาน ---
        Leave = self.env["hr.leave"].sudo()
        # ใช้ field date_from/date_to (Datetime, UTC) ในการทับซ้อนช่วงเวลา
        leave_domain = [
            ("employee_id", "=", employee.id),
            ("state", "=", "validate"),
            ("date_from", "<=", dt_to),
            ("date_to", ">=", dt_from),
            # filter ให้เป็นประเภท leave จริง (กันไว้เผื่อมีชนิดอื่น)
            ("holiday_status_id.time_type", "=", "leave"),
        ]
        if Leave.search_count(leave_domain):
            return True

        # --- 2) วันหยุด/Global Time Off จาก resource.calendar.leaves ---
        CalLeave = self.env["resource.calendar.leaves"].sudo()
        cal_ids = [False]
        if employee.resource_calendar_id:
            cal_ids.append(employee.resource_calendar_id.id)

        hol_domain = [
            ("calendar_id", "in", cal_ids),                         # ทั่วไปหรือของปฏิทินพนักงาน
            ("company_id", "in", [False, employee.company_id.id]),  # ทั่วไปหรือของบริษัท
            ("date_from", "<=", dt_to),
            ("date_to", ">=", dt_from),
        ]
        if CalLeave.search_count(hol_domain):
            return True

        return False

    @api.model_create_multi
    def create(self, vals_list=None):
        """Override create to compute lateness and discipline after creation."""
        # Handle empty/None case
        if vals_list is None:
            vals_list = []
        if not vals_list:
            return self.browse()
        
        # Handle single dict (backward compatibility)
        if isinstance(vals_list, dict):
            vals_list = [vals_list]
        
        recs = super().create(vals_list)
        recs._compute_lateness_and_discipline()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ["check_in", "check_out"]):
            # Policy 002/2025: If check_in changed, need to reverse/update previous case
            for att in self:
                if att.discipline_processed:
                    # Find existing case for this attendance
                    existing_case = self.env["hr.discipline.case"].sudo().search([
                        ("attendance_id", "=", att.id),
                        ("is_attendance_auto", "=", True),
                    ], limit=1)
                    if existing_case and existing_case.status == "confirmed":
                        # Reverse the ledger entry if case was confirmed
                        self._reverse_case_ledger(existing_case)
                        # Delete or cancel the case
                        existing_case.unlink()
            # Reset and recompute
            self.write({"discipline_processed": False, "lateness_minutes": 0})
            self._compute_lateness_and_discipline()
        return res

    def _reverse_case_ledger(self, case):
        """Delete ledger entry for a case (when attendance check_in is modified)."""
        Ledger = self.env["hr.discipline.point.ledger"].sudo()
        existing_ledger = Ledger.search([("case_id", "=", case.id)])
        if existing_ledger:
            # Also delete any reversal entries related to this case
            # (in case there are multiple reversals from previous recomputations)
            reversal_entries = Ledger.search([
                ("case_id", "=", False),
                ("employee_id", "=", case.employee_id.id),
                ("year", "=", case.calendar_year),
                ("reason", "ilike", f"%case {case.name}%"),
            ])
            if reversal_entries:
                _logger.info("Deleting %d reversal entries related to case %s", len(reversal_entries), case.name)
                reversal_entries.unlink()
            
            # Delete the original ledger entry directly (instead of creating reversal)
            _logger.info(
                "Deleting ledger entry for case %s (attendance %s modified)",
                case.name, case.attendance_id.id if case.attendance_id else "N/A"
            )
            existing_ledger.unlink()

    # ---- Helpers ----
    def _get_notification_user(self, employee):
        """Resolve a user to notify for the given employee."""
        if employee and employee.user_id and employee.user_id.active:
            return employee.user_id
        env_user = self.env.user
        if env_user and env_user.active:
            env_employee = getattr(env_user, "employee_id", False)
            if env_employee and employee and env_employee.id == employee.id:
                return env_user
        return False

    def _send_user_notification(self, *, user, title, message, level="info", sticky=False):
        """Send a right-side UI notification with best-effort fallbacks."""
        if not user or not user.active:
            return
        notify_method = getattr(user, f"notify_{level}", None)
        if callable(notify_method):
            try:
                notify_method(message, title=title, sticky=sticky)
                return
            except TypeError:
                try:
                    notify_method(message)
                    return
                except Exception as exc:
                    _logger.warning("Failed to notify user %s via notify_%s: %s", user.id, level, str(exc))
            except Exception as exc:
                _logger.warning("Failed to notify user %s via notify_%s: %s", user.id, level, str(exc))
        try:
            user._bus_send("simple_notification", {
                "title": title,
                "message": message,
                "sticky": sticky,
                "type": level,
            })
        except Exception as exc:
            _logger.warning("Failed to send bus notification to user %s: %s", user.id, str(exc))

    def _notify_employee_late(self, *, employee, minutes, tokens, case):
        """Send a right-side UI notification to the employee (if user is linked)."""
        user = self._get_notification_user(employee)
        if not user:
            _logger.debug("No user to notify for late attendance (employee_id=%s).", employee.id if employee else None)
            return
        case_no = case.name or "-"
        if case.status == "draft":
            msg = _(
                "คุณมาสาย %(min)d นาที วันที่ %(date)s ระบบบันทึกเคส %(case)s และรอตรวจสอบ\n"
                "จำนวน Token ที่คาดว่าจะหัก: %(tokens)d"
            ) % {
                "min": minutes,
                "date": fields.Date.to_string(case.date),
                "tokens": tokens,
                "case": case_no,
            }
        else:
            msg = _(
                "คุณมาสาย %(min)d นาที วันที่ %(date)s ถูกหัก %(tokens)d Token (Case: %(case)s)"
            ) % {
                "min": minutes,
                "date": fields.Date.to_string(case.date),
                "tokens": tokens,
                "case": case_no,
            }
        self._send_user_notification(
            user=user,
            title=_("แจ้งเตือนการมาสาย"),
            message=msg,
            level="warning",
            sticky=True,
        )

    def _notify_employee_out_of_schedule(self, *, employee, check_in_dt, schedule_start, schedule_end):
        """Notify employee when check-in is outside working hours (no discipline case)."""
        user = self._get_notification_user(employee)
        if not user:
            _logger.debug("No user to notify for out-of-schedule check-in (employee_id=%s).",
                          employee.id if employee else None)
            return
        tzname = employee.tz or getattr(employee.user_id, "tz", False) or self.env.user.tz or "UTC"
        tz = pytz.timezone(tzname)
        UTC = pytz.UTC
        check_in_utc = UTC.localize(check_in_dt) if check_in_dt.tzinfo is None else check_in_dt
        check_in_local = check_in_utc.astimezone(tz)
        start_local = schedule_start
        end_local = schedule_end
        if schedule_start:
            start_local = UTC.localize(schedule_start) if schedule_start.tzinfo is None else schedule_start
            start_local = start_local.astimezone(tz)
        if schedule_end:
            end_local = UTC.localize(schedule_end) if schedule_end.tzinfo is None else schedule_end
            end_local = end_local.astimezone(tz)
        work_window = "-"
        if start_local and end_local:
            work_window = f"{start_local.strftime('%H:%M')}–{end_local.strftime('%H:%M')}"
        msg = _(
            "คุณลงเวลาเข้างานนอกช่วงเวลาทำงานของวันนั้น\n"
            "เวลาเข้างาน: %(check_in)s | ช่วงเวลางาน: %(window)s\n"
            "ระบบไม่สร้างเคสวินัย กรุณาตรวจสอบหรือแจ้งหัวหน้างานหากเป็นงานนอกเวลา"
        ) % {
            "check_in": check_in_local.strftime("%H:%M"),
            "window": work_window,
        }
        self._send_user_notification(
            user=user,
            title=_("ลงเวลานอกเวลางาน"),
            message=msg,
            level="info",
            sticky=False,
        )

    def _create_employee_late_activity(self, *, employee, minutes, tokens, case, attendance_id, threshold_minutes):
        """Create a persistent activity when lateness exceeds the threshold."""
        user = employee.user_id if employee else False
        if not user or not user.active:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        if not case:
            return
        key = f"[late_attendance_id={attendance_id}]"
        Activity = self.env["mail.activity"].sudo()
        existing = Activity.search([
            ("user_id", "=", user.id),
            ("activity_type_id", "=", activity_type.id),
            ("note", "ilike", key),
        ], limit=1)
        if existing:
            return
        res_model_id = self.env["ir.model"]._get("hr.discipline.case").id
        case_no = case.name or "-"
        if case.status == "draft":
            note = _(
                "เรียนคุณ %(employee)s,\n"
                "วันนี้คุณเข้างานสายเกินเกณฑ์ของบริษัท (สาย %(min)d นาที, เกณฑ์ %(threshold)d นาที)\n"
                "ระบบบันทึกกรณีความผิดเลขที่ %(case)s และรอตรวจสอบ\n"
                "จำนวน Token ที่คาดว่าจะหัก: %(tokens)d\n"
                "ขอความร่วมมือรักษาเวลาเพื่อประสิทธิภาพของทีม หากมีเหตุจำเป็นโปรดแจ้งหัวหน้างานล่วงหน้า\n"
                "%(key)s"
            ) % {
                "employee": employee.name,
                "min": minutes,
                "threshold": threshold_minutes,
                "case": case_no,
                "tokens": tokens,
                "key": key,
            }
        else:
            note = _(
                "เรียนคุณ %(employee)s,\n"
                "วันนี้คุณเข้างานสายเกินเกณฑ์ของบริษัท (สาย %(min)d นาที, เกณฑ์ %(threshold)d นาที)\n"
                "ระบบบันทึกกรณีความผิดเลขที่ %(case)s และหัก %(tokens)d Token แล้ว\n"
                "ขอความร่วมมือรักษาเวลาเพื่อประสิทธิภาพของทีม หากมีเหตุจำเป็นโปรดแจ้งหัวหน้างานล่วงหน้า\n"
                "%(key)s"
            ) % {
                "employee": employee.name,
                "min": minutes,
                "threshold": threshold_minutes,
                "case": case_no,
                "tokens": tokens,
                "key": key,
            }
        Activity.create({
            "res_model_id": res_model_id,
            "res_id": case.id,
            "activity_type_id": activity_type.id,
            "user_id": user.id,
            "summary": _("แจ้งเตือนมาสายเกินเกณฑ์"),
            "note": note,
            "date_deadline": case.date or fields.Date.context_today(self),
        })

    def _create_employee_repeat_activity(self, *, employee, count, threshold, period_start, period_end):
        """Create a persistent activity when lateness repeats in a period."""
        user = employee.user_id if employee else False
        if not user or not user.active:
            return
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not activity_type:
            return
        key = f"[repeat_lateness_period={period_start}:{period_end}]"
        Activity = self.env["mail.activity"].sudo()
        existing = Activity.search([
            ("user_id", "=", user.id),
            ("activity_type_id", "=", activity_type.id),
            ("note", "ilike", key),
        ], limit=1)
        if existing:
            return
        Log = self.env["hr.lateness.log"].sudo()
        log_rec = Log.search([
            ("employee_id", "=", employee.id),
            ("date", ">=", period_start),
            ("date", "<=", period_end),
        ], order="date desc, id desc", limit=1)
        case_rec = log_rec.case_id if log_rec and log_rec.case_id else self.env["hr.discipline.case"].sudo().search([
            ("employee_id", "=", employee.id),
            ("date", ">=", period_start),
            ("date", "<=", period_end),
            ("is_attendance_auto", "=", True),
        ], order="date desc, id desc", limit=1)
        if not case_rec and not log_rec:
            return
        if case_rec:
            res_model_id = self.env["ir.model"]._get("hr.discipline.case").id
            res_id = case_rec.id
        else:
            res_model_id = self.env["ir.model"]._get("hr.lateness.log").id
            res_id = log_rec.id
        note = _(
            "คุณมีการมาสายสะสม %(count)d ครั้ง (เกณฑ์แจ้งเตือน %(threshold)d ครั้ง)\n"
            "ช่วงวันที่ %(start)s ถึง %(end)s\n"
            "ขอความร่วมมือปรับเวลาเข้างานให้ตรงตามนโยบายบริษัท หากมีเหตุจำเป็นโปรดแจ้งหัวหน้างานล่วงหน้า\n"
            "%(key)s"
        ) % {
            "count": count,
            "threshold": threshold,
            "start": fields.Date.to_string(period_start),
            "end": fields.Date.to_string(period_end),
            "key": key,
        }
        Activity.create({
            "res_model_id": res_model_id,
            "res_id": res_id,
            "activity_type_id": activity_type.id,
            "user_id": user.id,
            "summary": _("แจ้งเตือนมาสายซ้ำในรอบ"),
            "note": note,
            "date_deadline": fields.Date.context_today(self),
        })

    def _is_working_day(self, employee, check_in_dt):
        """ตรวจสอบว่าเป็นวันทำงานหรือไม่ตาม resource calendar"""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            # ถ้าไม่มี calendar ให้ถือว่าเป็นวันทำงาน (fallback)
            return True
        
        tzname = employee.tz or getattr(employee.user_id, "tz", False) or self.env.user.tz or "UTC"
        tz = pytz.timezone(tzname)
        UTC = pytz.UTC

        if not check_in_dt:
            check_in_dt = fields.Datetime.now()

        check_in_local = UTC.localize(check_in_dt).astimezone(tz)
        day_local = check_in_local.date()
        dow = str(check_in_local.weekday())  # Monday=0..Sunday=6

        # Filter attendance lines by day of week
        # Note: In Odoo 19, resource.calendar.attendance may not have date_from/date_to fields
        # Use getattr() to safely check for these fields (returns None if field doesn't exist)
        lines = calendar.attendance_ids.filtered(
            lambda l: l.dayofweek == dow
            and (not getattr(l, 'date_from', None) or getattr(l, 'date_from', None) <= day_local)
            and (not getattr(l, 'date_to', None) or getattr(l, 'date_to', None) >= day_local)
        )

        if getattr(calendar, "two_weeks_calendar", False):
            iso_week = check_in_local.isocalendar()[1]
            week_type = "0" if iso_week % 2 == 0 else "1"
            lines = lines.filtered(lambda l: (getattr(l, "week_type", False) in (False, week_type)))

        # ถ้ามี lines แสดงว่าเป็นวันทำงาน
        return bool(lines)

    def _float_hour_to_time(self, hour_float):
        """Convert float hour (e.g., 8.5) to time object."""
        h = int(hour_float)
        m = int(round((hour_float - h) * 60))
        if m == 60:
            h += 1
            m = 0
        h = h % 24
        return time(h, m)

    def _get_daily_work_intervals(self, employee, check_in_dt):
        """Return list of work intervals (UTC naive) for the local day of check_in."""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        if not calendar:
            return None

        tzname = employee.tz or getattr(employee.user_id, "tz", False) or self.env.user.tz or "UTC"
        tz = pytz.timezone(tzname)
        UTC = pytz.UTC

        if not check_in_dt:
            check_in_dt = fields.Datetime.now()

        check_in_local = UTC.localize(check_in_dt).astimezone(tz)
        day_local = check_in_local.date()
        dow = str(check_in_local.weekday())

        lines = calendar.attendance_ids.filtered(
            lambda l: l.dayofweek == dow
            and (not getattr(l, 'date_from', None) or getattr(l, 'date_from', None) <= day_local)
            and (not getattr(l, 'date_to', None) or getattr(l, 'date_to', None) >= day_local)
        )

        if getattr(calendar, "two_weeks_calendar", False):
            iso_week = check_in_local.isocalendar()[1]
            week_type = "0" if iso_week % 2 == 0 else "1"
            lines = lines.filtered(lambda l: (getattr(l, "week_type", False) in (False, week_type)))

        intervals = []
        for line in lines:
            start_local = datetime.combine(day_local, self._float_hour_to_time(line.hour_from))
            end_local = datetime.combine(day_local, self._float_hour_to_time(line.hour_to))
            if line.hour_to >= 24 or line.hour_to < line.hour_from:
                end_local += timedelta(days=1)
            start_utc = tz.localize(start_local).astimezone(UTC).replace(tzinfo=None)
            end_utc = tz.localize(end_local).astimezone(UTC).replace(tzinfo=None)
            intervals.append((start_utc, end_utc))

        intervals.sort(key=lambda x: x[0])
        return intervals

    def _find_interval_for_check_in(self, check_in_dt, intervals):
        """Find work interval that contains check_in."""
        for start_utc, end_utc in intervals:
            if start_utc <= check_in_dt <= end_utc:
                return (start_utc, end_utc)
        return None

    def _get_schedule_start(self, employee, check_in_dt):
        """หาเวลาเริ่มงานของวันนั้น (UTC-naive) จาก resource calendar.
        ถ้าไม่พบ → fallback 09:00 local."""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        tzname = employee.tz or getattr(employee.user_id, "tz", False) or self.env.user.tz or "UTC"
        tz = pytz.timezone(tzname)
        UTC = pytz.UTC

        if not check_in_dt:
            check_in_dt = fields.Datetime.now()

        check_in_local = UTC.localize(check_in_dt).astimezone(tz)
        day_local = check_in_local.date()
        dow = str(check_in_local.weekday())  # Monday=0..Sunday=6

        if not calendar:
            scheduled_local = datetime.combine(day_local, time(9, 0))
            return tz.localize(scheduled_local).astimezone(UTC).replace(tzinfo=None)

        # Filter attendance lines by day of week
        # Note: In Odoo 19, resource.calendar.attendance may not have date_from/date_to fields
        # Use getattr() to safely check for these fields (returns None if field doesn't exist)
        lines = calendar.attendance_ids.filtered(
            lambda l: l.dayofweek == dow
            and (not getattr(l, 'date_from', None) or getattr(l, 'date_from', None) <= day_local)
            and (not getattr(l, 'date_to', None) or getattr(l, 'date_to', None) >= day_local)
        )

        if getattr(calendar, "two_weeks_calendar", False):
            iso_week = check_in_local.isocalendar()[1]
            week_type = "0" if iso_week % 2 == 0 else "1"
            lines = lines.filtered(lambda l: (getattr(l, "week_type", False) in (False, week_type)))

        if lines:
            hour_from = min(lines.mapped("hour_from"))
            h = int(hour_from)
            m = int(round((hour_from - h) * 60))
            scheduled_local = datetime.combine(day_local, time(h, m))
        else:
            scheduled_local = datetime.combine(day_local, time(9, 0))

        return tz.localize(scheduled_local).astimezone(UTC).replace(tzinfo=None)

    def _get_schedule_end(self, employee, check_in_dt):
        """หาเวลาเลิกงานของวันนั้น (UTC-naive) จาก resource calendar.
        ถ้าไม่พบ → return None."""
        calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
        tzname = employee.tz or getattr(employee.user_id, "tz", False) or self.env.user.tz or "UTC"
        tz = pytz.timezone(tzname)
        UTC = pytz.UTC

        if not check_in_dt:
            check_in_dt = fields.Datetime.now()

        check_in_local = UTC.localize(check_in_dt).astimezone(tz)
        day_local = check_in_local.date()
        dow = str(check_in_local.weekday())

        if not calendar:
            return None

        lines = calendar.attendance_ids.filtered(
            lambda l: l.dayofweek == dow
            and (not getattr(l, 'date_from', None) or getattr(l, 'date_from', None) <= day_local)
            and (not getattr(l, 'date_to', None) or getattr(l, 'date_to', None) >= day_local)
        )

        if getattr(calendar, "two_weeks_calendar", False):
            iso_week = check_in_local.isocalendar()[1]
            week_type = "0" if iso_week % 2 == 0 else "1"
            lines = lines.filtered(lambda l: (getattr(l, "week_type", False) in (False, week_type)))

        if not lines:
            return None

        hour_to = max(lines.mapped("hour_to"))
        h = int(hour_to)
        m = int(round((hour_to - h) * 60))
        scheduled_local = datetime.combine(day_local, time(h, m))
        return tz.localize(scheduled_local).astimezone(UTC).replace(tzinfo=None)

    # ------------------------------------------------------------------

    def _compute_lateness_and_discipline(self):
        """
        Policy 002/2025: Token-based lateness system.
        - Each lateness event creates one discipline case with negative points (tokens)
        - No bundling: one case per attendance lateness
        - Token deduction rules:
          1. No notification => -3 tokens
          2. Late <= 10 min (with notification) => -1 token
          3. Late > 10 min (with notification) => -2 tokens
        """
        Log = self.env["hr.lateness.log"].sudo()
        Case = self.env["hr.discipline.case"].sudo()

        for att in self:
            if att.discipline_processed or not att.check_in or not att.employee_id:
                _logger.debug("Skipping attendance %s: discipline_processed=%s, check_in=%s, employee_id=%s",
                             att.id, att.discipline_processed, att.check_in, att.employee_id.id if att.employee_id else None)
                continue

            company = att.employee_id.company_id
            grace = company.hr_lateness_grace or 0
            effective_late = 0

            # ตรวจสอบย้อนหลัง
            start_date = company.discipline_start_date
            att_date = fields.Date.to_date(att.check_in)
            if start_date and att_date < start_date:
                _logger.info("Skipping attendance %s: date %s < discipline_start_date %s",
                            att.id, att_date, start_date)
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue

            # หนึ่งเคสต่อวัน: ใช้ earliest check-in ของวันนั้นเท่านั้น
            day_start = datetime.combine(att_date, time.min)
            day_end = day_start + timedelta(days=1)
            earliest_att = self.env["hr.attendance"].search([
                ("employee_id", "=", att.employee_id.id),
                ("check_in", ">=", day_start),
                ("check_in", "<", day_end),
            ], order="check_in asc, id asc", limit=1)
            if earliest_att and earliest_att.id != att.id:
                _logger.info(
                    "Skipping attendance %s: not earliest check-in for %s (earliest=%s)",
                    att.id, att_date, earliest_att.id
                )
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue

            # ปิดการลงโทษเมื่อไม่มี calendar
            intervals = self._get_daily_work_intervals(att.employee_id, att.check_in)
            if intervals is None:
                _logger.warning("Skipping attendance %s: no resource calendar configured", att.id)
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue

            # ตรวจสอบว่าวันนี้มีการลาหรือเป็นวันหยุด
            period_from = att.check_in
            period_to = att.check_out or period_from
            if self._is_leave_or_public_holiday(att.employee_id, period_from, period_to):
                _logger.info("Skipping attendance %s: on leave or public holiday",
                            att.id)
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue

            # ไม่มีช่วงเวลาทำงานในวันนั้น (ไม่สร้างเคสวินัย)
            if not intervals:
                _logger.info("Skipping attendance %s: not a working day (date=%s)",
                            att.id, att_date)
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue

            # เช็คอินนอกช่วงเวลาทำงานของวันนั้น -> ไม่สร้างเคสวินัย
            interval = self._find_interval_for_check_in(att.check_in, intervals)
            if not interval:
                schedule_start = intervals[0][0] if intervals else None
                schedule_end = intervals[-1][1] if intervals else None
                _logger.info(
                    "Skipping attendance %s: check_in %s outside working intervals",
                    att.id, att.check_in
                )
                self._notify_employee_out_of_schedule(
                    employee=att.employee_id,
                    check_in_dt=att.check_in,
                    schedule_start=schedule_start,
                    schedule_end=schedule_end,
                )
                att.lateness_minutes = 0
                att.discipline_processed = True
                continue
            start_utc, end_utc = interval

            # 1) คำนวณนาทีสายจากช่วงเวลาทำงานที่ตรงกับการเช็คอิน
            late_min = max(0, int((att.check_in - start_utc).total_seconds() // 60))
            effective_late = late_min if late_min > grace else 0
            att.lateness_minutes = effective_late
            _logger.info("Attendance %s: late_min=%d, grace=%d, effective_late=%d",
                        att.id, late_min, grace, effective_late)

            # ไม่สายตามเกณฑ์ -> จบ
            if effective_late <= 0:
                _logger.info("Skipping attendance %s: effective_late=%d <= 0",
                            att.id, effective_late)
                att.discipline_processed = True
                continue

            # 2) สร้าง/อัปเดต lateness log (idempotent: unique by attendance_id)
            existing_log = Log.search([("attendance_id", "=", att.id)], limit=1)
            log_vals = {
                    "employee_id": att.employee_id.id,
                    "company_id": company.id,
                    "attendance_id": att.id,
                "date": att_date,
                    "minutes": effective_late,
                }
            if existing_log:
                existing_log.write(log_vals)
                log_rec = existing_log
            else:
                log_rec = Log.create(log_vals)
            
            _logger.info("Lateness log %s: notified_before_start=%s, effective_late=%d",
                        log_rec.id, log_rec.notified_before_start, effective_late)

            # 3) Policy 002/2025: Determine token deduction based on notification and lateness
            # Check if case already exists for this attendance (idempotency)
            # Also check via lateness_log.case_id to handle legacy cases
            existing_case = False
            if log_rec.case_id:
                existing_case = log_rec.case_id
            else:
                existing_case = Case.search([
                    ("attendance_id", "=", att.id),
                    ("is_attendance_auto", "=", True),
                ], limit=1)

            if existing_case:
                # Case already exists - skip to avoid duplicate ledger entries
                # But update lateness_minutes if check_in changed
                if existing_case.lateness_minutes != effective_late:
                    existing_case.write({"lateness_minutes": effective_late})
                att.discipline_processed = True
                continue

            # Determine token deduction based on Policy 002/2025 rules:
            # 1. มาสายเกินสิทธิ์ที่บริษัทอนุโลม แต่ไม่เกิน 10 นาที → -1 token (ไม่ต้องสนใจ notification)
            # 2. มาสายเกิน 10 นาที → -2 tokens (ไม่ต้องสนใจ notification)
            # 3. มาสายโดยไม่แจ้งหัวหน้างานล่วงหน้า → -3 tokens
            notified = log_rec.notified_before_start
            tier1_max = company.lateness_tier1_max_minutes or 10
            _logger.info("Determining tokens: notified=%s, effective_late=%d, tier1_max=%d",
                        notified, effective_late, tier1_max)
            
            # Policy ใหม่: ดูที่จำนวนนาทีที่สายเป็นหลัก
            if effective_late <= tier1_max:
                # สาย ≤ 10 นาที → -1 token (ไม่ต้องสนใจ notification status)
                tokens = company.tokens_tier1 or 1
                offense_xmlid = "onthisday_hr_discipline.offense_late_tier1"
                needs_hr_confirmation = False
                _logger.info("Token deduction: Late ≤ %d min → %d tokens (notification status ignored)", tier1_max, tokens)
            elif not notified:
                # สาย > 10 นาที + ไม่แจ้งล่วงหน้า → -3 tokens
                tokens = company.tokens_no_notice or 3
                offense_xmlid = "onthisday_hr_discipline.offense_late_no_notice"
                needs_hr_confirmation = False
                _logger.info("Token deduction: Late > %d min + No notification → %d tokens", tier1_max, tokens)
            else:
                # สาย > 10 นาที + แจ้งล่วงหน้า → -2 tokens
                tokens = company.tokens_tier2 or 2
                offense_xmlid = "onthisday_hr_discipline.offense_late_tier2"
                needs_hr_confirmation = True
                _logger.info("Token deduction: Late > %d min + Notification → %d tokens (needs HR confirmation)", tier1_max, tokens)

            # Get or create offense (points are negative for token deduction)
            offense = self.env.ref(offense_xmlid, raise_if_not_found=False)
            if not offense:
                # Fallback: find or create Lateness category
                cat = self.env["hr.discipline.offense.category"].search(
                    [("name", "=", "Lateness")], limit=1
                )
                if not cat:
                    cat = self.env["hr.discipline.offense.category"].create({
                        "name": "Lateness",
                    })
                
                offense_name = {
                    "onthisday_hr_discipline.offense_late_no_notice": _("Late (No Notice)"),
                    "onthisday_hr_discipline.offense_late_tier1": _("Late (Tier 1: ≤%d min)") % tier1_max,
                    "onthisday_hr_discipline.offense_late_tier2": _("Late (Tier 2: >%d min)") % tier1_max,
                }.get(offense_xmlid, _("Late"))
                
                offense = self.env["hr.discipline.offense"].create({
                    "name": offense_name,
                    "points": -tokens,  # Negative points = token deduction
                    "category_id": cat.id,
                })

            # 4) Create discipline case (one per attendance)
            # Convert datetime to local timezone for display
            check_in_str = "-"
            check_out_str = "-"
            if att.check_in:
                check_in_dt = fields.Datetime.to_datetime(att.check_in)
                if check_in_dt:
                    # Convert to employee's timezone
                    tzname = att.employee_id.tz or getattr(att.employee_id.user_id, "tz", False) or self.env.user.tz or "UTC"
                    tz = pytz.timezone(tzname)
                    UTC = pytz.UTC
                    # Convert UTC-naive to UTC-aware, then to local time
                    check_in_utc = UTC.localize(check_in_dt) if check_in_dt.tzinfo is None else check_in_dt
                    check_in_local = check_in_utc.astimezone(tz)
                    check_in_str = check_in_local.strftime('%H:%M')
            if att.check_out:
                check_out_dt = fields.Datetime.to_datetime(att.check_out)
                if check_out_dt:
                    # Convert to employee's timezone
                    tzname = att.employee_id.tz or getattr(att.employee_id.user_id, "tz", False) or self.env.user.tz or "UTC"
                    tz = pytz.timezone(tzname)
                    UTC = pytz.UTC
                    # Convert UTC-naive to UTC-aware, then to local time
                    check_out_utc = UTC.localize(check_out_dt) if check_out_dt.tzinfo is None else check_out_dt
                    check_out_local = check_out_utc.astimezone(tz)
                    check_out_str = check_out_local.strftime('%H:%M')
                        
            if needs_hr_confirmation:
                description = _(
                    "สร้างอัตโนมัติจาก Attendance: มาสาย %(min)d นาที ในวันที่ %(date)s\n"
                    "เวลาเข้างาน: %(check_in)s, เวลาออกงาน: %(check_out)s\n"
                    "แจ้งเตือนก่อนเริ่มงาน: %(notified)s\n"
                    "จำนวน Token ที่คาดว่าจะหัก: %(tokens)d (รอตรวจสอบ)"
                ) % {
                    "min": effective_late,
                    "date": fields.Date.to_string(att_date),
                    "check_in": check_in_str,
                    "check_out": check_out_str,
                    "notified": _("ใช่") if notified else _("ไม่"),
                    "tokens": tokens,
                }
            else:
                description = _(
                    "สร้างอัตโนมัติจาก Attendance: มาสาย %(min)d นาที ในวันที่ %(date)s\n"
                    "เวลาเข้างาน: %(check_in)s, เวลาออกงาน: %(check_out)s\n"
                    "แจ้งเตือนก่อนเริ่มงาน: %(notified)s\n"
                    "จำนวน Token ที่หัก: %(tokens)d"
                ) % {
                    "min": effective_late,
                    "date": fields.Date.to_string(att_date),
                    "check_in": check_in_str,
                    "check_out": check_out_str,
                    "notified": _("ใช่") if notified else _("ไม่"),
                    "tokens": tokens,
                }

            case_vals = {
                "employee_id": att.employee_id.id,
                "date": att_date,
                "offense_id": offense.id,
                "description": description,
                "is_attendance_auto": True,
                "lateness_minutes": effective_late,
                "attendance_id": att.id,  # Link to attendance for idempotency check
                "status": "draft" if needs_hr_confirmation else "confirmed",  # ตั้งค่า status ตามเงื่อนไข
            }
            _logger.info("Creating case with vals: employee_id=%s, date=%s, offense_id=%s, tokens=%d, needs_hr_confirmation=%s",
                        case_vals["employee_id"], case_vals["date"], case_vals["offense_id"], tokens, needs_hr_confirmation)
            new_case = Case.with_context(skip_backdate_error=True).create(case_vals)
            _logger.info("Created case ID=%s, name=%s, points=%d, status=%s",
                        new_case.id, new_case.name, new_case.points, new_case.status)
            
            # ตรวจสอบและอัปเดต Case No. ถ้ายังเป็น "/"
            if not new_case.name or new_case.name == "/":
                try:
                    company_id = new_case.company_id.id if new_case.company_id else False
                    sequence_domain = [
                        ("code", "=", "hr.discipline.case"),
                        "|",
                        ("company_id", "=", company_id),
                        ("company_id", "=", False),
                    ]
                    sequence = self.env["ir.sequence"].search(sequence_domain, limit=1)
                    if not sequence:
                        # สร้าง sequence ถ้ายังไม่มี
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
                    
                    # ใช้ next_by_code() พร้อม company_id เพื่อรองรับ multi-company
                    new_name = self.env["ir.sequence"].with_company(company_id).next_by_code("hr.discipline.case") or "/"
                    if new_name != "/":
                        new_case.write({"name": new_name})
                        _logger.info("Updated case ID=%s (company_id=%s) name from '/' to '%s'", new_case.id, company_id, new_name)
                except Exception as e:
                    _logger.error("Error updating Case No. for case ID=%s: %s", new_case.id, str(e))
            
            # ถ้าต้องการ HR confirmation ให้สร้าง case เป็น draft และเพิ่ม note
            if needs_hr_confirmation:
                new_case.message_post(
                    body=_(
                        "⚠️ <b>ต้องการการยืนยันจาก HR</b><br/>"
                        "พนักงานแจ้งเตือนก่อนเริ่มงาน แต่มาสายมากกว่า %d นาที<br/>"
                        "กรุณายืนยันว่าพนักงานแจ้งเตือนผู้บังคับบัญชาก่อนเริ่มงานหรือไม่<br/>"
                        "ถ้ายืนยัน → หัก 2 tokens, ถ้าไม่ยืนยัน → หัก 3 tokens"
                    ) % tier1_max
                )

            # Notify employee on the right-side UI
            self._notify_employee_late(
                employee=att.employee_id,
                minutes=effective_late,
                tokens=tokens,
                case=new_case,
            )
            if effective_late > tier1_max:
                self._create_employee_late_activity(
                    employee=att.employee_id,
                    minutes=effective_late,
                    tokens=tokens,
                    case=new_case,
                    attendance_id=att.id,
                    threshold_minutes=tier1_max,
                )

            # Link log to case
            log_rec.write({
                "case_id": new_case.id,
                "token_deducted": tokens,
            })

            # Confirm case (creates ledger entry) - ยกเว้นกรณีที่ต้องรอ HR confirmation
            if not needs_hr_confirmation:
                try:
                    new_case.with_context(skip_case_email=True).action_confirm()
                except Exception as e:
                    _logger.error(
                        "Failed to confirm discipline case %s for attendance %s: %s",
                        new_case.id, att.id, str(e)
                    )

            # 5) Check for management review threshold (no auto punishment, just flag/activity)
            # This is informational only - no additional token deduction
            threshold = company.lateness_repeat_threshold or 3
            period_start = self._get_period_start(company, att_date)
            period_end = self._get_period_end(company, att_date)
            
            period_lateness_count = Log.search_count([
                ("employee_id", "=", att.employee_id.id),
                ("company_id", "=", company.id),
                ("date", ">=", period_start),
                ("date", "<=", period_end),
            ])
            
            if period_lateness_count >= threshold:
                self._create_employee_repeat_activity(
                    employee=att.employee_id,
                    count=period_lateness_count,
                    threshold=threshold,
                    period_start=period_start,
                    period_end=period_end,
                )
                # Create activity for manager/HR review (optional)
                self._create_management_review_activity(att.employee_id, period_lateness_count, period_start, period_end)

            # จบการประมวลผลของ attendance นี้
            att.discipline_processed = True

    def _get_period_start(self, company, date):
        """Get start date of current token period."""
        if company.token_period_type == "weekly":
            # Weekly: start from token_period_start_day
            date_obj = fields.Date.to_date(date)
            start_day = company.token_period_start_day or 0  # 0=Monday
            days_since_monday = date_obj.weekday()
            days_to_subtract = (days_since_monday - start_day) % 7
            return date_obj - timedelta(days=days_to_subtract)
        else:
            # Monthly: start from reset_day_of_month
            date_obj = fields.Date.to_date(date)
            reset_day = company.token_reset_day_of_month or 1
            if date_obj.day >= reset_day:
                return date_class(date_obj.year, date_obj.month, reset_day)
            else:
                # Previous month
                if date_obj.month == 1:
                    return date_class(date_obj.year - 1, 12, reset_day)
                else:
                    return date_class(date_obj.year, date_obj.month - 1, reset_day)

    def _get_period_end(self, company, date):
        """Get end date of current token period."""
        if company.token_period_type == "weekly":
            period_start = self._get_period_start(company, date)
            return period_start + timedelta(days=6)
        else:
            # Monthly: end of month or day before next reset
            date_obj = fields.Date.to_date(date)
            reset_day = company.token_reset_day_of_month or 1
            if date_obj.month == 12:
                next_reset = date_class(date_obj.year + 1, 1, reset_day)
            else:
                next_reset = date_class(date_obj.year, date_obj.month + 1, reset_day)
            return next_reset - timedelta(days=1)

    def _create_management_review_activity(self, employee, count, period_start, period_end):
        """Create activity for manager/HR to review employee with multiple lateness occurrences."""
        try:
            manager = employee.parent_id
            if not manager or not manager.user_id:
                return
            
            activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
            if not activity_type:
                return

            self.env["mail.activity"].sudo().create({
                "res_model_id": self.env.ref("hr.model_hr_employee").id,
                "res_id": employee.id,
                "activity_type_id": activity_type.id,
                "summary": _("Management Review: Multiple Lateness Occurrences"),
                "note": _(
                    "Employee has %(count)d lateness occurrences in period %(start)s to %(end)s. "
                    "Please review and take appropriate action if needed."
                ) % {
                    "count": count,
                    "start": fields.Date.to_string(period_start),
                    "end": fields.Date.to_string(period_end),
                },
                "user_id": manager.user_id.id,
                "date_deadline": fields.Date.today(),
            })
        except Exception as e:
            _logger.warning(
                "Failed to create management review activity for employee %s: %s",
                employee.id, str(e)
            )
