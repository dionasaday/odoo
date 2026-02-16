from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HelpdeskTicketStage(models.Model):
    _name = "helpdesk.ticket.stage"
    _description = "Helpdesk Ticket Stage"
    _order = "sequence, id"

    name = fields.Char(string="Stage Name", required=True, translate=True)
    description = fields.Html(translate=True, sanitize_style=True)
    sequence = fields.Integer(default=1)
    x_sla_hours = fields.Float(string="SLA Hours")
    x_notify_customer_email = fields.Boolean(string="Notify Customer by Email")
    x_notify_customer_line = fields.Boolean(string="Notify Customer by LINE")
    x_email_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Customer Email Template",
        domain=[("model", "=", "helpdesk.ticket")],
    )
    x_line_message_template = fields.Text(string="LINE Message Template")
    active = fields.Boolean(default=True)
    unattended = fields.Boolean()
    closed = fields.Boolean()
    close_from_portal = fields.Boolean(
        help="Display button in portal ticket form to allow closing ticket "
        "with this stage as target."
    )
    mail_template_id = fields.Many2one(
        comodel_name="mail.template",
        string="Email Template",
        domain=[("model", "=", "helpdesk.ticket")],
        help="If set an email will be sent to the "
        "customer when the ticket"
        "reaches this step.",
    )
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="This stage is folded in the kanban view "
        "when there are no records in that stage "
        "to display.",
    )
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    team_ids = fields.Many2many(
        comodel_name="helpdesk.ticket.team",
        string="Helpdesk Teams",
        help="Specific team that uses this stage. If it is empty all teams could uses",
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]",
    )

    @api.onchange("closed")
    def _onchange_closed(self):
        if not self.closed:
            self.close_from_portal = False

    def unlink(self):
        team_id = (
            self.env.context.get("default_team_id")
            or self.env.context.get("team_id")
        )
        Ticket = self.env["helpdesk.ticket"].sudo()
        Stage = self.env["helpdesk.ticket.stage"].sudo()

        stages_to_delete = Stage.browse()
        for stage in self:
            if team_id and not stage.team_ids:
                other_team_ids = self.env["helpdesk.ticket.team"].sudo().search(
                    [
                        ("company_id", "in", [False, stage.company_id.id if stage.company_id else self.env.company.id]),
                        ("id", "!=", team_id),
                    ]
                ).ids
                if other_team_ids:
                    stage.sudo().team_ids = [(6, 0, other_team_ids)]
                    tickets = Ticket.search(
                        [("stage_id", "=", stage.id), ("team_id", "=", team_id)]
                    )
                    if tickets:
                        company_id = (
                            stage.company_id.id if stage.company_id else self.env.company.id
                        )
                        fallback_stage = Stage.search(
                            [
                                ("company_id", "in", [False, company_id]),
                                "|",
                                ("team_ids", "=", team_id),
                                ("team_ids", "=", False),
                                ("id", "!=", stage.id),
                            ],
                            order="sequence,id",
                            limit=1,
                        )
                        if not fallback_stage:
                            raise UserError(
                                _(
                                    "Cannot remove stage '%s' from this team because no other "
                                    "stage is available. Please create another stage first."
                                )
                                % stage.name
                            )
                        tickets.write({"stage_id": fallback_stage.id})
                    continue

            if (
                team_id
                and stage.team_ids
                and team_id in stage.team_ids.ids
                and len(stage.team_ids) > 1
            ):
                stage.sudo().team_ids = [(3, team_id)]
                continue

            tickets = Ticket.search([("stage_id", "=", stage.id)])
            if tickets:
                company_id = stage.company_id.id if stage.company_id else self.env.company.id
                fallback_stage = False
                if team_id:
                    fallback_stage = Stage.search(
                        [
                            ("company_id", "in", [False, company_id]),
                            ("team_ids", "=", team_id),
                            ("id", "not in", self.ids),
                        ],
                        order="sequence,id",
                        limit=1,
                    )
                if not fallback_stage:
                    fallback_stage = Stage.search(
                        [
                            ("company_id", "in", [False, company_id]),
                            ("team_ids", "=", False),
                            ("id", "not in", self.ids),
                        ],
                        order="sequence,id",
                        limit=1,
                    )
                if not fallback_stage:
                    raise UserError(
                        _(
                            "Cannot delete stage '%s' because it has tickets. "
                            "Please create another stage first."
                        )
                        % stage.name
                    )
                tickets.write({"stage_id": fallback_stage.id})

            stages_to_delete |= stage

        return super(HelpdeskTicketStage, stages_to_delete).unlink()
