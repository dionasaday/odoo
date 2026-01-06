# -*- coding: utf-8 -*-
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # ---- CRON ENTRY ---------------------------------------------------------
    @api.model
    def _cron_send_monthly_discipline_summary(self):
        """Entry ของ Cron: loop ทุกบริษัทแล้วส่งสรุปเดือนที่แล้ว"""
        for company in self.search([]):
            company._send_monthly_discipline_summary()

    # ---- CORE ---------------------------------------------------------------
    def _send_monthly_discipline_summary(self, date_from=None, date_to=None):
        """
        ส่งอีเมลสรุปคะแนน/การมาสาย รายเดือน ให้หัวหน้าทีมของแต่ละบริษัท
        - บังคับไม่อ่านย้อนหลังเกิน company.discipline_start_date
        - ใช้ read_group เพื่อประมวลผลเร็ว
        """
        self = self.sudo()
        Case = self.env["hr.discipline.case"].sudo()
        Log = self.env["hr.lateness.log"].sudo()
        Employee = self.env["hr.employee"].sudo()
        EmailLog = self.env["hr.discipline.email.log"]

        Template = self.env.ref(
            "onthisday_hr_discipline.mail_template_monthly_summary",
            raise_if_not_found=False,
        )

        for company in self:
            # ===== คำนวณช่วง "เดือนที่แล้ว" หากไม่ได้ส่งช่วงมา =====
            if not (date_from and date_to):
                today = fields.Date.context_today(self)
                first_this_month = date(today.year, today.month, 1)
                date_to = first_this_month - relativedelta(days=1)
                date_from = date_to.replace(day=1)

            # ===== ไม่ให้ย้อนก่อนวันเริ่มนโยบายของบริษัท =====
            start_cut = company.discipline_start_date
            if start_cut:
                # ถ้า date_to ทั้งช่วงอยู่ก่อนวันเริ่มนโยบาย -> ข้ามบริษัทนี้ไปเลย
                if date_to < start_cut:
                    continue
                # ถ้า date_from ย้อนก่อนวันเริ่ม ให้เลื่อนไปเริ่มที่วันเริ่ม
                if date_from < start_cut:
                    date_from = start_cut

            # ===== ค่ากรองนาทีที่ถือว่ามาสาย (เผื่อฟิลด์ต่างชื่อ) =====
            min_min = (
                getattr(company, "lateness_alert_min_minutes", None)
                or getattr(company, "lateness_alert_over_min", None)
                or 10
            )

            # ===== หาหัวหน้าที่มีลูกทีม (มี child_ids) =====
            managers = Employee.search([
                ("company_id", "=", company.id),
                ("child_ids", "!=", False),
            ])

            # ===== คะแนนความประพฤติ (กรองตามช่วง + ไม่ย้อนหลัง) =====
            domain_points = [
                ("employee_id.company_id", "=", company.id),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
            ]
            points_rows = Case.read_group(
                domain=domain_points,
                fields=["employee_id", "points:sum"],
                groupby=["employee_id"],
            )
            points_by_emp = {
                r["employee_id"][0]: int(r.get("points_sum") or 0)
                for r in points_rows
            }

            # ===== ข้อมูลมาสาย (รวมจำนวนครั้ง + จำนวนนาที) =====
            domain_late = [
                ("employee_id.company_id", "=", company.id),
                ("date", ">=", date_from),
                ("date", "<=", date_to),
                ("minutes", ">=", min_min),
            ]
            late_rows = Log.read_group(
                domain=domain_late,
                fields=["employee_id", "minutes:sum", "id:count"],
                groupby=["employee_id"],
            )
            late_days_by_emp = {
                r["employee_id"][0]: int(r.get("id_count") or 0) for r in late_rows
            }
            late_minutes_by_emp = {
                r["employee_id"][0]: int(r.get("minutes_sum") or 0) for r in late_rows
            }

            # ===== ส่งให้หัวหน้าทีมทีละคน =====
            for mgr in managers:
                # ลูกทีม (ทุกระดับ) ยกเว้นตัวหัวหน้าเอง
                team = Employee.search([
                    ("company_id", "=", company.id),
                    ("id", "child_of", mgr.id),
                ]) - mgr
                if not team:
                    continue

                rows = []
                for emp in team:
                    pts = points_by_emp.get(emp.id, 0)
                    days = late_days_by_emp.get(emp.id, 0)
                    mins = late_minutes_by_emp.get(emp.id, 0)
                    if pts or days:
                        rows.append({
                            "emp": emp,
                            "points": pts,
                            "late_days": days,
                            "late_minutes": mins,
                        })

                if not rows or not Template:
                    continue

                # อีเมลหัวหน้า (work_email -> user.email -> private email)
                addr = getattr(mgr, "address_home_id", False) or getattr(mgr, "address_id", False)
                email_to = (
                    mgr.work_email
                    or (mgr.user_id and mgr.user_id.email)
                    or (addr and addr.email)
                    or ""
                )
                if not email_to:
                    continue

                email_values = EmailLog._prepare_email_values(email_to, manager=mgr)
                try:
                    Template.sudo().with_context(
                        manager=mgr,
                        period_from=date_from,
                        period_to=date_to,
                        min_min=min_min,
                        summary_rows=rows,
                    ).send_mail(
                        company.id,
                        force_send=True,
                        email_values=email_values,
                    )
                    EmailLog._log_email(
                        Template.model or "res.company",
                        company.id,
                        Template,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                    )
                except Exception:
                    EmailLog._log_email(
                        Template.model or "res.company",
                        company.id,
                        Template,
                        email_values.get("email_to"),
                        email_values.get("email_cc"),
                        state="failed",
                    )
