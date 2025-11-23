# -*- coding: utf-8 -*-

import re

from odoo import models, fields, api


class MarketplaceChannel(models.Model):
    _name = 'marketplace.channel'
    _description = 'Marketplace Channel'
    _order = 'name ASC'

    name = fields.Char(string='Channel Name', required=True, translate=True)
    code = fields.Char(
        string='Technical Code',
        required=True,
        help='Internal identifier used to map shops and integrations'
    )
    active = fields.Boolean(default=True)
    description = fields.Text(string='Description')

    _sql_constraints = [
        ('marketplace_channel_code_unique', 'unique(code)', 'Channel code must be unique.')
    ]

    @staticmethod
    def _slugify(text):
        text = text or ''
        cleaned = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_')
        return cleaned.lower() or 'channel'

    @api.model
    def _generate_unique_code(self, name):
        base = self._slugify(name)
        code = base
        index = 1
        while self.search_count([('code', '=', code)]):
            code = f'{base or "channel"}{index}'
            index += 1
        return code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code') and vals.get('name'):
                vals['code'] = self._generate_unique_code(vals['name'])
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if 'code' not in vals and vals.get('name') is not None:
            for channel in self:
                if channel and not channel.code and channel.name:
                    channel.code = channel._generate_unique_code(channel.name)
        return res

