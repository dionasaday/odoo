from odoo import fields, models


class MailActivity(models.Model):
    _inherit = "mail.activity"

    def action_done(self, *args, **kwargs):
        activity_ids = self.ids
        res = super().action_done(*args, **kwargs)
        if not activity_ids:
            return res
        events = self.env["helpdesk.followup.event"].sudo().search(
            [("followup_activity_id", "in", activity_ids)]
        )
        if events:
            activities = {
                activity.id: activity
                for activity in self.env["mail.activity"]
                .sudo()
                .with_context(active_test=False)
                .search([("id", "in", activity_ids)])
            }
            for event in events:
                activity = activities.get(event.followup_activity_id.id)
                done_at = (activity and (activity.date_done or activity.write_date)) or fields.Datetime.now()
                event.write({"followup_done_at": done_at, "state": "done"})
        return res
