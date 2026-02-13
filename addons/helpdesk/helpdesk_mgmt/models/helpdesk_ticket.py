from odoo import api, fields, models, tools
from odoo.exceptions import AccessError


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _rec_name = "number"
    _rec_names_search = ["number", "name", "purchase_order_number"]
    _order = "priority desc, sequence, number desc, id desc"
    _mail_post_access = "read"
    _inherit = [
        "mail.thread.cc",
        "mail.activity.mixin",
        "portal.mixin",
        "mail.tracking.duration.mixin",
    ]
    _track_duration_field = "stage_id"

    @api.depends("team_id")
    def _compute_stage_id(self):
        """Compute default stage based on team."""
        for ticket in self:
            if ticket.team_id:
                stages = ticket.team_id._get_applicable_stages()
                ticket.stage_id = stages[:1] if stages else False
            else:
                ticket.stage_id = False

    @api.depends("team_id")
    def _compute_user_id(self):
        for ticket in self:
            if ticket.team_id and ticket.user_id not in ticket.team_id.user_ids:
                # If the user is not part of the team, we remove the user
                ticket.user_id = False

    @api.depends("user_id")
    def _compute_team_id(self):
        for ticket in self:
            if not ticket.team_id and ticket.user_id.helpdesk_team_ids:
                # If no team is set, we default to the user's first team
                ticket.team_id = ticket.user_id.helpdesk_team_ids[0]

    @api.model
    def _read_group_stage_ids(self, stages, domain):
        """Show always the stages without team, or stages of the default team."""
        search_domain = [
            "|",
            ("id", "in", stages.ids),
            ("team_ids", "=", False),
        ]
        default_team_id = self.default_get(["team_id"])
        if default_team_id:
            search_domain = [
                "|",
                ("team_ids", "=", default_team_id["team_id"]),
            ] + search_domain
        return stages.search(search_domain)

    @api.depends("duplicate_ids")
    def _compute_duplicate_count(self):
        for record in self:
            record.duplicate_count = len(record.duplicate_ids)

    @api.depends("create_date")
    def _compute_total_days(self):
        now = fields.Datetime.now()
        for ticket in self:
            if ticket.create_date:
                start = fields.Datetime.context_timestamp(ticket, ticket.create_date)
                end = fields.Datetime.context_timestamp(ticket, now)
                delta = end - start
                ticket.x_total_days = max(0, delta.days)
            else:
                ticket.x_total_days = 0

    @api.depends("x_stage_entered_at", "last_stage_update", "create_date")
    def _compute_stage_hours(self):
        now = fields.Datetime.now()
        for ticket in self:
            entered_at = (
                ticket.x_stage_entered_at
                or ticket.last_stage_update
                or ticket.create_date
            )
            if entered_at:
                start = fields.Datetime.context_timestamp(ticket, entered_at)
                end = fields.Datetime.context_timestamp(ticket, now)
                delta = end - start
                ticket.x_stage_hours = max(0.0, delta.total_seconds() / 3600.0)
            else:
                ticket.x_stage_hours = 0.0

    @api.depends("x_stage_hours", "stage_id.x_sla_hours")
    def _compute_sla_status(self):
        for ticket in self:
            sla_hours = ticket.stage_id.x_sla_hours or 0.0
            if sla_hours <= 0:
                ticket.x_sla_status = "safe"
                continue
            ratio = ticket.x_stage_hours / sla_hours
            if ratio < 0.7:
                ticket.x_sla_status = "safe"
            elif ratio < 1:
                ticket.x_sla_status = "warning"
            else:
                ticket.x_sla_status = "danger"

    @api.depends("x_last_update_at", "create_date")
    def _compute_no_update_warning(self):
        now = fields.Datetime.now()
        for ticket in self:
            last = ticket.x_last_update_at or ticket.create_date
            if last:
                start = fields.Datetime.context_timestamp(ticket, last)
                end = fields.Datetime.context_timestamp(ticket, now)
                hours = max(0.0, (end - start).total_seconds() / 3600.0)
                ticket.x_no_update_warning = hours >= 48.0
            else:
                ticket.x_no_update_warning = False

    number = fields.Char(string="Ticket number", default="/", readonly=True)
    name = fields.Char(string="Title", required=True)
    purchase_order_number = fields.Char(string="เลขคำสั่งซื้อ", required=True)
    description = fields.Html(required=True, sanitize_style=True)
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Assigned user",
        tracking=True,
        index=True,
        compute="_compute_user_id",
        store=True,
        readonly=False,
        domain="team_id and [('share', '=', False),('id', 'in', user_ids)] or [('share', '=', False)]",  # noqa: B950,E501
    )
    assigned_user_ids = fields.Many2many(
        comodel_name="res.users",
        string="Assigned user",
        tracking=True,
        domain="team_id and [('share', '=', False),('id', 'in', user_ids)] or [('share', '=', False)]",  # noqa: B950,E501
    )
    user_ids = fields.Many2many(
        comodel_name="res.users", related="team_id.user_ids", string="Users"
    )
    stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Stage",
        compute="_compute_stage_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        tracking=True,
        group_expand="_read_group_stage_ids",
        copy=False,
        index=True,
        domain="['|',('team_ids', '=', team_id),('team_ids','=',False)]",
    )
    x_total_days = fields.Integer(
        string="Total Days", compute="_compute_total_days", store=True
    )
    x_stage_entered_at = fields.Datetime(string="Stage Entered At", store=True)
    x_stage_hours = fields.Float(string="Stage Hours", compute="_compute_stage_hours")
    x_sla_status = fields.Selection(
        selection=[
            ("safe", "Safe"),
            ("warning", "Warning"),
            ("danger", "Danger"),
        ],
        string="SLA Status",
        compute="_compute_sla_status",
    )
    x_no_update_warning = fields.Boolean(
        string="No Update > 48h", compute="_compute_no_update_warning"
    )
    x_last_update_at = fields.Datetime(string="Last Update At", copy=False)
    partner_id = fields.Many2one(comodel_name="res.partner", string="Contact")
    commercial_partner_id = fields.Many2one(
        string="Commercial Partner",
        store=True,
        related="partner_id.commercial_partner_id",
    )
    partner_name = fields.Char()
    partner_email = fields.Char(string="Email")
    last_stage_update = fields.Datetime(default=fields.Datetime.now)
    assigned_date = fields.Datetime()
    closed_date = fields.Datetime()
    closed = fields.Boolean(related="stage_id.closed")
    unattended = fields.Boolean(related="stage_id.unattended", store=True)
    tag_ids = fields.Many2many(comodel_name="helpdesk.ticket.tag", string="Tags")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    channel_id = fields.Many2one(
        comodel_name="helpdesk.ticket.channel",
        string="Channel",
        required=True,
        help="Channel indicates where the source of a ticket"
        "comes from (it could be a phone call, an email...)",
    )
    category_id = fields.Many2one(
        comodel_name="helpdesk.ticket.category",
        string="Category",
    )
    team_id = fields.Many2one(
        comodel_name="helpdesk.ticket.team",
        string="Team",
        index=True,
        compute="_compute_team_id",
        store=True,
        readonly=False,
    )
    priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
    )
    attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "helpdesk.ticket")],
        string="Media Attachments",
    )
    color = fields.Integer(string="Color Index")
    kanban_state = fields.Selection(
        selection=[
            ("normal", "Default"),
            ("done", "Ready for next stage"),
            ("blocked", "Blocked"),
        ],
    )
    sequence = fields.Integer(
        index=True,
        default=10,
        help="Gives the sequence order when displaying a list of tickets.",
    )
    active = fields.Boolean(default=True)

    duplicate_id = fields.Many2one(
        "helpdesk.ticket", string="Duplicate of", tracking=True, copy=False
    )
    duplicate_ids = fields.One2many(
        "helpdesk.ticket", "duplicate_id", string="Duplicate tickets"
    )
    duplicate_count = fields.Integer(compute="_compute_duplicate_count")
    duplicate_tracking_enabled = fields.Boolean(
        related="company_id.helpdesk_mgmt_duplicate_tracking"
    )

    def action_open_duplicate_wizard(self):
        self.ensure_one()
        target_stage = self.env.company.helpdesk_mgmt_duplicate_ticket_stage_id
        return {
            "name": "Mark as Duplicate",
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket.duplicate.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_ticket_id": self.id,
                "default_target_stage_id": target_stage.id,
            },
        }

    def action_view_duplicates(self):
        self.ensure_one()
        return {
            "name": "Duplicates",
            "type": "ir.actions.act_window",
            "res_model": "helpdesk.ticket",
            "view_mode": "list",
            "target": "new",
            "domain": [("duplicate_id", "=", self.id)],
        }

    @api.model
    def default_get(self, fields):
        # The appropriate user is defined only if the "Auto assign User" option is
        # checked in the company.
        # If the team is set, the user must belong to that team.
        defaults = super().default_get(fields)
        company_id = defaults.get("company_id") or self.env.company.id
        if "user_id" in fields and not defaults.get("user_id"):
            company = self.env["res.company"].browse(company_id)
            if company.helpdesk_mgmt_ticket_auto_assign:
                if defaults.get("team_id"):
                    team = self.env["helpdesk.ticket.team"].browse(
                        defaults.get("team_id")
                    )
                    if self.env.user in team.user_ids:
                        defaults["user_id"] = self.env.user.id
                else:
                    defaults["user_id"] = self.env.user.id
        return defaults

    @api.depends("name")
    def _compute_display_name(self):
        for ticket in self:
            ticket.display_name = f"{ticket.number} - {ticket.name}"

    def assign_to_me(self):
        self.write({"user_id": self.env.user.id})

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.partner_name = self.partner_id.name
            self.partner_email = self.partner_id.email

    @api.onchange("user_id")
    def _onchange_user_id(self):
        if self.user_id and self.user_id not in self.assigned_user_ids:
            self.assigned_user_ids = self.assigned_user_ids | self.user_id

    @api.onchange("assigned_user_ids")
    def _onchange_assigned_user_ids(self):
        if self.assigned_user_ids and self.user_id not in self.assigned_user_ids:
            self.user_id = self.assigned_user_ids[0]
        elif not self.assigned_user_ids:
            self.user_id = False

    @api.onchange("team_id")
    def _onchange_team_id(self):
        if self.team_id and self.assigned_user_ids:
            self.assigned_user_ids = self.assigned_user_ids & self.team_id.user_ids

    # ---------------------------------------------------
    # CRUD
    # ---------------------------------------------------

    def _creation_subtype(self):
        return self.env.ref("helpdesk_mgmt.hlp_tck_created")

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get("number", "/") == "/":
                vals["number"] = self._prepare_ticket_number(vals)
            if vals.get("user_id") and not vals.get("assigned_date"):
                vals["assigned_date"] = fields.Datetime.now()
            if vals.get("team_id"):
                team = self.env["helpdesk.ticket.team"].browse([vals["team_id"]])
                if team.company_id:
                    vals["company_id"] = team.company_id.id
                if "stage_id" not in vals:
                    # Ensure that stage_id is set before creating the ticket
                    # so that the field is tracked correctly
                    # and notifications can be sent by email
                    # if a mail template is configured
                    vals["stage_id"] = team._get_applicable_stages()[:1].id
            # Automatically set default e-mail channel when created from the
            # fetchmail cron task
            if self.env.context.get("fetchmail_cron_running") and not vals.get(
                "channel_id"
            ):
                channel_email_id = self.env.ref(
                    "helpdesk_mgmt.helpdesk_ticket_channel_email",
                    raise_if_not_found=False,
                )
                if channel_email_id:
                    vals["channel_id"] = channel_email_id.id
            # Fallback channel for programmatic creates without explicit channel
            if not vals.get("channel_id"):
                channel_other_id = self.env.ref(
                    "helpdesk_mgmt.helpdesk_ticket_channel_other",
                    raise_if_not_found=False,
                )
                if channel_other_id:
                    vals["channel_id"] = channel_other_id.id
            if not vals.get("x_stage_entered_at"):
                vals["x_stage_entered_at"] = fields.Datetime.now()
            if not vals.get("x_last_update_at"):
                vals["x_last_update_at"] = now
        records = super().create(vals_list)
        if not self.env.context.get("skip_assignment_email"):
            for record in records:
                assigned_users = set(record.assigned_user_ids.ids)
                if record.user_id:
                    assigned_users.add(record.user_id.id)
                for user in self.env["res.users"].browse(assigned_users):
                    record._send_assignment_email(user)
        if not self.env.context.get("skip_assignment_sync"):
            records.with_context(
                skip_assignment_email=True, skip_assignment_sync=True
            )._sync_assigned_users()
        return records

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = self._prepare_ticket_number(default)
        res = super().copy(default)
        return res

    def write(self, vals):
        """Update ticket with proper timestamp tracking."""
        now = fields.Datetime.now()
        skip_email = self.env.context.get("skip_assignment_email")
        old_users = {}
        old_assigned = {}
        if "user_id" in vals:
            old_users = {rec.id: rec.user_id for rec in self}
        if "assigned_user_ids" in vals:
            old_assigned = {rec.id: set(rec.assigned_user_ids.ids) for rec in self}
        if vals.get("stage_id"):
            stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
            # Check if stage exists to prevent errors if stage was deleted
            if stage.exists():
                vals["last_stage_update"] = now
                if stage.closed:
                    vals["closed_date"] = now
            vals["x_stage_entered_at"] = now
            vals["x_last_update_at"] = now
        if vals.get("user_id"):
            vals["assigned_date"] = now
        res = super().write(vals)
        if not skip_email and ("user_id" in vals or "assigned_user_ids" in vals):
            for rec in self:
                new_users = set()
                if "assigned_user_ids" in vals:
                    new_users |= set(rec.assigned_user_ids.ids) - old_assigned.get(
                        rec.id, set()
                    )
                if "user_id" in vals:
                    new_user = rec.user_id
                    if new_user and new_user != old_users.get(rec.id):
                        new_users.add(new_user.id)
                for user in self.env["res.users"].browse(new_users):
                    rec._send_assignment_email(user)
        if not self.env.context.get("skip_assignment_sync"):
            self.with_context(
                skip_assignment_email=True, skip_assignment_sync=True
            )._sync_assigned_users()
        return res

    def message_post(self, **kwargs):
        res = super().message_post(**kwargs)
        if not self.env.context.get("skip_last_update_at"):
            subtype_id = kwargs.get("subtype_id")
            if subtype_id:
                mt_note = self.env.ref("mail.mt_note", raise_if_not_found=False)
                if mt_note and subtype_id == mt_note.id:
                    self.with_context(skip_last_update_at=True).write(
                        {"x_last_update_at": fields.Datetime.now()}
                    )
        return res

    def action_duplicate_tickets(self):
        for ticket in self.browse(self.env.context["active_ids"]):
            ticket.copy()

    def _prepare_ticket_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return seq.next_by_code("helpdesk.ticket.sequence") or "/"

    def _compute_access_url(self):
        res = super()._compute_access_url()
        for item in self:
            item.access_url = f"/my/ticket/{item.id}"
        return res

    def _sync_assigned_users(self):
        for ticket in self:
            updates = {}
            if ticket.user_id and ticket.user_id not in ticket.assigned_user_ids:
                updates["assigned_user_ids"] = [(4, ticket.user_id.id)]
            elif ticket.assigned_user_ids and not ticket.user_id:
                updates["user_id"] = ticket.assigned_user_ids[0].id
            if updates:
                ticket.with_context(
                    skip_assignment_email=True, skip_assignment_sync=True
                ).write(updates)

    def _send_assignment_email(self, user):
        template = self.env.ref(
            "helpdesk_mgmt.assignment_email_template", raise_if_not_found=False
        )
        if not template or not user or not user.email:
            return
        base_url = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        )
        for ticket in self:
            ticket_label = ticket.display_name or ticket.number or ticket.name or ""
            ticket_url = (
                f"{base_url}/web#id={ticket.id}&model=helpdesk.ticket&view_type=form"
            )
            cta_html = f"""
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="background:#623412; border-radius:6px;">
                            <a href="{ticket_url}" target="_blank"
                               style="display:inline-block; padding:10px 16px; color:#ffffff;
                                      text-decoration:none; font-weight:600;">
                                View Helpdesk Ticket
                            </a>
                        </td>
                    </tr>
                </table>
            """
            email_values = {
                "email_to": user.email,
                "email_cc": False,
                "recipient_ids": [(6, 0, [user.partner_id.id])],
                "body_html": (
                    f"<p>Hello {user.name},</p>"
                    f"<p>The ticket <strong>{ticket_label}</strong> has been assigned to you.</p>"
                    f"{cta_html}"
                ),
            }
            template.with_context(
                lang=user.partner_id.lang or user.lang
            ).send_mail(ticket.id, force_send=True, email_values=email_values, raise_exception=False)

    # ---------------------------------------------------
    # Mail gateway
    # ---------------------------------------------------

    def _track_template(self, tracking):
        res = super()._track_template(tracking)
        ticket = self[0]
        if "stage_id" in tracking and ticket.stage_id.mail_template_id:
            res["stage_id"] = (
                ticket.stage_id.mail_template_id,
                {
                    # Need to set mass_mail so that the email will always be sent
                    "composition_mode": "mass_mail",
                    "auto_delete_keep_log": False,
                    "subtype_id": self.env["ir.model.data"]._xmlid_to_res_id(
                        "mail.mt_note"
                    ),
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        return res

    @api.model
    def message_new(self, msg, custom_values=None):
        """Override message_new from mail gateway so we can set correct
        default values.
        """
        if custom_values is None:
            custom_values = {}
        defaults = {
            "name": msg.get("subject") or self.env._("No Subject"),
            "number": "/",
            "description": msg.get("body"),
            "partner_email": msg.get("from"),
            "partner_id": msg.get("author_id"),
            "purchase_order_number": self.env._("N/A"),
        }
        defaults.update(custom_values)

        # Write default values coming from msg
        ticket = super().message_new(msg, custom_values=defaults)

        # Use mail gateway tools to search for partners to subscribe
        email_list = tools.email_split(
            (msg.get("to") or "") + "," + (msg.get("cc") or "")
        )
        partner_ids = [
            p.id
            for p in self.env["mail.thread"]._mail_find_partner_from_emails(
                email_list, records=ticket, force_create=False
            )
            if p
        ]
        ticket.message_subscribe(partner_ids)

        return ticket

    def message_update(self, msg, update_vals=None):
        """Override message_update to subscribe partners"""
        email_list = tools.email_split(
            (msg.get("to") or "") + "," + (msg.get("cc") or "")
        )
        partner_ids = [
            p.id
            for p in self.env["mail.thread"]._mail_find_partner_from_emails(
                email_list, records=self, force_create=False
            )
            if p
        ]
        self.message_subscribe(partner_ids)
        return super().message_update(msg, update_vals=update_vals)

    def _message_get_suggested_recipients(self, **kwargs):
        recipients = super()._message_get_suggested_recipients(**kwargs)
        # In Odoo 19, recipients is a list of tuples: (partner_id, name, reason)
        if not isinstance(recipients, list):
            recipients = list(recipients) if recipients else []
        try:
            for ticket in self:
                if ticket.partner_id:
                    # Add suggested recipient as tuple: (partner_id, name, reason)
                    recipients.append(
                        (ticket.partner_id.id, ticket.partner_id.name, self.env._("Customer"))
                    )
                elif ticket.partner_email:
                    # Add suggested recipient by email: (False, email, reason)
                    recipients.append(
                        (False, ticket.partner_email, self.env._("Customer Email"))
                    )
        except AccessError:
            # no read access rights -> just ignore suggested recipients because this
            # imply modifying followers
            return recipients
        return recipients

    def _notify_get_reply_to(self, default=None, author_id=None):
        """Override to set alias of tasks to their team if any."""
        aliases = self.sudo().mapped("team_id")._notify_get_reply_to(default=default, author_id=author_id)
        res = {ticket.id: aliases.get(ticket.team_id.id) for ticket in self}
        leftover = self.filtered(lambda rec: not rec.team_id)
        if leftover:
            res.update(
                super(HelpdeskTicket, leftover)._notify_get_reply_to(default=default, author_id=author_id)
            )
        return res
