from datetime import timedelta

from odoo import api, fields, models


class HelpdeskFollowupEvent(models.Model):
    _name = "helpdesk.followup.event"
    _description = "Helpdesk Follow-up Event"
    _order = "trigger_at desc, id desc"

    ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket", required=True, index=True
    )
    team_id = fields.Many2one(
        related="ticket_id.team_id", store=True, index=True, readonly=True
    )
    policy_id = fields.Many2one(
        comodel_name="helpdesk.followup.policy", required=True, index=True
    )
    open_event_key = fields.Char(
        compute="_compute_open_event_key",
        store=True,
        index=True,
        precompute=True,
    )
    trigger_at = fields.Datetime(required=True, default=fields.Datetime.now)
    followup_created_at = fields.Datetime()
    followup_created_date = fields.Date(
        compute="_compute_followup_created_date", store=True
    )
    followup_done_at = fields.Datetime()
    followup_activity_id = fields.Many2one(comodel_name="mail.activity")
    assigned_user_id = fields.Many2one(comodel_name="res.users")
    due_date = fields.Date()
    escalation_created_at = fields.Datetime()
    overdue_notified_at = fields.Datetime()
    escalation_notified_at = fields.Datetime()
    escalation_activity_id = fields.Many2one(comodel_name="mail.activity")
    escalated_to_user_id = fields.Many2one(comodel_name="res.users")
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("done", "Done"),
            ("escalated", "Escalated"),
        ],
        default="pending",
    )
    is_done = fields.Boolean(compute="_compute_is_done", store=True)
    is_escalated = fields.Boolean(compute="_compute_is_escalated", store=True)
    response_time_hours = fields.Float(
        compute="_compute_response_time_hours", store=True
    )
    completion_rate = fields.Float(
        compute="_compute_completion_rate", store=True
    )
    escalation_count = fields.Float(
        compute="_compute_escalation_count", store=True
    )

    _sql_constraints = [
        (
            "helpdesk_followup_event_open_uniq",
            "unique(open_event_key)",
            "An open follow-up event already exists for this ticket and policy.",
        )
    ]

    @api.depends("followup_created_at")
    def _compute_followup_created_date(self):
        for event in self:
            event.followup_created_date = (
                fields.Date.to_date(event.followup_created_at)
                if event.followup_created_at
                else False
            )

    @api.depends("ticket_id", "policy_id", "state")
    def _compute_open_event_key(self):
        for event in self:
            if event.state in ("pending", "escalated") and event.ticket_id and event.policy_id:
                event.open_event_key = f"{event.ticket_id.id}:{event.policy_id.id}"
            else:
                event.open_event_key = False

    @api.depends("followup_done_at")
    def _compute_is_done(self):
        for event in self:
            event.is_done = bool(event.followup_done_at)

    @api.depends("escalation_created_at")
    def _compute_is_escalated(self):
        for event in self:
            event.is_escalated = bool(event.escalation_created_at)

    @api.depends("followup_created_at", "followup_done_at")
    def _compute_response_time_hours(self):
        for event in self:
            if event.followup_created_at and event.followup_done_at:
                delta = event.followup_done_at - event.followup_created_at
                event.response_time_hours = max(0.0, delta.total_seconds() / 3600.0)
            else:
                event.response_time_hours = 0.0

    @api.depends("followup_done_at")
    def _compute_completion_rate(self):
        for event in self:
            event.completion_rate = 100.0 if event.followup_done_at else 0.0

    @api.depends("escalation_created_at")
    def _compute_escalation_count(self):
        for event in self:
            event.escalation_count = 1.0 if event.escalation_created_at else 0.0

    def _render_template(self, template, ticket, trigger_at):
        values = {
            "ticket_name": ticket.name or "",
            "ticket_id": ticket.number or str(ticket.id),
            "customer_name": ticket.partner_id.name if ticket.partner_id else "",
            "trigger_date": fields.Datetime.context_timestamp(ticket, trigger_at).strftime(
                "%Y-%m-%d %H:%M"
            )
            if trigger_at
            else "",
            "ticket_url": ticket._ticket_url(),
        }
        message = template or ""
        for key, val in values.items():
            message = message.replace("{" + key + "}", str(val or ""))
        return message

    @api.model
    def _cron_create_followups(self):
        now = fields.Datetime.now()
        pending_domain = [
            ("state", "=", "pending"),
            ("followup_created_at", "=", False),
        ]
        min_wait = 0
        policies = self.env["helpdesk.followup.policy"].search([("active", "=", True)])
        if policies:
            min_wait = min(policies.mapped("wait_days") or [0])
        if min_wait:
            pending_domain.append(
                ("trigger_at", "<=", now - timedelta(days=min_wait))
            )
        pending = self.search(pending_domain)
        for event in pending:
            policy = event.policy_id
            if not policy:
                continue
            wait_days = max(policy.wait_days or 0, 0)
            if event.trigger_at and event.trigger_at > now - timedelta(days=wait_days):
                continue
            ticket = event.ticket_id
            if not ticket or ticket.closed:
                event.write({"state": "done", "followup_done_at": now})
                continue
            if policy.target_stage_id:
                ticket.with_context(skip_followup=True).write(
                    {"stage_id": policy.target_stage_id.id}
                )
            assignee = (
                event.assigned_user_id
                or policy.default_assignee_user_id
                or ticket.user_id
            )
            activity_type = policy.activity_type_id
            if not activity_type:
                continue
            summary = policy.summary or "Follow-up"
            note = self._render_template(policy.note_template, ticket, event.trigger_at)
            due_days = max(policy.due_days or 0, 0)
            deadline = fields.Date.context_today(ticket) + timedelta(days=due_days)
            activity = ticket.activity_schedule(
                activity_type_id=activity_type.id,
                summary=summary,
                note=note,
                user_id=assignee.id if assignee else False,
                date_deadline=deadline,
            )
            event.write(
                {
                    "followup_created_at": now,
                    "followup_activity_id": activity.id,
                    "assigned_user_id": assignee.id if assignee else False,
                    "due_date": deadline,
                }
            )

    @api.model
    def _cron_escalate_overdue(self):
        now = fields.Datetime.now()
        pending_domain = [
            ("state", "=", "pending"),
            ("followup_created_at", "!=", False),
            ("followup_done_at", "=", False),
        ]
        policies = self.env["helpdesk.followup.policy"].search(
            [("active", "=", True), ("enable_escalation", "=", True)]
        )
        min_overdue = 0
        if policies:
            min_overdue = min(policies.mapped("escalation_after_overdue_days") or [0])
        if min_overdue:
            pending_domain.append(
                ("due_date", "<=", fields.Date.context_today(self) - timedelta(days=min_overdue))
            )
        pending = self.search(pending_domain)
        for event in pending:
            policy = event.policy_id
            if not policy or not policy.enable_escalation:
                continue
            if event.escalation_activity_id:
                continue
            if not event.due_date:
                continue
            overdue_days = max(policy.escalation_after_overdue_days or 0, 0)
            threshold = event.due_date + timedelta(days=overdue_days)
            if fields.Date.context_today(event) < threshold:
                continue
            ticket = event.ticket_id
            if not ticket or ticket.closed:
                continue
            assignee = policy.escalation_user_id or event.assigned_user_id
            activity_type = policy.escalation_activity_type_id or policy.activity_type_id
            if not activity_type:
                continue
            summary = policy.escalation_summary or "Escalation"
            note = self._render_template(policy.escalation_note_template, ticket, event.trigger_at)
            activity = ticket.activity_schedule(
                activity_type_id=activity_type.id,
                summary=summary,
                note=note,
                user_id=assignee.id if assignee else False,
                date_deadline=fields.Date.context_today(ticket),
            )
            event.write(
                {
                    "escalation_created_at": now,
                    "escalation_activity_id": activity.id,
                    "escalated_to_user_id": assignee.id if assignee else False,
                    "state": "escalated",
                }
            )
            if not event.escalation_notified_at:
                self._send_escalation_email(event, assignee)
                event.write({"escalation_notified_at": now})

    def _send_overdue_email(self, event):
        ticket = event.ticket_id
        if not ticket:
            return
        policy = event.policy_id
        assignee = (
            event.assigned_user_id
            or (policy.default_assignee_user_id if policy else False)
            or ticket.user_id
        )
        if not assignee or not assignee.email:
            return
        recipient_name = self._get_user_display_name(assignee) or assignee.name
        subject = f"[Overdue Reminder] {ticket.display_name or ticket.name}"
        due_date = event.due_date or ""
        body = (
            f"<p>Hello {recipient_name},</p>"
            f"<p>The follow-up activity for ticket "
            f"<strong>{ticket.display_name or ticket.name}</strong> "
            f"is overdue (due date: <strong>{due_date}</strong>).</p>"
            f"<p><a href=\"{ticket._ticket_url()}\">Open Ticket</a></p>"
        )
        self.env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": assignee.email,
            }
        ).send()

    def _send_escalation_email(self, event, assignee):
        ticket = event.ticket_id
        if not ticket:
            return
        if not assignee or not assignee.email:
            return
        ticket_id_label = ticket.number or str(ticket.id)
        ticket_name = ticket.name or ""
        customer_name = ticket.partner_id.name if ticket.partner_id else ""
        policy = event.policy_id
        assigned_user = (
            event.assigned_user_id
            or (policy.default_assignee_user_id if policy else False)
            or ticket.user_id
        )
        assigned_user_name = self._get_user_display_name(assigned_user)
        today = fields.Date.context_today(ticket)
        overdue_days = 0
        if event.due_date:
            overdue_days = max((today - event.due_date).days, 0)
        due_date = event.due_date or ""
        followup_wait_days = policy.wait_days if policy else 0

        recipient_name = self._get_user_display_name(assignee) or assignee.name
        subject = (
            f"[Escalation] Follow-up เกินกำหนด – {ticket_id_label} {ticket_name}"
        )
        body = (
            f"<p>เรียน {recipient_name},</p>"
            f"<p>Follow-up Activity สำหรับเคส "
            f"<strong>{ticket_id_label} – {ticket_name}</strong><br/>"
            f"ยังไม่ได้รับการดำเนินการภายใน SLA ที่กำหนด</p>"
            f"<ul>"
            f"<li>ลูกค้า: {customer_name}</li>"
            f"<li>ผู้รับผิดชอบ: {assigned_user_name}</li>"
            f"<li>SLA Follow-up: {followup_wait_days} วัน</li>"
            f"<li>เกินกำหนด: {overdue_days} วัน</li>"
            f"<li>กำหนดเสร็จ: {due_date}</li>"
            f"</ul>"
            f"<p>เพื่อรักษามาตรฐานบริการของ On This Day "
            f"กรุณาตรวจสอบและดำเนินการโดยเร็ว</p>"
            f"<p>เปิดเคส: <a href=\"{ticket._ticket_url()}\">{ticket._ticket_url()}</a></p>"
        )
        self.env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": assignee.email,
            }
        ).send()

    def _get_user_display_name(self, user):
        if not user:
            return ""
        employee = False
        if hasattr(user, "employee_id"):
            employee = user.employee_id
        if not employee and hasattr(user, "employee_ids") and user.employee_ids:
            employee = user.employee_ids[:1]
        if employee and employee.name:
            return employee.name
        if user.name:
            return user.name
        if user.partner_id and user.partner_id.name:
            return user.partner_id.name
        return ""

    @api.model
    def _cron_notify_overdue_followups(self):
        today = fields.Date.context_today(self)
        domain = [
            ("state", "in", ["pending", "escalated"]),
            ("followup_created_at", "!=", False),
            ("followup_done_at", "=", False),
            ("due_date", "!=", False),
            ("overdue_notified_at", "=", False),
            ("due_date", "<", today),
        ]
        events = self.search(domain)
        now = fields.Datetime.now()
        for event in events:
            self._send_overdue_email(event)
            event.write({"overdue_notified_at": now})
