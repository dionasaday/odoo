# Copyright 2022 Tecnativa - Víctor Martínez
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    @api.model
    def _default_line_team(self):
        return (
            self.env["helpdesk.ticket.team"].search([("name", "=", "LINE OA")], limit=1).id
        )

    @api.model
    def _default_line_stage(self):
        return (
            self.env["helpdesk.ticket.stage"].search([("name", "=", "New")], limit=1).id
        )

    helpdesk_mgmt_portal_select_team = fields.Boolean(
        related="company_id.helpdesk_mgmt_portal_select_team",
        readonly=False,
    )
    helpdesk_mgmt_portal_team_id_required = fields.Boolean(
        related="company_id.helpdesk_mgmt_portal_team_id_required",
        readonly=False,
    )
    helpdesk_mgmt_portal_category_id_required = fields.Boolean(
        related="company_id.helpdesk_mgmt_portal_category_id_required",
        readonly=False,
    )
    helpdesk_mgmt_duplicate_tracking = fields.Boolean(
        related="company_id.helpdesk_mgmt_duplicate_tracking", readonly=False
    )
    helpdesk_mgmt_duplicate_ticket_stage_id = fields.Many2one(
        related="company_id.helpdesk_mgmt_duplicate_ticket_stage_id", readonly=False
    )
    helpdesk_mgmt_ticket_auto_assign = fields.Boolean(
        related="company_id.helpdesk_mgmt_ticket_auto_assign",
        readonly=False,
    )

    lineoa_enabled = fields.Boolean(
        string="Enable LINE OA",
        config_parameter="helpdesk_mgmt.lineoa_enabled",
    )
    lineoa_channel_access_token = fields.Char(
        string="LINE OA Channel Access Token",
        config_parameter="helpdesk_mgmt.lineoa_channel_access_token",
    )
    lineoa_channel_secret = fields.Char(
        string="LINE OA Channel Secret",
        config_parameter="helpdesk_mgmt.lineoa_channel_secret",
    )
    lineoa_webhook_path = fields.Char(
        string="LINE OA Webhook Path",
        config_parameter="helpdesk_mgmt.lineoa_webhook_path",
        default="/line/webhook/otd",
    )
    lineoa_create_ticket = fields.Boolean(
        string="Create Ticket from LINE",
        config_parameter="helpdesk_mgmt.lineoa_create_ticket",
        default=True,
    )
    lineoa_helpdesk_team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="LINE OA Helpdesk Team",
        config_parameter="helpdesk_mgmt.lineoa_helpdesk_team_id",
        default=_default_line_team,
    )
    lineoa_default_stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="LINE OA Default Stage",
        config_parameter="helpdesk_mgmt.lineoa_default_stage_id",
        default=_default_line_stage,
    )
    lineoa_match_mode = fields.Selection(
        selection=[
            ("by_phone_or_email_in_message", "By phone/email in message"),
            ("manual_only", "Manual only"),
        ],
        string="LINE OA Match Mode",
        config_parameter="helpdesk_mgmt.lineoa_match_mode",
        default="by_phone_or_email_in_message",
    )
    helpdesk_email_enabled = fields.Boolean(
        string="Enable Customer Email",
        config_parameter="helpdesk_mgmt.helpdesk_email_enabled",
        default=True,
    )
