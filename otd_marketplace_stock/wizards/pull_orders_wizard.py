# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta


class PullOrdersWizard(models.TransientModel):
    _name = 'marketplace.pull.orders.wizard'
    _description = 'Pull Orders Wizard'

    account_id = fields.Many2one(
        'marketplace.account', string='Account', required=True,
        help='Marketplace account to pull orders from'
    )
    shop_id = fields.Many2one(
        'marketplace.shop', string='Shop',
        domain="[('account_id', '=', account_id), ('active', '=', True)]",
        help='Specific shop to pull orders from (leave empty to pull from all shops)'
    )
    date_from = fields.Datetime(
        string='From Date', required=True,
        default=lambda self: fields.Datetime.now() - timedelta(days=7),
        help='Start date for pulling orders'
    )
    date_to = fields.Datetime(
        string='To Date', required=True,
        default=lambda self: fields.Datetime.now(),
        help='End date for pulling orders'
    )
    use_custom_date = fields.Boolean(
        string='Use Custom Date Range', default=True,
        help='If checked, use the date range specified above. If unchecked, pull orders since last sync.'
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to:
                if record.date_from > record.date_to:
                    raise ValidationError('From Date must be before To Date')
                # Check if date range is too large (more than 90 days)
                if (record.date_to - record.date_from).days > 90:
                    raise ValidationError('Date range cannot exceed 90 days. Please select a smaller range.')

    def action_pull_orders(self):
        """Create pull order jobs with specified date range"""
        self.ensure_one()
        
        if not self.account_id.sync_enabled:
            raise UserError(f'Sync is disabled for account {self.account_id.name}. Please enable sync first.')
        
        if self.account_id.channel == 'zortout':
            raise UserError('Pulling orders is not supported for Zortout. This account only syncs stock.')
        
        # Check if Shopee account has tokens
        if self.account_id.channel == 'shopee':
            has_access_token = bool(self.account_id.access_token)
            has_refresh_token = bool(self.account_id.refresh_token)
            if not has_access_token or not has_refresh_token:
                raise UserError(f'Cannot pull orders for Shopee account {self.account_id.name}: Account is not fully connected. Please connect the account first (missing access_token or refresh_token).')
        
        # Determine shops to pull from
        if self.shop_id:
            shops = self.shop_id
        else:
            shops = self.account_id.shop_ids.filtered('active')
        
        if not shops:
            raise UserError('No active shops found for this account.')
        
        # Prepare payload
        if self.use_custom_date:
            payload = {
                'since': self.date_from.isoformat(),
                'until': self.date_to.isoformat(),
            }
            job_name_suffix = f' ({self.date_from.strftime("%Y-%m-%d")} to {self.date_to.strftime("%Y-%m-%d")})'
        else:
            payload = {}
            job_name_suffix = ''
        
        # Create jobs for each shop
        created_jobs = []
        for shop in shops:
            job = self.env['marketplace.job'].create({
                'name': f'Pull orders for {shop.name}{job_name_suffix}',
                'job_type': 'pull_order',
                'account_id': self.account_id.id,
                'shop_id': shop.id,
                'priority': 'high',
                'payload': payload,
                'state': 'pending',
                'next_run_at': fields.Datetime.now(),
            })
            created_jobs.append(job)
        
        # Return notification
        shop_names = ', '.join([s.name for s in shops])
        date_info = f' from {self.date_from.strftime("%Y-%m-%d %H:%M")} to {self.date_to.strftime("%Y-%m-%d %H:%M")}' if self.use_custom_date else ' since last sync'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Jobs Created',
                'message': f'Created {len(created_jobs)} pull order job(s) for {shop_names}{date_info}. Jobs will be processed automatically.',
                'type': 'success',
                'sticky': False,
            }
        }

