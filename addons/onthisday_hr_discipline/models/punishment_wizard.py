# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class DisciplinePunishmentWizard(models.TransientModel):
    _name = "hr.discipline.punishment.wizard"
    _description = "Discipline Punishment Wizard"

    case_id = fields.Many2one(
        "hr.discipline.case",
        string="กรณีความผิด",
        required=True,
        ondelete="cascade",
    )
    action_taken_id = fields.Many2one(
        "hr.discipline.action",
        string="บทลงโทษที่ต้องการบันทึก",
        required=True,
    )
    punishment_note = fields.Text(string="ข้อความเพิ่มเติม")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        case_id = self.env.context.get("active_id") or self.env.context.get("default_case_id")
        if case_id:
            case = self.env["hr.discipline.case"].browse(case_id).exists()
            if case:
                res.setdefault("case_id", case.id)
                res.setdefault(
                    "action_taken_id",
                    case.action_taken_id.id or case.action_suggested_id.id or False,
                )
                res.setdefault("punishment_note", case.punishment_note or False)

        action_id = res.get("action_taken_id")
        if action_id:
            action = self.env["hr.discipline.action"].browse(action_id)
            if action and action.note:
                # Prefer template note from the selected punishment rule.
                res["punishment_note"] = action.note
        return res

    @api.onchange("action_taken_id")
    def _onchange_action_taken_id(self):
        if self.action_taken_id:
            # Always refresh note from template when selecting a punishment.
            self.punishment_note = self.action_taken_id.note or False

    def action_confirm(self):
        self.ensure_one()
        case = self.case_id
        if not case:
            raise UserError(_("ไม่พบเคสที่ต้องการสรุปบทลงโทษ"))
        if case.status not in ("confirmed", "appeal"):
            raise UserError(_("เคสต้องอยู่สถานะ Confirmed หรือ Appeal ก่อน"))
        case.action_taken_id = self.action_taken_id
        case.punishment_note = self.punishment_note or False
        return case.action_apply_punishment()
