# -*- coding: utf-8 -*-
from odoo import models, fields, api

class DisciplineOffenseCategory(models.Model):
    _name = "hr.discipline.offense.category"
    _description = "Discipline Offense Category"
    

    name = fields.Char(required=True)
    note = fields.Text()

class DisciplineOffense(models.Model):
    _name = "hr.discipline.offense"
    _description = "Discipline Offense"

    name = fields.Char(required=True)
    category_id = fields.Many2one(
        "hr.discipline.offense.category", string="ระดับความผิด", required=True
    )
    points = fields.Integer(required=True, default=1)
    description = fields.Text()
    active = fields.Boolean(default=True)

class OffenseCategory(models.Model):
    _name = "hr.discipline.category"
    _description = "Discipline Offense Category"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)