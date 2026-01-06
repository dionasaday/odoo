# -*- coding: utf-8 -*-

from odoo import api, fields, models


DEFAULT_CC_EMAIL = "nattapon.s@onthisdayco.com"


class HrDisciplineEmailLog(models.Model):
    _name = "hr.discipline.email.log"
    _description = "Discipline Email Log"
    _order = "sent_at desc, id desc"
    _rec_name = "subject"

    sent_at = fields.Datetime(
        string="Sent At",
        default=fields.Datetime.now,
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
        index=True,
    )
    res_model = fields.Char(string="Model", required=True, index=True)
    res_id = fields.Integer(string="Record ID", required=True, index=True)
    template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Template",
    )
    subject = fields.Char(string="Subject")
    email_to = fields.Char(string="Email To")
    email_cc = fields.Char(string="Email CC")
    state = fields.Selection(
        selection=[("sent", "Sent"), ("failed", "Failed")],
        string="Status",
        default="sent",
        required=True,
    )
    error_message = fields.Text(string="Error")

    @api.model
    def _get_employee_email(self, employee):
        if not employee:
            return False
        employee = employee.sudo()
        addr = getattr(employee, "address_home_id", False) or getattr(employee, "address_id", False)
        return (
            employee.work_email
            or (employee.user_id and employee.user_id.email)
            or (addr and addr.email)
            or False
        )

    @api.model
    def _normalize_emails(self, emails):
        if not emails:
            return []
        if isinstance(emails, str):
            raw = emails.replace(";", ",").split(",")
        elif isinstance(emails, (list, tuple, set)):
            raw = []
            for item in emails:
                if not item:
                    continue
                if isinstance(item, str):
                    raw.extend(item.replace(";", ",").split(","))
                else:
                    raw.append(str(item))
        else:
            raw = [str(emails)]
        cleaned = []
        seen = set()
        for item in raw:
            value = (item or "").strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(value)
        return cleaned

    @api.model
    def _prepare_email_values(self, email_to, manager=None, extra_cc=None):
        to_list = self._normalize_emails(email_to)
        cc_list = self._normalize_emails(extra_cc)
        default_cc = self._normalize_emails(DEFAULT_CC_EMAIL)
        cc_list.extend(default_cc)
        if manager:
            mgr_email = self._get_employee_email(manager)
            if mgr_email:
                cc_list.append(mgr_email)
        cc_list = self._normalize_emails(cc_list)
        to_lower = {email.lower() for email in to_list}
        cc_list = [email for email in cc_list if email.lower() not in to_lower]
        return {
            "email_to": ",".join(to_list) if to_list else False,
            "email_cc": ",".join(cc_list) if cc_list else False,
        }

    @api.model
    def _log_email(self, res_model, res_id, template, email_to, email_cc, state="sent", error_message=None):
        subject = False
        template_id = False
        if template:
            template_id = template.id
            try:
                rendered = template._render_field("subject", [res_id])
                subject = rendered.get(res_id) if rendered else template.subject
            except Exception:
                subject = template.subject
        return self.sudo().create({
            "res_model": res_model,
            "res_id": res_id,
            "template_id": template_id,
            "subject": subject,
            "email_to": email_to or False,
            "email_cc": email_cc or False,
            "state": state,
            "error_message": error_message,
        })
