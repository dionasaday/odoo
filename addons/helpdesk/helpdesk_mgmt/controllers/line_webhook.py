import base64
import hashlib
import hmac
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import requests

import odoo.http as http
from odoo import fields
from odoo.http import request
from odoo.osv import expression

_logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s]{6,}\d")


class LineOAController(http.Controller):
    @http.route(
        ["/line/webhook/otd", "/line/webhook/<path:webhook_path>"],
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def line_webhook(self, webhook_path=None, **kwargs):
        icp = request.env["ir.config_parameter"].sudo()
        conf_path = icp.get_param(
            "helpdesk_mgmt.lineoa_webhook_path", "/line/webhook/otd"
        )
        if request.httprequest.path != conf_path:
            return http.Response(status=404)
        if icp.get_param("helpdesk_mgmt.lineoa_enabled", "False") != "True":
            return http.Response(status=404)

        body = request.httprequest.get_data() or b""
        signature = request.httprequest.headers.get("X-Line-Signature")
        channel = self._match_lineoa_channel(body, signature)
        if not channel:
            secret = icp.get_param("helpdesk_mgmt.lineoa_channel_secret") or ""
            if not self._verify_signature(secret, body, signature):
                return http.Response(status=403)

        try:
            payload = json.loads(body.decode("utf-8") if body else "{}")
        except Exception:
            return http.Response(status=400)

        events = payload.get("events", [])
        for event in events:
            self._process_event(event, channel)
        return http.Response("OK", status=200)

    def _verify_signature(self, secret, body, signature):
        if not secret or not signature:
            return False
        digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    def _match_lineoa_channel(self, body, signature):
        Channel = request.env["helpdesk.lineoa.channel"].sudo()
        for channel in Channel.search([("active", "=", True)]):
            if self._verify_signature(channel.channel_secret or "", body, signature):
                return channel
        return None

    def _process_event(self, event, channel=None):
        env = request.env
        icp = env["ir.config_parameter"].sudo()
        line_event = env["x_line_webhook_event"].sudo()

        payload_snippet = json.dumps(event, ensure_ascii=False)[:1000]
        if event.get("type") != "message":
            line_event.create(
                {
                    "received_at": fields.Datetime.now(),
                    "lineoa_channel_id": channel.id if channel else False,
                    "processed": False,
                    "payload_snippet": payload_snippet,
                }
            )
            return

        message = event.get("message", {})
        if message.get("type") != "text":
            line_event.create(
                {
                    "received_at": fields.Datetime.now(),
                    "lineoa_channel_id": channel.id if channel else False,
                    "processed": False,
                    "payload_snippet": payload_snippet,
                }
            )
            return

        line_user_id = (event.get("source") or {}).get("userId")
        message_text = message.get("text") or ""
        timestamp_ms = event.get("timestamp")
        timestamp = None
        if timestamp_ms:
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

        display_name = None
        access_token = (
            channel.channel_access_token if channel else icp.get_param("helpdesk_mgmt.lineoa_channel_access_token") or ""
        )
        if access_token and line_user_id:
            display_name = self._fetch_line_profile(line_user_id, access_token)

        match_mode = (
            channel.match_mode
            if channel
            else icp.get_param(
                "helpdesk_mgmt.lineoa_match_mode", "by_phone_or_email_in_message"
            )
        )
        partner, matched_partner, created_partner, conflict = self._map_partner(
            line_user_id, message_text, display_name, match_mode
        )

        created_ticket = None
        create_ticket = (
            channel.create_ticket
            if channel
            else icp.get_param("helpdesk_mgmt.lineoa_create_ticket", "True") == "True"
        )
        if create_ticket:
            created_ticket = self._create_or_update_ticket(
                partner,
                line_user_id,
                message_text,
                timestamp,
                channel,
            )

        line_event.create(
            {
                "received_at": fields.Datetime.now(),
                "lineoa_channel_id": channel.id if channel else False,
                "line_user_id": line_user_id,
                "message_text": message_text,
                "matched_partner_id": matched_partner.id if matched_partner else False,
                "created_partner_id": created_partner.id if created_partner else False,
                "created_ticket_id": created_ticket.id if created_ticket else False,
                "processed": True,
                "payload_snippet": payload_snippet,
            }
        )

        if conflict and matched_partner:
            matched_partner.message_post(
                body="LINE user ID mismatch detected for this contact.",
                subtype_xmlid="mail.mt_note",
            )

    def _fetch_line_profile(self, line_user_id, access_token):
        try:
            response = requests.get(
                f"https://api.line.me/v2/bot/profile/{line_user_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=3,
            )
            if response.status_code >= 300:
                return None
            data = response.json()
            return data.get("displayName")
        except Exception:
            return None

    def _map_partner(self, line_user_id, message_text, display_name, match_mode):
        env = request.env
        Partner = env["res.partner"].sudo()

        conflict = False
        matched_partner = None
        created_partner = None

        partner = False
        if line_user_id:
            partner = Partner.search([("x_line_user_id", "=", line_user_id)], limit=1)

        if not partner and match_mode == "by_phone_or_email_in_message":
            email = self._extract_email(message_text)
            phone_variants = self._extract_phone_variants(message_text)
            domain = []
            if email:
                domain = expression.OR([domain, [("email", "=ilike", email)]])
            if phone_variants:
                phone_domain = []
                for variant in phone_variants:
                    phone_domain = expression.OR(
                        [
                            phone_domain,
                            ["|", ("phone", "ilike", variant), ("mobile", "ilike", variant)],
                        ]
                    )
                domain = expression.OR([domain, phone_domain])
            if domain:
                partner = Partner.search(domain, limit=1)

        if partner:
            matched_partner = partner
            vals = {"x_line_last_seen": fields.Datetime.now()}
            if display_name:
                vals["x_line_display_name"] = display_name
            if line_user_id:
                if not partner.x_line_user_id or partner.x_line_user_id == line_user_id:
                    vals["x_line_user_id"] = line_user_id
                else:
                    conflict = True
            if vals:
                partner.write(vals)
            return partner, matched_partner, created_partner, conflict

        vals = {
            "name": display_name or "LINE Customer",
            "x_line_user_id": line_user_id,
            "x_line_display_name": display_name,
            "x_line_last_seen": fields.Datetime.now(),
        }
        created_partner = Partner.create(vals)
        return created_partner, matched_partner, created_partner, conflict

    def _create_or_update_ticket(self, partner, line_user_id, message_text, timestamp, channel=None):
        env = request.env
        icp = env["ir.config_parameter"].sudo()
        Ticket = env["helpdesk.ticket"].sudo()

        team_id = (
            channel.helpdesk_team_id.id if channel and channel.helpdesk_team_id else icp.get_param("helpdesk_mgmt.lineoa_helpdesk_team_id")
        )
        stage_id = (
            channel.default_stage_id.id if channel and channel.default_stage_id else icp.get_param("helpdesk_mgmt.lineoa_default_stage_id")
        )
        team_id = int(team_id) if team_id else False
        stage_id = int(stage_id) if stage_id else False

        since = fields.Datetime.now() - timedelta(hours=24)
        domain = [
            ("partner_id", "=", partner.id),
            ("create_date", ">=", since),
        ]
        if team_id:
            domain.append(("team_id", "=", team_id))
        domain.append(("stage_id.closed", "=", False))
        existing = Ticket.search(domain, limit=1)

        if existing:
            existing.message_post(
                body=f"New LINE message received:\n{message_text}",
                subtype_xmlid="mail.mt_note",
            )
            return existing

        if not stage_id and team_id:
            team = env["helpdesk.ticket.team"].browse(team_id)
            stage_id = team._get_applicable_stages()[:1].id

        channel = env.ref("helpdesk_mgmt.helpdesk_ticket_channel_other", False)
        if channel:
            channel_id = channel.id
        else:
            channel_id = env["helpdesk.ticket.channel"].search([], limit=1).id

        ts_text = timestamp.isoformat() if timestamp else ""
        description = (
            f"LINE message:\n{message_text}\n\n"
            f"LINE userId: {line_user_id}\n"
            f"Timestamp: {ts_text}"
        )
        vals = {
            "name": f"LINE: {message_text[:60]}",
            "description": description,
            "partner_id": partner.id,
            "team_id": team_id,
            "stage_id": stage_id,
            "channel_id": channel_id,
            "purchase_order_number": env._("N/A"),
            "x_line_channel_id": channel.id if channel else False,
            "x_line_user_id": line_user_id,
        }
        return Ticket.create(vals)

    def _extract_email(self, text):
        match = EMAIL_RE.search(text or "")
        return match.group(0) if match else None

    def _extract_phone_variants(self, text):
        match = PHONE_RE.search(text or "")
        if not match:
            return []
        raw = match.group(0)
        digits = re.sub(r"\D", "", raw)
        if not digits:
            return []
        variants = {digits}
        if digits.startswith("66") and len(digits) > 2:
            variants.add("0" + digits[2:])
        if digits.startswith("0") and len(digits) > 1:
            variants.add("66" + digits[1:])
        return list(variants)
