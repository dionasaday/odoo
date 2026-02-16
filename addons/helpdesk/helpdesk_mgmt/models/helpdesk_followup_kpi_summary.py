from datetime import timedelta

from odoo import api, fields, models


class HelpdeskFollowupKpiSummary(models.Model):
    _name = "helpdesk.followup.kpi.summary"
    _description = "Helpdesk Follow-up KPI Summary"
    _order = "date desc, id desc"

    key = fields.Char(required=True, default="summary", copy=False)
    date = fields.Date(required=True, index=True)
    period_days = fields.Integer(default=30)
    period_start = fields.Date()
    period_end = fields.Date()

    followup_created_count = fields.Integer(default=0)
    followup_done_count = fields.Integer(default=0)
    escalation_count = fields.Integer(default=0)
    avg_response_time_hours = fields.Float(default=0.0)
    completion_rate = fields.Float(compute="_compute_completion_rate", store=True)

    _sql_constraints = [
        (
            "helpdesk_followup_kpi_summary_key_uniq",
            "unique(key)",
            "Summary KPI already exists.",
        )
    ]

    @api.depends("followup_created_count", "followup_done_count")
    def _compute_completion_rate(self):
        for rec in self:
            if rec.followup_created_count:
                rec.completion_rate = (
                    rec.followup_done_count / rec.followup_created_count
                ) * 100.0
            else:
                rec.completion_rate = 0.0

    @api.model
    def _cron_compute_summary_kpi(self):
        Event = self.env["helpdesk.followup.event"]
        today = fields.Date.context_today(self)

        summary = self.search([("key", "=", "summary")], limit=1)
        period_days = summary.period_days if summary else 30
        period_days = max(period_days or 30, 1)
        period_start = today - timedelta(days=period_days - 1)

        domain = [
            ("followup_created_date", ">=", period_start),
            ("followup_created_date", "!=", False),
        ]
        group = Event.read_group(
            domain,
            [
                "id:count",
                "followup_done_at:count",
                "escalation_created_at:count",
                "response_time_hours:avg",
            ],
            [],
            lazy=False,
        )
        stats = group[0] if group else {}
        created_count = (
            stats.get("id_count")
            or stats.get("__count")
            or stats.get("id")
            or 0
        )
        done_count = (
            stats.get("followup_done_at_count")
            or stats.get("followup_done_at")
            or 0
        )
        escalation_count = (
            stats.get("escalation_created_at_count")
            or stats.get("escalation_created_at")
            or 0
        )
        avg_response = (
            stats.get("response_time_hours_avg")
            if stats.get("response_time_hours_avg") is not None
            else stats.get("response_time_hours")
        )
        vals = {
            "key": "summary",
            "date": today,
            "period_days": period_days,
            "period_start": period_start,
            "period_end": today,
            "followup_created_count": int(created_count),
            "followup_done_count": int(done_count),
            "escalation_count": int(escalation_count),
            "avg_response_time_hours": avg_response or 0.0,
        }
        if summary:
            summary.write(vals)
        else:
            self.create(vals)
