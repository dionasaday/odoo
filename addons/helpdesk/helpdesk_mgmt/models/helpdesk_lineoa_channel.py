from odoo import fields, models


class HelpdeskLineOAChannel(models.Model):
    _name = "helpdesk.lineoa.channel"
    _description = "LINE OA Channel"
    _order = "name"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    channel_secret = fields.Char(string="Channel Secret", required=True)
    channel_access_token = fields.Char(string="Channel Access Token")
    helpdesk_team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="Helpdesk Team",
    )
    default_stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Default Stage",
    )
    create_ticket = fields.Boolean(string="Create Ticket from LINE", default=True)
    match_mode = fields.Selection(
        selection=[
            ("by_phone_or_email_in_message", "By phone/email in message"),
            ("manual_only", "Manual only"),
        ],
        string="Match Mode",
        default="by_phone_or_email_in_message",
    )
