from odoo import fields, models


class LineWebhookEvent(models.Model):
    _name = "x_line_webhook_event"
    _description = "LINE OA Webhook Event"
    _order = "received_at desc, id desc"

    received_at = fields.Datetime(default=fields.Datetime.now, required=True)
    line_user_id = fields.Char(string="LINE User ID")
    message_text = fields.Text(string="Message Text")
    lineoa_channel_id = fields.Many2one(
        comodel_name="helpdesk.lineoa.channel", string="LINE OA Channel"
    )
    matched_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Matched Partner"
    )
    created_partner_id = fields.Many2one(
        comodel_name="res.partner", string="Created Partner"
    )
    created_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket", string="Created Ticket"
    )
    processed = fields.Boolean(default=False)
    payload_snippet = fields.Text(string="Payload Snippet")
