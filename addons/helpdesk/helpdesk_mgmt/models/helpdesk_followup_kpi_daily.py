from datetime import date, timedelta

from dateutil import parser

from odoo import api, fields, models

DEFAULT_COMPLETION_TARGET = 90.0
DEFAULT_RESPONSE_SLA_HOURS = 2.0


class HelpdeskFollowupKpiDaily(models.Model):
    _name = "helpdesk.followup.kpi.daily"
    _description = "Helpdesk Follow-up KPI Daily"
    _order = "date desc, id desc"

    date = fields.Date(required=True, index=True)
    team_id = fields.Many2one(comodel_name="helpdesk.ticket.team", string="Team")
    policy_id = fields.Many2one(comodel_name="helpdesk.followup.policy", string="Policy")
    assigned_user_id = fields.Many2one(comodel_name="res.users", string="Assigned User")

    followup_created_count = fields.Integer(default=0)
    followup_done_count = fields.Integer(default=0)
    escalation_count = fields.Integer(default=0)
    avg_response_time_hours = fields.Float(default=0.0)
    completion_rate = fields.Float(compute="_compute_completion_rate", store=True)

    card_completion_class = fields.Char(compute="_compute_card_classes")
    card_response_class = fields.Char(compute="_compute_card_classes")
    card_escalation_class = fields.Char(compute="_compute_card_classes")

    exec_is_header = fields.Boolean(compute="_compute_exec_metrics")
    exec_total_created = fields.Integer(compute="_compute_exec_metrics")
    exec_total_done = fields.Integer(compute="_compute_exec_metrics")
    exec_total_escalations = fields.Integer(compute="_compute_exec_metrics")
    exec_completion_rate = fields.Float(compute="_compute_exec_metrics")
    exec_avg_response_time_hours = fields.Float(compute="_compute_exec_metrics")
    exec_completion_delta = fields.Float(compute="_compute_exec_metrics")
    exec_response_delta = fields.Float(compute="_compute_exec_metrics")
    exec_completion_delta_display = fields.Char(compute="_compute_exec_metrics")
    exec_response_delta_display = fields.Char(compute="_compute_exec_metrics")
    exec_completion_class = fields.Char(compute="_compute_exec_metrics")
    exec_response_class = fields.Char(compute="_compute_exec_metrics")
    exec_escalation_class = fields.Char(compute="_compute_exec_metrics")
    exec_completion_target = fields.Float(compute="_compute_exec_metrics")
    exec_response_sla_hours = fields.Float(compute="_compute_exec_metrics")
    exec_trend_points = fields.Json(compute="_compute_exec_metrics")
    exec_trend_interval = fields.Char(compute="_compute_exec_metrics")
    exec_cs_ranking = fields.Json(compute="_compute_exec_metrics")
    exec_escalation_ranking = fields.Json(compute="_compute_exec_metrics")
    exec_team_rankings = fields.Json(compute="_compute_exec_metrics")

    _sql_constraints = [
        (
            "helpdesk_followup_kpi_daily_uniq",
            "unique(date, team_id, policy_id, assigned_user_id)",
            "KPI Daily already exists for this date/team/policy/user.",
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

    @api.depends("completion_rate", "avg_response_time_hours", "escalation_count")
    def _compute_card_classes(self):
        for rec in self:
            rec.card_completion_class = self._completion_class(rec.completion_rate)
            rec.card_response_class = self._response_class(rec.avg_response_time_hours)
            rec.card_escalation_class = self._escalation_class(rec.escalation_count)

    @api.model
    def search(self, domain, offset=0, limit=None, order=None):
        if self.env.context.get("skip_kpi_domain"):
            return super().search(domain, offset=offset, limit=limit, order=order)
        records = super().search(domain, offset=offset, limit=limit, order=order)
        return records.with_context(kpi_domain=domain, skip_kpi_domain=True)

    @api.depends_context("kpi_domain")
    def _compute_exec_metrics(self):
        domain = self.env.context.get("kpi_domain") or []
        completion_target, response_sla = self._get_kpi_targets()
        summary = self._get_exec_summary(domain)
        trend_points, trend_interval = self._get_exec_trends(domain)
        cs_ranking, escalation_ranking = self._get_exec_rankings(domain)
        team_rankings = self._get_exec_team_rankings(domain)
        first_record = self.with_context(skip_kpi_domain=True).search(
            domain, order="date desc, id desc", limit=1
        )
        first_id = first_record.id if first_record else False

        completion_rate = summary["completion_rate"]
        avg_response = summary["avg_response_time_hours"]
        completion_delta = completion_rate - completion_target
        response_delta = avg_response - response_sla
        completion_delta_display = self._format_delta(
            completion_delta, suffix="%", precision=1
        )
        response_delta_display = self._format_delta(
            response_delta, suffix="h", precision=2
        )
        completion_class = self._completion_class(completion_rate)
        response_class = self._response_class(avg_response)
        escalation_class = self._escalation_class(summary["escalation_count"])

        for rec in self:
            rec.exec_is_header = bool(first_id and rec.id == first_id)
            rec.exec_total_created = summary["created_count"]
            rec.exec_total_done = summary["done_count"]
            rec.exec_total_escalations = summary["escalation_count"]
            rec.exec_completion_rate = completion_rate
            rec.exec_avg_response_time_hours = avg_response
            rec.exec_completion_delta = completion_delta
            rec.exec_response_delta = response_delta
            rec.exec_completion_delta_display = completion_delta_display
            rec.exec_response_delta_display = response_delta_display
            rec.exec_completion_class = completion_class
            rec.exec_response_class = response_class
            rec.exec_escalation_class = escalation_class
            rec.exec_completion_target = completion_target
            rec.exec_response_sla_hours = response_sla
            rec.exec_trend_points = trend_points
            rec.exec_trend_interval = trend_interval
            rec.exec_cs_ranking = cs_ranking
            rec.exec_escalation_ranking = escalation_ranking
            rec.exec_team_rankings = team_rankings

    def _get_exec_summary(self, domain):
        stats = self.read_group(
            domain,
            [
                "followup_created_count:sum",
                "followup_done_count:sum",
                "escalation_count:sum",
                "avg_response_time_hours:avg",
            ],
            [],
            lazy=False,
        )
        row = stats[0] if stats else {}
        created_count = (
            row.get("followup_created_count_sum")
            or row.get("followup_created_count")
            or 0
        )
        done_count = (
            row.get("followup_done_count_sum") or row.get("followup_done_count") or 0
        )
        escalation_count = (
            row.get("escalation_count_sum") or row.get("escalation_count") or 0
        )
        avg_response = (
            row.get("avg_response_time_hours_avg")
            if row.get("avg_response_time_hours_avg") is not None
            else row.get("avg_response_time_hours")
        )
        completion_rate = (done_count / created_count * 100.0) if created_count else 0.0
        return {
            "created_count": int(created_count),
            "done_count": int(done_count),
            "escalation_count": int(escalation_count),
            "avg_response_time_hours": avg_response or 0.0,
            "completion_rate": completion_rate,
        }

    def _get_exec_trends(self, domain):
        first = self.with_context(skip_kpi_domain=True).search(
            domain, order="date asc", limit=1
        )
        last = self.with_context(skip_kpi_domain=True).search(
            domain, order="date desc", limit=1
        )
        if not first or not last:
            return [], "day"
        range_days = (last.date - first.date).days + 1
        interval = "week" if range_days > 60 else "day"
        groups = self.read_group(
            domain,
            [
                "followup_created_count:sum",
                "followup_done_count:sum",
                "escalation_count:sum",
                "avg_response_time_hours:avg",
            ],
            [f"date:{interval}"],
            lazy=False,
        )
        points = []
        for g in groups:
            raw_date = g.get("date") or g.get(f"date:{interval}")
            if isinstance(raw_date, date):
                label = fields.Date.to_string(raw_date)
            else:
                label = str(raw_date)
            created = (
                g.get("followup_created_count_sum")
                or g.get("followup_created_count")
                or 0
            )
            done = (
                g.get("followup_done_count_sum") or g.get("followup_done_count") or 0
            )
            esc = (
                g.get("escalation_count_sum") or g.get("escalation_count") or 0
            )
            avg_response = (
                g.get("avg_response_time_hours_avg")
                if g.get("avg_response_time_hours_avg") is not None
                else g.get("avg_response_time_hours")
            )
            completion = (done / created * 100.0) if created else 0.0
            points.append(
                {
                    "label": label,
                    "completion_rate": round(completion, 2),
                    "avg_response_time_hours": round(avg_response or 0.0, 2),
                    "escalation_count": int(esc),
                }
            )
        max_response = max(
            [point["avg_response_time_hours"] for point in points] or [0]
        )
        max_escalations = max([point["escalation_count"] for point in points] or [0])
        for point in points:
            point["response_pct"] = (
                round(point["avg_response_time_hours"] / max_response * 100.0, 1)
                if max_response
                else 0.0
            )
            point["escalation_pct"] = (
                round(point["escalation_count"] / max_escalations * 100.0, 1)
                if max_escalations
                else 0.0
            )
        return points, interval

    def _get_exec_rankings(self, domain):
        completion_target, response_sla = self._get_kpi_targets()
        groups = self.read_group(
            domain,
            [
                "followup_created_count:sum",
                "followup_done_count:sum",
                "escalation_count:sum",
                "avg_response_time_hours:avg",
            ],
            ["assigned_user_id"],
            lazy=False,
        )
        cs_rows = []
        esc_rows = []
        for g in groups:
            user = g.get("assigned_user_id")
            if not user:
                continue
            created = (
                g.get("followup_created_count_sum")
                or g.get("followup_created_count")
                or 0
            )
            done = (
                g.get("followup_done_count_sum") or g.get("followup_done_count") or 0
            )
            esc = (
                g.get("escalation_count_sum") or g.get("escalation_count") or 0
            )
            avg_response = (
                g.get("avg_response_time_hours_avg")
                if g.get("avg_response_time_hours_avg") is not None
                else g.get("avg_response_time_hours")
            )
            completion = (done / created * 100.0) if created else 0.0
            cs_score, cs_grade = self._compute_cs_score(
                created, done, avg_response or 0.0, esc, completion_target, response_sla
            )
            row = {
                "user": user[1],
                "created": int(created),
                "done": int(done),
                "completion_rate": round(completion, 2),
                "avg_response_time_hours": round(avg_response or 0.0, 2),
                "escalations": int(esc),
                "cs_score": round(cs_score, 2),
                "cs_grade": cs_grade,
            }
            cs_rows.append(row)
            esc_rows.append(row)
        cs_rows.sort(
            key=lambda r: (-r["completion_rate"], r["avg_response_time_hours"])
        )
        esc_rows.sort(key=lambda r: (-r["escalations"], r["avg_response_time_hours"]))
        return cs_rows[:10], esc_rows[:10]

    def _get_exec_team_rankings(self, domain):
        completion_target, response_sla = self._get_kpi_targets()
        groups = self.read_group(
            domain,
            [
                "followup_created_count:sum",
                "followup_done_count:sum",
                "escalation_count:sum",
                "avg_response_time_hours:avg",
            ],
            ["team_id", "assigned_user_id"],
            lazy=False,
        )
        teams = {}
        for g in groups:
            user = g.get("assigned_user_id")
            if not user:
                continue
            team = g.get("team_id")
            team_id = team[0] if team else False
            team_name = team[1] if team else "No Team"
            team_key = team_id or "none"
            created = (
                g.get("followup_created_count_sum")
                or g.get("followup_created_count")
                or 0
            )
            done = (
                g.get("followup_done_count_sum") or g.get("followup_done_count") or 0
            )
            esc = (
                g.get("escalation_count_sum") or g.get("escalation_count") or 0
            )
            avg_response = (
                g.get("avg_response_time_hours_avg")
                if g.get("avg_response_time_hours_avg") is not None
                else g.get("avg_response_time_hours")
            )
            completion = (done / created * 100.0) if created else 0.0
            cs_score, cs_grade = self._compute_cs_score(
                created, done, avg_response or 0.0, esc, completion_target, response_sla
            )
            row = {
                "user": user[1],
                "created": int(created),
                "done": int(done),
                "completion_rate": round(completion, 2),
                "avg_response_time_hours": round(avg_response or 0.0, 2),
                "escalations": int(esc),
                "cs_score": round(cs_score, 2),
                "cs_grade": cs_grade,
            }
            if team_key not in teams:
                teams[team_key] = {
                    "team_id": team_id,
                    "team_name": team_name,
                    "cs_rows": [],
                    "esc_rows": [],
                }
            teams[team_key]["cs_rows"].append(row)
            teams[team_key]["esc_rows"].append(row)

        results = []
        for team in teams.values():
            team["cs_rows"].sort(
                key=lambda r: (-r["completion_rate"], r["avg_response_time_hours"])
            )
            team["esc_rows"].sort(
                key=lambda r: (-r["escalations"], r["avg_response_time_hours"])
            )
            team["cs_rows"] = team["cs_rows"][:10]
            team["esc_rows"] = team["esc_rows"][:10]
            results.append(team)
        results.sort(key=lambda t: t["team_name"])
        return results

    def _completion_class(self, completion_rate):
        completion_target, _response_sla = self._get_kpi_targets()
        if completion_rate >= completion_target:
            return "text-success"
        if completion_rate >= 70.0:
            return "text-warning"
        return "text-danger"

    def _response_class(self, avg_response_time_hours):
        _completion_target, response_sla = self._get_kpi_targets()
        if avg_response_time_hours <= response_sla:
            return "text-success"
        if avg_response_time_hours <= response_sla * 1.5:
            return "text-warning"
        return "text-danger"

    def _escalation_class(self, escalation_count):
        if escalation_count == 0:
            return "text-success"
        if escalation_count <= 2:
            return "text-warning"
        return "text-danger"

    def _format_delta(self, delta, suffix="", precision=1):
        sign = "+" if delta > 0 else ""
        fmt = f"{{:{sign}.{precision}f}}"
        return f"{fmt.format(delta)}{suffix}"

    def _compute_cs_score(
        self, created, done, avg_response_time_hours, escalation_count, target, sla
    ):
        completion_rate = (done / created * 100.0) if created else 0.0
        if target:
            completion_score = min(100.0, (completion_rate / target) * 100.0)
        else:
            completion_score = 0.0

        if avg_response_time_hours <= sla:
            response_score = 100.0
        elif avg_response_time_hours <= sla * 1.5:
            response_score = 70.0
        elif avg_response_time_hours <= sla * 2:
            response_score = 40.0
        else:
            response_score = 0.0

        if escalation_count == 0:
            escalation_score = 100.0
        elif escalation_count <= 2:
            escalation_score = 70.0
        elif escalation_count <= 5:
            escalation_score = 40.0
        else:
            escalation_score = 0.0

        total_score = (
            completion_score * 0.50
            + response_score * 0.30
            + escalation_score * 0.20
        )
        grade = self._score_to_grade(total_score)
        return total_score, grade

    def _score_to_grade(self, score):
        if score >= 90.0:
            return "A"
        if score >= 80.0:
            return "B"
        if score >= 70.0:
            return "C"
        if score >= 60.0:
            return "D"
        return "F"

    def _get_kpi_targets(self):
        icp = self.env["ir.config_parameter"].sudo()
        completion_raw = icp.get_param("helpdesk_mgmt.followup_completion_target")
        response_raw = icp.get_param("helpdesk_mgmt.followup_response_sla_hours")
        try:
            completion_target = float(completion_raw)
        except (TypeError, ValueError):
            completion_target = DEFAULT_COMPLETION_TARGET
        try:
            response_sla = float(response_raw)
        except (TypeError, ValueError):
            response_sla = DEFAULT_RESPONSE_SLA_HOURS
        return completion_target, response_sla

    @api.model
    def _cron_compute_daily_kpis(self):
        Event = self.env["helpdesk.followup.event"]
        today = fields.Date.context_today(self)
        start = today - timedelta(days=90)

        self.search([("date", ">=", start)]).unlink()

        domain = [
            ("followup_created_date", ">=", start),
            ("followup_created_date", "!=", False),
        ]
        groups = Event.read_group(
            domain,
            [
                "id:count",
                "followup_done_at:count",
                "escalation_created_at:count",
                "response_time_hours:avg",
            ],
            [
                "followup_created_date:day",
                "team_id",
                "policy_id",
                "assigned_user_id",
            ],
            lazy=False,
        )
        for g in groups:
            raw_date = g.get("followup_created_date") or g.get(
                "followup_created_date:day"
            )
            if not raw_date:
                continue
            if isinstance(raw_date, date):
                date_value = raw_date
            else:
                try:
                    date_value = fields.Date.to_date(raw_date)
                except Exception:
                    date_value = parser.parse(str(raw_date)).date()
            created_count = (
                g.get("id_count")
                or g.get("__count")
                or g.get("id")
                or 0
            )
            done_count = (
                g.get("followup_done_at_count")
                or g.get("followup_done_at")
                or 0
            )
            escalation_count = (
                g.get("escalation_created_at_count")
                or g.get("escalation_created_at")
                or 0
            )
            avg_response = (
                g.get("response_time_hours_avg")
                if g.get("response_time_hours_avg") is not None
                else g.get("response_time_hours")
            )
            self.create(
                {
                    "date": date_value,
                    "team_id": g.get("team_id") and g["team_id"][0],
                    "policy_id": g.get("policy_id") and g["policy_id"][0],
                    "assigned_user_id": g.get("assigned_user_id")
                    and g["assigned_user_id"][0],
                    "followup_created_count": int(created_count),
                    "followup_done_count": int(done_count),
                    "escalation_count": int(escalation_count),
                    "avg_response_time_hours": avg_response or 0.0,
                }
            )
