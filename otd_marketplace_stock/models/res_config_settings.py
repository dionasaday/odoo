# -*- coding: utf-8 -*-

from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Marketplace settings
    marketplace_default_buffer = fields.Integer(
        string='Default Buffer Quantity',
        config_parameter='marketplace.default_buffer_qty',
        default=5,
    )
    marketplace_default_min_qty = fields.Integer(
        string='Default Minimum Quantity',
        config_parameter='marketplace.default_min_qty',
        default=0,
    )
    marketplace_batch_size = fields.Integer(
        string='Default Batch Size',
        config_parameter='marketplace.batch_size',
        default=50,
    )
    marketplace_pull_interval = fields.Integer(
        string='Default Pull Interval (minutes)',
        config_parameter='marketplace.pull_interval_minutes',
        default=5,
    )

