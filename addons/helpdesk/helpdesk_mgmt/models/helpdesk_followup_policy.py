from odoo import fields, models
from odoo.tools.safe_eval import safe_eval


class HelpdeskFollowupPolicy(models.Model):
    _name = "helpdesk.followup.policy"
    _description = "Helpdesk Follow-up Policy"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    team_id = fields.Many2one(comodel_name="helpdesk.ticket.team", string="Team")
    tag_ids = fields.Many2many(comodel_name="helpdesk.ticket.tag", string="Tags")
    domain_filter = fields.Text(string="Domain Filter")

    trigger_stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Trigger Stage",
        required=True,
    )
    wait_days = fields.Integer(default=3)
    target_stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Target Stage",
    )

    activity_type_id = fields.Many2one(
        comodel_name="mail.activity.type", string="Activity Type", required=True
    )
    summary = fields.Char(
        default="Follow-up ลูกค้าหลังส่งมอบ",
    )
    note_template = fields.Text(
        string="Note Template",
        default="ติดตามงาน {ticket_name} ของ {customer_name} (วันที่ {trigger_date})\n{ticket_url}",
    )
    default_assignee_user_id = fields.Many2one(
        comodel_name="res.users", string="Default Assignee"
    )
    due_days = fields.Integer(default=2)

    enable_escalation = fields.Boolean(string="Enable Escalation")
    escalation_after_overdue_days = fields.Integer(default=2)
    escalation_user_id = fields.Many2one(
        comodel_name="res.users", string="Escalation User"
    )
    escalation_activity_type_id = fields.Many2one(
        comodel_name="mail.activity.type", string="Escalation Activity Type"
    )
    escalation_summary = fields.Char(
        default="Escalation: Follow-up overdue",
    )
    escalation_note_template = fields.Text(
        string="Escalation Note Template",
        default="Follow-up overdue for {ticket_name} ({ticket_id}).\n{ticket_url}",
    )

    def _safe_domain(self):
        self.ensure_one()
        if not self.domain_filter:
            return []
        try:
            domain = safe_eval(self.domain_filter, {})
        except Exception:
            return []
        if isinstance(domain, (list, tuple)):
            return list(domain)
        return []

    def _matches_ticket(self, ticket):
        self.ensure_one()
        if self.team_id and ticket.team_id != self.team_id:
            return False
        if self.tag_ids and not (set(ticket.tag_ids.ids) & set(self.tag_ids.ids)):
            return False
        domain = self._safe_domain()
        if domain:
            return bool(
                ticket.sudo().search_count([("id", "=", ticket.id)] + domain)
            )
        return True
