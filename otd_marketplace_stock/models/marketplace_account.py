# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import json
import csv
import io
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_logger = logging.getLogger(__name__)


class MarketplaceAccount(models.Model):
    _name = 'marketplace.account'
    _description = 'Marketplace Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Account Name', required=True, tracking=True)
    channel = fields.Selection([
        ('shopee', 'Shopee'),
        ('lazada', 'Lazada'),
        ('tiktok', 'TikTok Shop'),
        ('zortout', 'Zortout'),
        ('woocommerce', 'WooCommerce'),
    ], string='Channel', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, tracking=True
    )
    active = fields.Boolean(string='Active', default=True, tracking=True)

    # OAuth/Auth fields
    client_id = fields.Char(string='Client ID', tracking=True)
    client_secret = fields.Char(string='Client Secret', tracking=True)
    access_token = fields.Text(string='Access Token', tracking=True)
    refresh_token = fields.Text(string='Refresh Token', tracking=True)
    access_token_expire_at = fields.Datetime(string='Token Expires At')
    
    # WooCommerce specific fields
    woocommerce_consumer_key = fields.Char(
        string='Consumer Key',
        help='WooCommerce Consumer Key (ck_...) - Required for WooCommerce authentication',
        tracking=True
    )
    
    # Shop relationship
    shop_ids = fields.One2many(
        'marketplace.shop', 'account_id', string='Shops'
    )
    shop_count = fields.Integer(
        string='Shop Count', compute='_compute_shop_count'
    )

    # Configuration
    stock_location_id = fields.Many2one(
        'stock.location', string='Stock Location',
        domain=[('usage', '=', 'internal')],
        help='Location used for stock calculation'
    )
    push_buffer_qty = fields.Integer(
        string='Push Buffer Quantity', default=0,
        help='Buffer quantity to subtract from available stock. Set to 0 to push actual stock quantity without buffer. Note: Push stock only updates marketplace inventory, it does NOT reduce stock in Odoo.'
    )
    min_online_qty = fields.Integer(
        string='Minimum Online Quantity', default=0,
        help='Minimum quantity to show online (0 = hide if out of stock)'
    )
    sync_enabled = fields.Boolean(
        string='Sync Enabled', default=True,
        help='Enable automatic synchronization'
    )
    max_concurrent_jobs = fields.Integer(
        string='Max Concurrent Jobs', default=3,
        help='Maximum number of jobs that can run concurrently for this account. Prevents API rate limiting and system overload. Recommended: 2-5 jobs.',
        tracking=True
    )
    stock_sync_interval_minutes = fields.Integer(
        string='Stock Sync Interval (minutes)', default=10,
        help='Interval between automatic stock syncs from Zortout (in minutes). Minimum: 1 minute.',
        tracking=True
    )
    push_stock_interval_minutes = fields.Integer(
        string='Push Stock Interval (minutes)', default=30,
        help='Interval between automatic stock pushes to marketplace (in minutes). Minimum: 1 minute. Used for WooCommerce and other marketplaces.',
        tracking=True
    )
    push_stock_batch_size = fields.Integer(
        string='Push Stock Batch Size', default=25,
        help='Number of products to push per batch. Larger batches may cause timeouts. Recommended: 20-50 products per batch. Set to 0 to disable batching (push all at once).',
        tracking=True
    )
    stock_sync_batch_size = fields.Integer(
        string='Stock Sync Batch Size', default=500,
        help='Number of products to sync per batch when syncing stock from Zortout. Larger batches may cause timeouts. Recommended: 300-500 products per batch. Set to 0 to disable batching (sync all at once).',
        tracking=True
    )
    
    # Job cleanup settings
    job_cleanup_enabled = fields.Boolean(
        string='Enable Job Cleanup', default=False,
        help='Enable automatic cleanup of old done jobs',
        tracking=True
    )
    job_cleanup_retention_days = fields.Integer(
        string='Job Retention Days', default=7,
        help='Number of days to keep done jobs. Jobs older than this will be automatically deleted. Minimum: 1 day.',
        tracking=True
    )
    job_cleanup_keep_count = fields.Integer(
        string='Keep Recent Jobs Count', default=0,
        help='Number of recent jobs to keep per job type (0 = no limit, delete all old jobs). This ensures you always keep the most recent N jobs even if they are older than retention days.',
        tracking=True
    )
    job_cleanup_job_types = fields.Char(
        string='Job Types to Cleanup',
        help='Comma-separated list of job types to cleanup (e.g., "pull_order,push_stock"). Leave empty to cleanup all job types.',
        tracking=True
    )
    
    # Export data for skipped/not found products
    sync_export_data = fields.Text(
        string='Sync Export Data',
        help='JSON data containing skipped and not found products from last sync (for CSV export)'
    )
    
    @api.constrains('stock_sync_interval_minutes')
    def _check_stock_sync_interval(self):
        """Validate stock sync interval"""
        for record in self:
            if record.stock_sync_interval_minutes < 1:
                raise ValidationError('Stock Sync Interval must be at least 1 minute.')
    
    @api.constrains('push_stock_interval_minutes')
    def _check_push_stock_interval(self):
        """Validate push stock interval"""
        for record in self:
            if record.push_stock_interval_minutes < 1:
                raise ValidationError('Push Stock Interval must be at least 1 minute.')
    
    @api.constrains('push_stock_batch_size')
    def _check_push_stock_batch_size(self):
        """Validate push stock batch size"""
        for record in self:
            if record.push_stock_batch_size < 0:
                raise ValidationError('Push Stock Batch Size must be 0 (no batching) or greater.')
            if record.push_stock_batch_size > 200:
                raise ValidationError('Push Stock Batch Size should not exceed 200 to avoid timeouts.')
    
    @api.constrains('stock_sync_batch_size')
    def _check_stock_sync_batch_size(self):
        """Validate stock sync batch size"""
        for record in self:
            if record.stock_sync_batch_size < 0:
                raise ValidationError('Stock Sync Batch Size must be 0 (no batching) or greater.')
            if record.stock_sync_batch_size > 1000:
                raise ValidationError('Stock Sync Batch Size should not exceed 1000 to avoid timeouts.')
    
    @api.constrains('pull_interval_minutes')
    def _check_pull_interval(self):
        """Validate pull order interval"""
        for record in self:
            if record.pull_interval_minutes < 1:
                raise ValidationError('Pull Order Interval must be at least 1 minute.')
    
    @api.constrains('job_cleanup_retention_days')
    def _check_job_cleanup_retention_days(self):
        """Validate job cleanup retention days"""
        for record in self:
            if record.job_cleanup_enabled and record.job_cleanup_retention_days < 1:
                raise ValidationError('Job Retention Days must be at least 1 day.')
    
    @api.constrains('job_cleanup_keep_count')
    def _check_job_cleanup_keep_count(self):
        """Validate job cleanup keep count"""
        for record in self:
            if record.job_cleanup_keep_count < 0:
                raise ValidationError('Keep Recent Jobs Count must be 0 (no limit) or greater.')
    
    @api.model
    def cron_auto_sync_stock_from_zortout(self):
        """Cron method to auto sync stock from Zortout based on stock_sync_interval_minutes"""
        from datetime import datetime, timedelta
        
        accounts = self.search([
            ('channel', '=', 'zortout'),
            ('active', '=', True),
            ('sync_enabled', '=', True),
            ('stock_sync_interval_minutes', '>', 0),
        ])
        
        for account in accounts:
            # Check if it's time to sync based on stock_sync_interval_minutes
            # Get the last stock sync job for this account
            last_stock_job = self.env['marketplace.job'].search([
                ('account_id', '=', account.id),
                ('job_type', '=', 'sync_stock_from_zortout'),
                ('state', '=', 'done'),
            ], order='started_at desc', limit=1)
            
            # Calculate if it's time to sync
            should_sync = False
            if not last_stock_job:
                # No previous sync, sync now
                should_sync = True
            else:
                # Check if interval has passed
                interval_minutes = account.stock_sync_interval_minutes or 10
                next_sync_time = last_stock_job.started_at + timedelta(minutes=interval_minutes)
                if datetime.now() >= next_sync_time:
                    should_sync = True
            
            # Also check if there's already a pending job (avoid duplicates)
            pending_job = self.env['marketplace.job'].search([
                ('account_id', '=', account.id),
                ('job_type', '=', 'sync_stock_from_zortout'),
                ('state', 'in', ['pending', 'running']),
            ], limit=1)
            
            if should_sync and not pending_job:
                # Get warehouse code from stock_location_id or use None (sync from all warehouses)
                warehouse_code = None
                if account.stock_location_id and account.stock_location_id.warehouse_id:
                    warehouse = account.stock_location_id.warehouse_id
                    warehouse_code = warehouse.code
                    
                    # Try to get Zortout warehouse code from config parameter
                    zortout_wh_code = self.env['ir.config_parameter'].sudo().get_param(
                        f'marketplace.zortout.warehouse_code.{warehouse.id}',
                        None
                    )
                    if zortout_wh_code:
                        warehouse_code = zortout_wh_code
                    else:
                        # If Odoo warehouse code is not in known Zortout codes, use None
                        known_zortout_codes = ['ODS001', 'ODS002', 'W0005', 'W0006']
                        if warehouse_code not in known_zortout_codes:
                            warehouse_code = None
                
                # Check if we need to split into batches
                # First, we need to know how many products we'll be syncing
                # Since we don't know the count yet, we'll create a job that will fetch first
                # and then split into batches if needed
                
                # For now, create a single job that will handle batching internally
                # The job will fetch products first, then decide if batching is needed
                batch_size = account.stock_sync_batch_size or 0
                
                if batch_size == 0:
                    # No batching - create single job
                    self.env['marketplace.job'].sudo().create({
                        'name': f'Sync Stock from Zortout - {account.name} (Auto)',
                        'job_type': 'sync_stock_from_zortout',
                        'account_id': account.id,
                        'priority': 'medium',
                        'payload': {
                            'warehouse_code': warehouse_code,
                            'sku_list': [],
                            'batch_index': 0,
                            'batch_total': 1,
                            'batch_size': 0,
                        },
                        'state': 'pending',
                        'next_run_at': fields.Datetime.now(),
                    })
                else:
                    # With batching, we need to fetch product count first
                    # Create a "preparation" job that will fetch and split
                    # For simplicity, we'll create jobs that fetch in batches directly
                    # The adapter's fetch_all_products will handle pagination
                    # We'll create multiple jobs for different page ranges
                    _logger.warning(f'📦 Stock sync batching enabled (batch_size={batch_size}) - will create batch jobs dynamically')
                    
                    # Create initial job that will fetch and split
                    self.env['marketplace.job'].sudo().create({
                        'name': f'Sync Stock from Zortout - {account.name} (Auto)',
                        'job_type': 'sync_stock_from_zortout',
                        'account_id': account.id,
                        'priority': 'medium',
                        'payload': {
                            'warehouse_code': warehouse_code,
                            'sku_list': [],
                            'batch_index': 0,
                            'batch_total': 1,  # Will be updated when products are fetched
                            'batch_size': batch_size,
                            'auto_split': True,  # Flag to indicate we should split after fetching
                        },
                        'state': 'pending',
                        'next_run_at': fields.Datetime.now(),
                    })
    
    @api.model
    def cron_auto_push_stock_to_marketplace(self):
        """Cron method to auto push stock to marketplace (WooCommerce, etc.) based on push_stock_interval_minutes"""
        from datetime import datetime, timedelta
        
        # Get accounts that need stock push (WooCommerce, Shopee, etc. - not Zortout)
        accounts = self.search([
            ('channel', '!=', 'zortout'),  # Zortout uses sync_stock_from_zortout instead
            ('active', '=', True),
            ('sync_enabled', '=', True),
            ('push_stock_interval_minutes', '>', 0),
        ])
        
        for account in accounts:
            # Check if it's time to push based on push_stock_interval_minutes
            # Get the last push stock job for this account
            last_push_job = self.env['marketplace.job'].search([
                ('account_id', '=', account.id),
                ('job_type', '=', 'push_stock'),
                ('state', '=', 'done'),
            ], order='started_at desc', limit=1)
            
            # Calculate if it's time to push
            should_push = False
            if not last_push_job:
                # No previous push, push now
                should_push = True
            else:
                # Check if interval has passed
                interval_minutes = account.push_stock_interval_minutes or 30
                next_push_time = last_push_job.started_at + timedelta(minutes=interval_minutes)
                if datetime.now() >= next_push_time:
                    should_push = True
            
            # Also check if there's already a pending job (avoid duplicates)
            pending_job = self.env['marketplace.job'].search([
                ('account_id', '=', account.id),
                ('job_type', '=', 'push_stock'),
                ('state', 'in', ['pending', 'in_progress']),
            ], limit=1)
            
            if should_push and not pending_job:
                # Check if there are any active product bindings
                if not account.shop_ids:
                    continue
                
                # Get all active bindings for all shops
                all_bindings = self.env['marketplace.product.binding'].search([
                    ('shop_id', 'in', account.shop_ids.ids),
                    ('active', '=', True),
                    ('exclude_push', '=', False),
                ])
                
                if not all_bindings:
                    continue
                
                # Group by shop
                shop_bindings = {}
                for binding in all_bindings:
                    shop_id = binding.shop_id.id
                    if shop_id not in shop_bindings:
                        shop_bindings[shop_id] = []
                    shop_bindings[shop_id].append(binding.id)
                
                # Create push stock job for each shop
                for shop_id, binding_ids in shop_bindings.items():
                    shop = self.env['marketplace.shop'].browse(shop_id)
                    
                    # Check batch size from account settings
                    batch_size = account.push_stock_batch_size or 0  # 0 = no batching
                    total_bindings = len(binding_ids)
                    
                    if batch_size > 0 and total_bindings > batch_size:
                        # Split into batches
                        batch_count = (total_bindings + batch_size - 1) // batch_size  # Ceiling division
                        
                        _logger.info(f'📦 Splitting {total_bindings} bindings into {batch_count} batches of {batch_size} for shop {shop.name} (Auto)')
                        
                        # Create batch jobs with staggered next_run_at to avoid overload
                        current_time = fields.Datetime.now()
                        for batch_idx in range(batch_count):
                            start_idx = batch_idx * batch_size
                            end_idx = min(start_idx + batch_size, total_bindings)
                            batch_binding_ids = binding_ids[start_idx:end_idx]
                            
                            # Stagger jobs: each batch starts 5 seconds after previous
                            batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                            
                            self.env['marketplace.job'].sudo().create({
                                'name': f'Push Stock to {account.channel.upper()} - {shop.name} (Auto Batch {batch_idx + 1}/{batch_count})',
                                'job_type': 'push_stock',
                                'account_id': account.id,
                                'shop_id': shop_id,
                                'priority': 'medium',  # Stock push is medium priority
                                'payload': {
                                    'binding_ids': batch_binding_ids,
                                    'batch_index': batch_idx,
                                    'batch_total': batch_count,
                                },
                                'state': 'pending',
                                'next_run_at': batch_next_run,
                            })
                        _logger.info(f'✅ Created {batch_count} auto push stock batch jobs for {account.channel} account {account.name}, shop {shop.name}')
                    else:
                        # No batching needed (batch_size = 0 or total_bindings <= batch_size)
                        self.env['marketplace.job'].sudo().create({
                            'name': f'Push Stock to {account.channel.upper()} - {shop.name} (Auto)',
                            'job_type': 'push_stock',
                            'account_id': account.id,
                            'shop_id': shop_id,
                            'priority': 'medium',  # Stock push is medium priority
                            'payload': {
                                'binding_ids': binding_ids,
                            },
                            'state': 'pending',
                            'next_run_at': fields.Datetime.now(),
                        })
                        _logger.info(f'✅ Created auto push stock job for {account.channel} account {account.name}, shop {shop.name}')
    
    @api.model
    def cron_auto_pull_orders(self):
        """Cron method to auto pull orders based on pull_interval_minutes for each account"""
        from datetime import datetime, timedelta
        
        # First, cleanup all Shopee pull_order jobs for accounts without tokens (BEFORE processing accounts)
        # This prevents jobs from accumulating
        shopee_accounts_no_token = self.search([
            ('channel', '=', 'shopee'),
            ('active', '=', True),
            ('sync_enabled', '=', True),
            ('pull_interval_minutes', '>', 0),
        ]).filtered(lambda a: not (a.access_token and a.refresh_token))
        
        if shopee_accounts_no_token:
            for account in shopee_accounts_no_token:
                # Delete any pending/in_progress pull_order jobs for this account
                pending_jobs = self.env['marketplace.job'].search([
                    ('account_id', '=', account.id),
                    ('job_type', '=', 'pull_order'),
                    ('state', 'in', ['pending', 'in_progress']),
                ])
                if pending_jobs:
                    _logger.info(f'🧹 Cleaning up {len(pending_jobs)} pending/in_progress pull_order jobs for Shopee account {account.name} (no token)')
                    pending_jobs.unlink()
        
        # Cleanup / disable Zortout pull orders completely (not supported)
        zortout_accounts = self.search([
            ('channel', '=', 'zortout'),
            ('active', '=', True),
        ])
        if zortout_accounts:
            zortout_jobs = self.env['marketplace.job'].search([
                ('account_id', 'in', zortout_accounts.ids),
                ('job_type', '=', 'pull_order'),
            ])
            if zortout_jobs:
                _logger.info(f'🧹 Removing {len(zortout_jobs)} pull_order job(s) for Zortout accounts (pull not supported)')
                zortout_jobs.unlink()
        
        # Get all active accounts (EXCLUDE Shopee accounts without tokens from the start)
        accounts = self.search([
            ('active', '=', True),
            ('sync_enabled', '=', True),
            ('pull_interval_minutes', '>', 0),
            ('channel', '!=', 'zortout'),
        ]).filtered(lambda a: not (a.channel == 'shopee' and not (a.access_token and a.refresh_token)))
        
        for account in accounts:
            # Double-check: Skip Shopee accounts that are not fully connected (defensive programming)
            if account.channel == 'shopee':
                has_access_token = bool(account.access_token)
                has_refresh_token = bool(account.refresh_token)
                if not has_access_token or not has_refresh_token:
                    _logger.warning(f'⚠️  Shopee account {account.name} (ID: {account.id}) has no token but passed filter - skipping (access_token: {has_access_token}, refresh_token: {has_refresh_token})')
                    continue
            
            if account.channel == 'zortout':
                _logger.debug(f'Skipping pull_order cron for Zortout account {account.name} - pull not supported')
                continue
            
            # Check if it's time to pull based on pull_interval_minutes
            # Get the last pull order job for this account
            last_pull_job = self.env['marketplace.job'].search([
                ('account_id', '=', account.id),
                ('job_type', '=', 'pull_order'),
                ('state', '=', 'done'),
            ], order='started_at desc', limit=1)
            
            # Calculate if it's time to pull
            should_pull = False
            if not last_pull_job:
                # No previous pull, pull now
                should_pull = True
            else:
                # Check if interval has passed
                interval_minutes = account.pull_interval_minutes or 5
                next_pull_time = last_pull_job.started_at + timedelta(minutes=interval_minutes)
                if datetime.now() >= next_pull_time:
                    should_pull = True
            
            if should_pull:
                # Create pull order jobs for all active shops
                for shop in account.shop_ids.filtered('active'):
                    # Check if there's already a pending or in_progress pull_order job for this shop
                    existing_job = self.env['marketplace.job'].search([
                        ('shop_id', '=', shop.id),
                        ('account_id', '=', account.id),
                        ('job_type', '=', 'pull_order'),
                        ('state', 'in', ['pending', 'in_progress']),
                    ], limit=1, order='id desc')
                    
                    if existing_job:
                        # Skip if there's already a pending or in_progress job
                        _logger.debug(f'Skipping pull_order job creation for shop {shop.name} (ID: {shop.id}) - job #{existing_job.id} already exists (state: {existing_job.state})')
                        continue
                    
                    # Create new pull_order job
                    job = self.env['marketplace.job'].sudo().create({
                        'name': f'Pull orders for {shop.name}',
                        'job_type': 'pull_order',
                        'shop_id': shop.id,
                        'account_id': account.id,
                        'priority': 'high',  # Orders are high priority
                        'payload': {},
                        'state': 'pending',
                        'next_run_at': fields.Datetime.now(),  # Set to now so it runs immediately
                    })
                    _logger.info(f'✅ Created auto pull order job #{job.id} for {account.channel} account {account.name}, shop {shop.name} (next_run_at: {job.next_run_at})')
    
    def action_run_all_pull_orders_now(self):
        """Run all pending pull_order jobs for this account immediately (priority queue)"""
        self.ensure_one()
        
        if self.channel == 'zortout':
            raise UserError('Pulling orders is not supported for Zortout. This account only syncs stock.')
        
        # Check if Shopee account has tokens
        if self.channel == 'shopee':
            has_access_token = bool(self.access_token)
            has_refresh_token = bool(self.refresh_token)
            if not has_access_token or not has_refresh_token:
                raise UserError(f'Cannot pull orders for Shopee account {self.name}: Account is not fully connected. Please connect the account first (missing access_token or refresh_token).')
        
        # Find all pending pull_order jobs for this account
        pending_jobs = self.env['marketplace.job'].search([
            ('job_type', '=', 'pull_order'),
            ('account_id', '=', self.id),
            ('state', '=', 'pending'),
        ])
        
        if not pending_jobs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Pending Jobs',
                    'message': 'No pending pull_order jobs found for this account.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Set all jobs to run now with high priority
        pending_jobs.write({
            'next_run_at': fields.Datetime.now(),
            'priority': 'high',
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Priority Queue Activated',
                'message': f'Set {len(pending_jobs)} pull_order job(s) to run immediately with high priority.',
                'type': 'success',
                'sticky': False,
            }
        }

    # -------------------------------------------------------------------------
    # Lazada operations (initial placeholder implementations)
    # -------------------------------------------------------------------------

    def _lazada_import_products(self, shop, payload=None, job=None):
        """Placeholder for Lazada product import logic"""
        self.ensure_one()
        shop = shop.sudo()
        payload = payload or {}

        message = (
            f'Lazada product import for shop {shop.name} has been queued. '
            f'Implementation is pending.'
        )
        _logger.warning(message)
        return {
            'status': 'pending',
            'message': message,
            'payload': payload,
        }

    def _lazada_update_images(self, shop, payload=None, job=None):
        """Placeholder for Lazada image update logic"""
        self.ensure_one()
        shop = shop.sudo()
        payload = payload or {}

        message = (
            f'Lazada image update for shop {shop.name} has been queued. '
            f'Implementation is pending.'
        )
        _logger.warning(message)
        return {
            'status': 'pending',
            'message': message,
            'payload': payload,
        }

    def _lazada_backfill_orders(self, shop, payload=None, job=None):
        """Backfill orders for a specific date from Lazada"""
        self.ensure_one()
        if self.channel != 'lazada':
            raise ValueError('Lazada order backfill only available for Lazada accounts')
        if not shop:
            raise ValueError('Shop is required for Lazada backfill')

        payload = payload or {}
        sync_date = payload.get('sync_date')
        start_dt = payload.get('start_datetime')
        end_dt = payload.get('end_datetime')

        if not start_dt or not end_dt:
            raise ValueError('start_datetime and end_datetime are required for backfill')

        start_dt = fields.Datetime.from_string(start_dt)
        end_dt = fields.Datetime.from_string(end_dt)

        adapter = self._get_adapter(shop)
        if self.channel == 'shopee':
            detailed_payloads = adapter.fetch_orders_list_with_details(
                since=start_dt,
                until=end_dt,
                time_range_field='create_time',
                page_size=100,
            )
            orders_payload = [adapter.parse_order_payload(p) for p in (detailed_payloads or [])]
        else:
            orders_payload = adapter.fetch_orders(start_dt, end_dt)

        total_orders = len(orders_payload)
        if job:
            job.write({
                'total_items': total_orders,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()

        result = self.env['marketplace.order'].sudo().create_from_payloads_bulk(
            shop, orders_payload, self.channel, batch_size=20)

        shop.sudo().write({'last_order_sync_at': end_dt})

        message = (
            f"Imported Lazada orders for {shop.name} on {sync_date} "
            f"({start_dt.strftime('%Y-%m-%d %H:%M')} - {end_dt.strftime('%Y-%m-%d %H:%M')}). "
            f"Created: {result.get('created', 0)}, Updated: {result.get('updated', 0)}, "
            f"Errors: {result.get('errors', 0)}"
        )

        return {
            'message': message,
            'created': result.get('created', 0),
            'updated': result.get('updated', 0),
            'errors': result.get('errors', 0),
            'fetched': total_orders,
        }

    def _woocommerce_backfill_orders(self, shop, payload=None, job=None):
        """Backfill orders for a specific date from WooCommerce"""
        self.ensure_one()
        if self.channel != 'woocommerce':
            raise ValueError('WooCommerce order backfill only available for WooCommerce accounts')
        if not shop:
            raise ValueError('Shop is required for WooCommerce backfill')

        payload = payload or {}
        sync_date = payload.get('sync_date')
        start_dt = payload.get('start_datetime')
        end_dt = payload.get('end_datetime')

        if not start_dt or not end_dt:
            if not sync_date:
                raise ValueError('sync_date is required for WooCommerce backfill')
            date_obj = fields.Date.from_string(sync_date)
            start_dt = datetime.combine(date_obj, datetime.min.time())
            end_dt = start_dt + timedelta(days=1)
        else:
            start_dt = fields.Datetime.from_string(start_dt)
            end_dt = fields.Datetime.from_string(end_dt)

        adapter = self._get_adapter(shop)
        if self.channel == 'shopee':
            detailed_payloads = adapter.fetch_orders_list_with_details(
                since=start_dt,
                until=end_dt,
                time_range_field='create_time',
                page_size=100,
            )
            orders_payload = [adapter.parse_order_payload(p) for p in (detailed_payloads or [])]
        else:
            orders_payload = adapter.fetch_orders(start_dt, end_dt)

        total_orders = len(orders_payload)
        if job:
            job.write({
                'total_items': total_orders,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()

        result = self.env['marketplace.order'].sudo().create_from_payloads_bulk(
            shop, orders_payload, self.channel, batch_size=20)

        shop.sudo().write({'last_order_sync_at': end_dt})

        message = (
            f"Imported WooCommerce orders for {shop.name} between "
            f"{start_dt.strftime('%Y-%m-%d %H:%M')} and {end_dt.strftime('%Y-%m-%d %H:%M')}. "
            f"Created: {result.get('created', 0)}, Updated: {result.get('updated', 0)}, "
            f"Errors: {result.get('errors', 0)}"
        )

        return {
            'message': message,
            'created': result.get('created', 0),
            'updated': result.get('updated', 0),
            'errors': result.get('errors', 0),
            'fetched': total_orders,
        }
    
    def action_pull_orders_wizard(self):
        """Open wizard to pull orders with custom date range"""
        self.ensure_one()
        return {
            'name': 'Pull Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.pull.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.id,
            },
        }
    
    order_auto_confirm = fields.Boolean(
        string='Auto Confirm Orders', default=False,
        help='Automatically confirm sale orders when pulled'
    )
    order_default_pricelist_id = fields.Many2one(
        'product.pricelist', string='Default Pricelist',
        help='Default pricelist for new orders'
    )
    
    # Sync settings
    pull_interval_minutes = fields.Integer(
        string='Pull Order Interval (minutes)', default=5,
        help='Interval between automatic order pulls (in minutes). Minimum: 1 minute. The system will pull orders automatically at this interval.',
        tracking=True
    )
    batch_size = fields.Integer(
        string='Batch Size', default=50,
        help='Number of items to process per batch'
    )
    last_sync_at = fields.Datetime(
        string='Last Sync At', readonly=True,
        help='Last successful synchronization timestamp'
    )

    @api.depends('shop_ids')
    def _compute_shop_count(self):
        for record in self:
            record.shop_count = len(record.shop_ids)

    def _get_adapter(self, shop=None):
        """Get the appropriate adapter instance for this account"""
        self.ensure_one()
        from . import adapters
        adapter_class = adapters.MarketplaceAdapters._get_adapter_class(self.channel)
        if not adapter_class:
            raise UserError(f'No adapter found for channel: {self.channel}')
        return adapter_class(self, shop)

    def action_connect_oauth(self):
        """Open OAuth authorization URL (not applicable for Zortout and WooCommerce)"""
        self.ensure_one()
        
        if self.channel == 'zortout':
            raise UserError('Zortout uses API key authentication. Please configure Store Name, API Key, and API Secret in the account settings.')
        
        if self.channel == 'woocommerce':
            raise UserError(
                'WooCommerce uses API key authentication. '
                'Please configure Store URL, Consumer Key, and Consumer Secret in the account settings. '
                'No OAuth authorization is required. Use "Test Connection" button to verify your credentials.'
            )
        
        _logger.warning(f"🔵 OAuth: action_connect_oauth called for account: {self.name} (ID: {self.id})")
        _logger.warning(f"🔵 OAuth: Channel: {self.channel}, Client ID: {self.client_id}")
        
        if not self.client_id:
            _logger.error("❌ OAuth: Client ID is missing!")
            raise UserError('Please configure Client ID first')
        
        adapter = self._get_adapter()
        _logger.warning(f"🔵 OAuth: Adapter created: {type(adapter).__name__}")
        
        auth_url = adapter.get_authorize_url()
        _logger.warning(f"🔵 OAuth: Authorization URL generated: {auth_url[:100]}...")
        
        return {
            'type': 'ir.actions.act_url',
            'url': auth_url,
            'target': 'new',
        }

    def action_refresh_token(self):
        """Refresh access token"""
        self.ensure_one()
        if not self.refresh_token:
            raise UserError('No refresh token available')
        
        adapter = self._get_adapter()
        try:
            token_data = adapter.refresh_access_token()
            self.write({
                'access_token': token_data.get('access_token'),
                'refresh_token': token_data.get('refresh_token', self.refresh_token),
                'access_token_expire_at': fields.Datetime.now() + timedelta(
                    seconds=token_data.get('expires_in', 3600)
                ),
            })
            self.message_post(body='Access token refreshed successfully')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': 'Token refreshed successfully',
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            _logger.error(f'Token refresh failed: {e}')
            raise UserError(f'Failed to refresh token: {e}')

    def _check_token_expiry(self):
        """Check and refresh token if expired"""
        self.ensure_one()
        if not self.access_token_expire_at:
            return False
        
        if fields.Datetime.now() >= self.access_token_expire_at - timedelta(minutes=5):
            try:
                self.action_refresh_token()
                return True
            except Exception as e:
                _logger.warning(f'Token refresh failed: {e}')
                return False
        return False

    @api.constrains('client_id', 'client_secret')
    def _check_credentials(self):
        for record in self:
            if record.channel and not record.client_id:
                raise ValidationError('Client ID is required for marketplace integration')

    def action_view_shops(self):
        """View shops for this account"""
        self.ensure_one()
        return {
            'name': 'Shops',
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.shop',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.id)],
            'context': {'default_account_id': self.id},
        }
    
    def _create_sync_export_attachment(self, export_data):
        """Create CSV attachment for skipped/not found/variation products"""
        self.ensure_one()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow([
            'Category',
            'Product ID',
            'Parent Product ID',
            'Variation ID',
            'Product Name',
            'SKU',
            'Type',
            'Reason',
        ])
        
        # Write skipped products
        for product in export_data.get('skipped_products', []):
            writer.writerow([
                'Skipped',
                product.get('product_id', ''),
                '',
                '',
                product.get('name', ''),
                product.get('sku', ''),
                product.get('type', ''),
                product.get('reason', ''),
            ])
        
        # Write not found products
        for product in export_data.get('not_found_products', []):
            writer.writerow([
                'Not Found',
                product.get('product_id', ''),
                '',
                '',
                product.get('name', ''),
                product.get('sku', ''),
                product.get('type', ''),
                product.get('reason', ''),
            ])
        
        # Write variations not found
        for variation in export_data.get('variations_not_found', []):
            writer.writerow([
                'Variation Not Found',
                '',
                variation.get('parent_product_id', ''),
                variation.get('variation_id', ''),
                variation.get('name', ''),
                variation.get('sku', ''),
                'variation',
                variation.get('reason', ''),
            ])
        
        # Write explicit error products (if provided)
        for product in export_data.get('errors', []):
            writer.writerow([
                'Error',
                product.get('product_id', ''),
                '',
                '',
                product.get('name', ''),
                product.get('sku', ''),
                product.get('type', ''),
                product.get('error', ''),
            ])
        
        # Get CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Encode to base64
        csv_bytes = csv_content.encode('utf-8-sig')  # UTF-8 with BOM for Excel compatibility
        csv_b64 = base64.b64encode(csv_bytes).decode('utf-8')
        
        # Create attachment
        filename = f'skipped_products_{self.name}_{export_data.get("sync_date", "").replace(":", "-").replace(" ", "_")}.csv'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': csv_b64,
            'mimetype': 'text/csv',
            'res_model': 'marketplace.account',
            'res_id': self.id,
        })
        return attachment

    def action_download_skipped_products(self):
        """Download CSV file containing skipped and not found products"""
        self.ensure_one()
        
        if not self.sync_export_data:
            raise UserError('No export data available. Please run product sync first.')
        
        try:
            export_data = json.loads(self.sync_export_data)
        except (json.JSONDecodeError, TypeError):
            raise UserError('Invalid export data. Please run product sync again.')
        
        attachment = self._create_sync_export_attachment(export_data)
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def _get_or_create_zortout_shop(self):
        """Ensure there is at least one shop for Zortout account and return it"""
        self.ensure_one()

        if self.channel != 'zortout':
            return self.env['marketplace.shop']

        shop_model = self.env['marketplace.shop'].with_context(active_test=False)
        shop = shop_model.search([('account_id', '=', self.id)], limit=1)

        if shop:
            if not shop.active:
                shop.write({'active': True})
            return shop

        # Determine default warehouse (use stock location warehouse if available)
        warehouse = False
        if self.stock_location_id and self.stock_location_id.warehouse_id:
            warehouse = self.stock_location_id.warehouse_id
        else:
            warehouse = self.env['stock.warehouse'].search(
                [('company_id', '=', self.company_id.id)],
                limit=1
            )

        shop_vals = {
            'name': f'Zortout - {self.name}',
            'external_shop_id': f'zortout-{self.id}',
            'account_id': self.id,
            'active': True,
            'timezone': 'Asia/Bangkok',
        }

        if warehouse:
            shop_vals['warehouse_id'] = warehouse.id

        shop = shop_model.create(shop_vals)
        _logger.info(f'✅ Auto-created Zortout shop {shop.name} (ID: {shop.id}) for account {self.name}')

        self.message_post(body=f'✅ Auto-created default Zortout shop: {shop.name}')
        return shop
    
    def action_import_products_from_zortout(self):
        """Import products from Zortout (create sync job)"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check credentials
        if not self.client_id or not self.client_secret or not self.access_token:
            raise UserError('Please configure Store Name, API Key, and API Secret first')
        
        # Get warehouse code from stock_location_id or default warehouse
        warehouse_code = None
        if self.stock_location_id and self.stock_location_id.warehouse_id:
            warehouse_code = self.stock_location_id.warehouse_id.code or self.stock_location_id.warehouse_id.name
        
        # Create sync job (skip images by default to avoid timeout)
        job = self.env['marketplace.job'].create({
            'name': f'Import Products from Zortout - {self.name}',
            'job_type': 'sync_product_from_zortout',
            'account_id': self.id,
            'priority': 'low',  # Product import is low priority (background task)
            'payload': {
                'trigger_uid': self.env.uid,
                'fetch_all': True,
                'warehouse_code': warehouse_code,
                'skip_images': True,  # Skip images to avoid timeout - use separate button for images
                'filters': {
                    'activestatus': 1,  # Active products only
                }
            },
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),  # Set to now so cron picks it up immediately
        })
        
        # Commit transaction to ensure job is saved
        self.env.cr.commit()
        
        # Post message
        self.message_post(
            body=f'Product import job created: <b>{job.name}</b>',
            subtype_xmlid='mail.mt_note'
        )
        
        # Trigger cron immediately to process this job
        _logger.warning(f'🚀 Triggering cron_run_jobs for job {job.id}: {job.name}')
        try:
            # Call cron_run_jobs with this specific job ID
            self.env['marketplace.job'].sudo().cron_run_jobs(job_ids=[job.id])
        except Exception as e:
            _logger.error(f'Failed to trigger cron for job {job.id}: {e}', exc_info=True)
            # If cron fails, still return success - cron will pick it up later
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Product import job "{job.name}" has been created and will start processing shortly.<br/>Note: Images are skipped to avoid timeout. Use "อัพเดทรูปภาพสินค้า" button to sync images separately.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_import_products_from_zortout_sync(self, job=None, payload=None):
        """Background task: import products from Zortout and create/update bindings"""
        self.ensure_one()
        self = self.sudo().with_company(self.company_id)

        if self.channel != 'zortout':
            raise ValueError('This method is only available for Zortout accounts')

        if not self.sync_enabled:
            raise ValueError('Sync is disabled for this account')

        if not self.client_id or not self.client_secret or not self.access_token:
            raise ValueError('Please configure Store Name, API Key, and API Secret first')

        payload = payload or {}

        fetch_all = payload.get('fetch_all', True)
        skip_images = payload.get('skip_images', True)
        update_images_only = payload.get('update_images_only', False)
        warehouse_code = payload.get('warehouse_code')
        filters = payload.get('filters') or {}
        page = payload.get('page') or 1
        limit = payload.get('limit') or 500
        commit_interval = payload.get('commit_interval') or 50
        if commit_interval < 1:
            commit_interval = 25

        shop = self._get_or_create_zortout_shop()
        if not shop:
            raise ValueError('Failed to determine shop for Zortout account')

        adapter = self._get_adapter(shop)
        _logger.info(f'🔄 Starting Zortout product import for account {self.id} (shop {shop.id})')

        # Fetch products from Zortout
        if fetch_all:
            products = adapter.fetch_all_products(warehouse_code=warehouse_code, **filters)
        else:
            result = adapter.fetch_products(
                page=page,
                limit=limit,
                warehouse_code=warehouse_code,
                **filters
            )
            products = result.get('products', [])

        total_products = len(products)
        _logger.info(f'📦 Fetched {total_products} Zortout products (fetch_all={fetch_all})')

        if job:
            job._update_progress(0, total_products if total_products else 1)

        def to_float(value):
            try:
                if value in (None, '', False):
                    return 0.0
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        def get_uom(unit_name):
            if not unit_name:
                return default_uom
            uom = self.env['uom.uom'].search([
                ('name', '=', unit_name)
            ], limit=1)
            if not uom:
                uom = self.env['uom.uom'].search([
                    ('name', 'ilike', unit_name)
                ], limit=1)
            return uom or default_uom

        def get_category(category_name):
            if not category_name:
                return default_categ
            category = self.env['product.category'].search([
                ('name', '=', category_name)
            ], limit=1)
            if not category:
                category = self.env['product.category'].create({
                    'name': category_name,
                })
            return category

        image_cache = {}
        image_session = None
        image_timeout = payload.get('image_timeout') or 12
        image_batch_size = max(1, int(payload.get('image_batch_size') or 50))
        image_worker_count = max(1, min(int(payload.get('image_workers') or 8), 16))

        if not skip_images:
            image_session = requests.Session()
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.4,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["GET"],
            )
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_connections=image_worker_count * 2,
                pool_maxsize=image_worker_count * 2,
            )
            image_session.mount('http://', adapter)
            image_session.mount('https://', adapter)

        def download_image(image_url):
            if not image_url:
                return None

            if image_url in image_cache:
                return image_cache[image_url]

            try:
                session = image_session or requests
                response = session.get(image_url, timeout=image_timeout)
                response.raise_for_status()
                encoded = base64.b64encode(response.content)
                image_cache[image_url] = encoded
                return encoded
            except Exception as exc:
                _logger.warning(f'⚠️ Failed to download image {image_url}: {exc}')
                return None

        def fetch_image_for_product(image_urls):
            if not image_urls:
                return None, None
            for image_url in image_urls:
                image_data = download_image(image_url)
                if image_data:
                    return image_data, image_url
            return None, None

        def process_image_batch(jobs):
            if not jobs:
                return

            with ThreadPoolExecutor(max_workers=image_worker_count) as executor:
                future_map = {
                    executor.submit(fetch_image_for_product, job['image_urls']): job
                    for job in jobs
                }
                for future in as_completed(future_map):
                    job_info = future_map[future]
                    product_id = job_info['product_id']
                    sku_code = job_info['sku']
                    source_product_id = job_info['source_product_id']
                    source_product_name = job_info['source_product_name']
                    image_data, image_url = future.result()

                    if image_data:
                        product_rec = product_model.browse(product_id)
                        try:
                            product_rec.product_tmpl_id.sudo().write({'image_1920': image_data})
                            stats['images_updated'] += 1
                        except Exception as image_write_error:
                            stats['errors'] += 1
                            error_details.append({
                                'product_id': source_product_id,
                                'name': source_product_name,
                                'sku': sku_code,
                                'error': f'Failed to write image: {image_write_error}',
                            })
                            _logger.error(
                                '❌ Failed to apply image for product %s (%s): %s',
                                sku_code, image_url, image_write_error,
                                exc_info=True
                            )
                    else:
                        _logger.warning(f'⚠️ Could not update image for product {sku_code}')
                        error_details.append({
                            'product_id': source_product_id,
                            'name': source_product_name,
                            'sku': sku_code,
                            'error': 'Image download failed for all provided URLs',
                        })

            self.env.cr.commit()
            jobs.clear()

        default_uom = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not default_uom:
            default_uom = self.env['uom.uom'].search([], limit=1)

        default_categ = self.env.ref('product.product_category_all', raise_if_not_found=False)

        # Determine purchase UoM field name (Odoo 19 uses purchase_uom_id)
        if 'purchase_uom_id' in self.env['product.template']._fields:
            purchase_uom_field = 'purchase_uom_id'
        elif 'uom_po_id' in self.env['product.template']._fields:
            purchase_uom_field = 'uom_po_id'
        else:
            purchase_uom_field = None

        product_model = self.env['product.product'].with_context(active_test=False)
        binding_model = self.env['marketplace.product.binding'].with_context(active_test=False)

        stats = {
            'total_products': total_products,
            'processed_products': 0,
            'created_products': 0,
            'updated_products': 0,
            'bindings_created': 0,
            'bindings_updated': 0,
            'skipped_products': 0,
            'images_updated': 0,
            'errors': 0,
        }
        skipped_details = []
        error_details = []

        type_mapping = {
            0: ('consu', True, True),     # Goods / stockable (treated as consumable in Odoo 19)
            1: ('service', True, False),  # Service
            2: ('consu', True, True),     # Consumable
        }

        image_jobs = []

        for index, product_data in enumerate(products, start=1):
            stats['processed_products'] += 1
            sku = (product_data.get('sku') or '').strip()

            if not sku:
                stats['skipped_products'] += 1
                skipped_details.append({
                    'product_id': product_data.get('id'),
                    'name': product_data.get('name'),
                    'reason': 'Missing SKU',
                })
                continue

            try:
                # Find existing Odoo product by SKU (company-specific first)
                product = product_model.search([
                    ('default_code', '=', sku),
                    ('company_id', '=', self.company_id.id),
                ], limit=1)

                if not product:
                    product = product_model.search([
                        ('default_code', '=', sku),
                        ('company_id', '=', False),
                    ], limit=1)

                if not product and update_images_only:
                    stats['skipped_products'] += 1
                    skipped_details.append({
                        'product_id': product_data.get('id'),
                        'name': product_data.get('name'),
                        'sku': sku,
                        'reason': 'Product not found in Odoo (images-only mode)',
                    })
                    continue

                product_type_value, sale_ok, purchase_ok = type_mapping.get(
                    product_data.get('producttype'),
                    type_mapping[0]
                )
                price = to_float(product_data.get('sellprice'))
                cost = to_float(product_data.get('purchaseprice'))
                category = get_category(product_data.get('category'))
                uom = get_uom(product_data.get('unittext'))
                product_active = bool(product_data.get('active', True))

                raw_barcode = (product_data.get('barcode') or '').strip()

                if not product:
                    # Create product template and variant
                    template_vals = {
                        'name': product_data.get('name') or sku,
                        'type': product_type_value,
                        'sale_ok': sale_ok,
                        'purchase_ok': purchase_ok,
                        'list_price': price,
                        'standard_price': cost,
                        'company_id': self.company_id.id,
                        'uom_id': uom.id if uom else False,
                        'categ_id': category.id if category else False,
                        'description_sale': product_data.get('description') or False,
                        'active': product_active,
                    }
                    if purchase_uom_field:
                        template_vals[purchase_uom_field] = uom.id if uom else False
                    template = self.env['product.template'].sudo().create(template_vals)
                    product = template.product_variant_id
                    product_write_vals = {
                        'default_code': sku,
                    }
                    barcode_value = False
                    if raw_barcode:
                        conflict = product_model.search([
                            ('barcode', '=', raw_barcode),
                        ], limit=1)
                        if conflict:
                            _logger.info(
                                'Skipping barcode %s for SKU %s because it is already used by %s',
                                raw_barcode, sku, conflict.display_name
                            )
                        else:
                            barcode_value = raw_barcode
                    if barcode_value:
                        product_write_vals['barcode'] = barcode_value
                    product.sudo().write(product_write_vals)
                    stats['created_products'] += 1
                    _logger.info(f'✅ Created product {product.name} (SKU: {sku}) from Zortout')
                else:
                    if not update_images_only:
                        barcode_value = False
                        if raw_barcode:
                            if product.barcode == raw_barcode:
                                barcode_value = raw_barcode
                            else:
                                conflict = product_model.search([
                                    ('barcode', '=', raw_barcode),
                                    ('id', '!=', product.id),
                                ], limit=1)
                                if conflict:
                                    _logger.info(
                                        'Skipping barcode update for SKU %s because barcode %s is already used by %s',
                                        sku, raw_barcode, conflict.display_name
                                    )
                                else:
                                    barcode_value = raw_barcode

                        product.sudo().write({
                            'name': product_data.get('name') or sku,
                            'default_code': sku,
                            **({'barcode': barcode_value} if barcode_value else {}),
                        })
                        template_updates = {
                            'name': product_data.get('name') or sku,
                            'list_price': price,
                            'sale_ok': sale_ok,
                            'purchase_ok': purchase_ok,
                            'type': product_type_value,
                            'active': product_active,
                        }
                        if cost:
                            template_updates['standard_price'] = cost
                        if category:
                            template_updates['categ_id'] = category.id
                        if product_data.get('description'):
                            template_updates['description_sale'] = product_data.get('description')
                        if purchase_uom_field:
                            template_updates[purchase_uom_field] = uom.id if uom else False
                        product.product_tmpl_id.sudo().write(template_updates)
                        stats['updated_products'] += 1

                # Update images if requested
                if not skip_images:
                    image_urls = product_data.get('imageList') or []
                    if not image_urls and product_data.get('imagepath'):
                        image_urls = [product_data.get('imagepath')]

                    if image_urls:
                        image_jobs.append({
                            'product_id': product.id,
                            'sku': sku,
                            'source_product_id': product_data.get('id'),
                            'source_product_name': product_data.get('name'),
                            'image_urls': image_urls,
                        })

                    if len(image_jobs) >= image_batch_size:
                        process_image_batch(image_jobs)

                if not update_images_only:
                    external_product_id = product_data.get('variationid') or product_data.get('id')
                    binding_vals = {
                        'external_sku': sku,
                        'external_product_id': str(external_product_id) if external_product_id else False,
                        'active': product_active,
                    }

                    binding = binding_model.search([
                        ('external_sku', '=', sku),
                        ('shop_id', '=', shop.id),
                    ], limit=1)

                    if binding:
                        binding.sudo().write(binding_vals)
                        stats['bindings_updated'] += 1
                    else:
                        binding_vals.update({
                            'product_id': product.id,
                            'shop_id': shop.id,
                        })
                        binding_model.sudo().create(binding_vals)
                        stats['bindings_created'] += 1

                if index % commit_interval == 0:
                    if job:
                        job._update_progress(index, total_products if total_products else 1)
                    self.env.cr.commit()

            except Exception as error:
                stats['errors'] += 1
                error_details.append({
                    'product_id': product_data.get('id'),
                    'name': product_data.get('name'),
                    'sku': sku,
                    'error': str(error),
                })
                _logger.error(f'❌ Failed to process Zortout product {sku}: {error}', exc_info=True)

        # Flush remaining image downloads
        if image_jobs:
            process_image_batch(image_jobs)

        if image_session:
            image_session.close()

        # Final progress update & commit
        if job:
            job._update_progress(total_products, total_products if total_products else 1)
        self.env.cr.commit()

        # Store export data for download
        export_payload = {
            'sync_date': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'skipped_products': skipped_details,
            'errors': error_details,
        }
        self.write({
            'sync_export_data': json.dumps(export_payload, ensure_ascii=False),
            'last_sync_at': fields.Datetime.now(),
        })

        attachment = None
        download_url = False
        if stats['errors'] > 0 or stats['skipped_products'] > 0:
            attachment = self._create_sync_export_attachment(export_payload)
            download_url = f'/web/content/{attachment.id}?download=true'
        elif stats['errors'] == 0 and stats['skipped_products'] == 0:
            self.write({'sync_export_data': False})

        summary_message = (
            f'✅ Zortout product import completed.<br/>'
            f'- Total fetched: {stats["total_products"]}<br/>'
            f'- Processed: {stats["processed_products"]}<br/>'
            f'- Created: {stats["created_products"]}<br/>'
            f'- Updated: {stats["updated_products"]}<br/>'
            f'- Bindings created: {stats["bindings_created"]}<br/>'
            f'- Bindings updated: {stats["bindings_updated"]}<br/>'
            f'- Images updated: {stats["images_updated"]}<br/>'
            f'- Skipped: {stats["skipped_products"]}<br/>'
            f'- Errors: {stats["errors"]}'
        )

        if download_url:
            summary_message += f'<br/><a href="{download_url}" target="_blank">📄 ดาวน์โหลดรายงานข้อผิดพลาด</a>'

        self.message_post(body=summary_message, subtype_xmlid='mail.mt_note')

        notify_uid = payload.get('trigger_uid') or (self.env.uid if self.env.uid else False)
        if not notify_uid and job:
            notify_uid = job.create_uid.id
        notify_user = self.env['res.users'].browse(notify_uid) if notify_uid else False
        if notify_user and notify_user.exists():
            notify_message = (
                f'สรุปการนำเข้าสินค้า Zortout<br/>'
                f'- ทั้งหมด: {stats["total_products"]}<br/>'
                f'- สร้างใหม่: {stats["created_products"]}<br/>'
                f'- อัปเดต: {stats["updated_products"]}<br/>'
                f'- ข้าม: {stats["skipped_products"]}<br/>'
                f'- Error: {stats["errors"]}'
            )
            if download_url:
                notify_message += (
                    f'<br/><a class="btn btn-primary" href="{download_url}" target="_blank">'
                    f'ดาวน์โหลดรายงานข้อผิดพลาด</a>'
                )
            try:
                notify_user.notify_success(
                    notify_message,
                    title='นำเข้าสินค้า Zortout เสร็จแล้ว',
                    sticky=True,
                )
            except Exception as notify_err:
                _logger.warning('Failed to send notification to user %s: %s', notify_user.ids, notify_err)

        result = {
            'status': 'success',
            'message': 'Zortout product import completed',
            'summary': stats,
        }
        if skipped_details:
            result['skipped'] = skipped_details[:50]
        if error_details:
            result['errors_detail'] = error_details[:50]
        if attachment:
            result['error_report_attachment_id'] = attachment.id
            result['error_report_url'] = download_url
        return result
    
    def action_update_product_images(self):
        """Update product images from Zortout (create sync job for images only)"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check credentials
        if not self.client_id or not self.client_secret or not self.access_token:
            raise UserError('Please configure Store Name, API Key, and API Secret first')
        
        # Get warehouse code from stock_location_id or default warehouse
        warehouse_code = None
        if self.stock_location_id and self.stock_location_id.warehouse_id:
            warehouse_code = self.stock_location_id.warehouse_id.code or self.stock_location_id.warehouse_id.name
        
        # Check if warehouse code is in known codes, if not set to None
        if warehouse_code:
            known_zortout_codes = ['ODS001', 'ODS002', 'W0005', 'W0006']
            if warehouse_code not in known_zortout_codes:
                warehouse_code = None
        
        # Create sync job for images only
        # We'll fetch all products and update images for existing products
        job = self.env['marketplace.job'].create({
            'name': f'Update Product Images from Zortout - {self.name}',
            'job_type': 'sync_product_from_zortout',
            'account_id': self.id,
            'priority': 'low',  # Image update is low priority (background task)
            'payload': {
                'fetch_all': True,
                'warehouse_code': warehouse_code,
                'skip_images': False,  # Enable image download
                'update_images_only': True,  # Only update images for existing products
                'image_batch_size': 50,  # Download images in batches of 50
                'filters': {
                    'activestatus': 1,  # Active products only
                }
            },
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),  # Set to now so cron picks it up immediately
        })
        
        # Commit transaction to ensure job is saved
        self.env.cr.commit()
        
        # Post message
        self.message_post(
            body=f'Product image update job created: <b>{job.name}</b>',
            subtype_xmlid='mail.mt_note'
        )
        
        # Trigger cron immediately to process this job
        _logger.warning(f'🚀 Triggering cron_run_jobs for image update job {job.id}: {job.name}')
        try:
            # Call cron_run_jobs with this specific job ID
            self.env['marketplace.job'].sudo().cron_run_jobs(job_ids=[job.id])
        except Exception as e:
            _logger.error(f'Failed to trigger cron for job {job.id}: {e}', exc_info=True)
            # If cron fails, still return success - cron will pick it up later
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Product image update job "{job.name}" has been created and will start processing shortly.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_enable_track_inventory_wizard(self):
        """Open wizard to enable Track Inventory for products"""
        self.ensure_one()
        
        return {
            'name': 'Enable Track Inventory',
            'type': 'ir.actions.act_window',
            'res_model': 'enable.track.inventory.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_filter_by_sku': True,  # Default: filter by SKU (Zortout products)
                'default_filter_by_type': 'consu',  # Default: Goods only
                'default_filter_tracking': 'all',  # Default: Update all (including those with tracking='lot')
            }
        }
    
    def action_apply_inventory_all_products(self):
        """Apply inventory adjustment for all products with inventory_quantity != 0"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        _logger.warning(f'🔧 Applying inventory adjustment for all products...')
        
        # Find all quants with inventory_quantity != 0
        quants = self.env['stock.quant'].sudo().search([
            ('inventory_quantity', '!=', 0),
        ])
        
        total_count = len(quants)
        _logger.warning(f'📦 Found {total_count} quants with inventory_quantity != 0')
        
        if total_count == 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Action Needed',
                    'message': 'No quants found with inventory_quantity != 0. All inventory adjustments have been applied.',
                    'type': 'info',
                    'sticky': True,
                }
            }
        
        # Apply inventory adjustment
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for idx, quant in enumerate(quants, 1):
            try:
                quant.action_apply_inventory()
                updated_count += 1
                
                # Commit every 100 products
                if updated_count % 100 == 0:
                    self.env.cr.commit()
                    _logger.warning(f'📊 Progress: {updated_count}/{total_count} quants updated')
                
            except Exception as e:
                skipped_count += 1
                error_msg = f"Quant {quant.product_id.default_code or quant.product_id.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg, exc_info=True)
        
        # Final commit
        self.env.cr.commit()
        
        _logger.warning(f'✅ Inventory adjustment completed: {updated_count} updated, {skipped_count} skipped')
        
        # Prepare result message
        message_parts = []
        message_parts.append(f'<b>Inventory Adjustment Completed:</b><br/>')
        message_parts.append(f'✅ Updated: {updated_count} quants<br/>')
        message_parts.append(f'📦 Total quants found: {total_count}<br/>')
        if skipped_count > 0:
            message_parts.append(f'⚠️ Skipped: {skipped_count} quants<br/>')
        message_parts.append(f'<br/><b>💡 Next Steps:</b><br/>')
        message_parts.append(f'1. Refresh the product page (F5)<br/>')
        message_parts.append(f'2. Check Quantity On Hand in products<br/>')
        if errors:
            message_parts.append(f'<br/><b>Errors ({min(len(errors), 10)} of {len(errors)}):</b><br/>')
            for error in errors[:10]:
                message_parts.append(f'• {error}<br/>')
        
        message = ''.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Inventory Adjustment Completed',
                'message': message,
                'type': 'success' if skipped_count == 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_fix_track_inventory_all_products(self):
        """Quick fix: Enable Track Inventory checkbox for all Zortout products"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        _logger.warning(f'🔧 Quick fix: Enabling Track Inventory checkbox for all Zortout products...')
        
        # Find all products with SKU (likely from Zortout) that are Goods type
        # Update products that don't have tracking='lot' OR is_storable=False
        domain = [
            ('type', '=', 'consu'),  # Goods type
            ('default_code', '!=', False),  # Has SKU
        ]
        
        all_products = self.env['product.template'].sudo().search(domain)
        
        # Filter products that need fixing (tracking != 'none' OR is_storable=False)
        products = all_products.filtered(lambda p: p.tracking != 'none' or not p.is_storable)
        total_count = len(products)
        
        _logger.warning(f'📦 Found {total_count} products that need fixing')
        _logger.warning(f'   - Products with tracking != none: {len(all_products.filtered(lambda p: p.tracking != "none"))}')
        _logger.warning(f'   - Products with is_storable=False: {len(all_products.filtered(lambda p: not p.is_storable))}')
        
        if total_count == 0:
            # Check if all products already have tracking='none' AND is_storable=True
            all_count = len(all_products)
            none_count = len(all_products.filtered(lambda p: p.tracking == 'none'))
            storable_count = len(all_products.filtered(lambda p: p.is_storable))
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Already Fixed',
                    'message': f'All products already have tracking=\'none\' (By Quantity) and is_storable=True.<br/>Total products: {all_count}<br/>With tracking=\'none\' (By Quantity): {none_count}<br/>With is_storable=True: {storable_count}<br/><br/>💡 If checkbox still not checked in UI, try:<br/>1. Refresh the page (F5)<br/>2. Logout and login again<br/>3. Clear browser cache',
                    'type': 'info',
                    'sticky': True,
                }
            }
        
        # Update all products to tracking='none' (By Quantity)
        updated_count = 0
        skipped_count = 0
        errors = []
        
        for idx, product in enumerate(products, 1):
            try:
                # Force update tracking to 'none' (By Quantity) AND is_storable=True to enable checkbox
                # In Odoo 19, tracking='none' with is_storable=True shows "Track Inventory? By Quantity"
                # BUT: checkbox visibility is controlled by 'is_storable' field
                # - If is_storable=False, checkbox will be HIDDEN (invisible="not is_storable")
                # - We need to set is_storable=True to show the checkbox
                update_vals = {}
                
                if product.tracking != 'none':
                    update_vals['tracking'] = 'none'  # "By Quantity"
                
                if not product.is_storable:
                    update_vals['is_storable'] = True  # Show Track Inventory checkbox in UI
                
                # Also ensure type is 'consu' (Goods)
                if product.type != 'consu':
                    update_vals['type'] = 'consu'
                
                if update_vals:
                    product.write(update_vals)
                    _logger.warning(f'✅ Updated product {product.default_code}: {update_vals}')
                
                updated_count += 1
                
                # Commit every 100 products to avoid long transaction
                if updated_count % 100 == 0:
                    self.env.cr.commit()
                    _logger.warning(f'📊 Progress: {updated_count}/{total_count} products updated')
                
            except Exception as e:
                skipped_count += 1
                error_msg = f"Product {product.default_code or product.name}: {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg, exc_info=True)
        
        # Final commit
        self.env.cr.commit()
        
        _logger.warning(f'✅ Quick fix completed: {updated_count} updated, {skipped_count} skipped')
        
        # Prepare result message
        message_parts = []
        message_parts.append(f'<b>Quick Fix Completed:</b><br/>')
        message_parts.append(f'✅ Updated: {updated_count} products<br/>')
        message_parts.append(f'📦 Total products found: {total_count}<br/>')
        if skipped_count > 0:
            message_parts.append(f'⚠️ Skipped: {skipped_count} products<br/>')
        message_parts.append(f'<br/><b>💡 Next Steps:</b><br/>')
        message_parts.append(f'1. Refresh the product page (F5)<br/>')
        message_parts.append(f'2. If checkbox still not checked, logout and login again<br/>')
        message_parts.append(f'3. Clear browser cache if needed<br/>')
        if errors:
            message_parts.append(f'<br/><b>Errors ({min(len(errors), 10)} of {len(errors)}):</b><br/>')
            for error in errors[:10]:
                message_parts.append(f'• {error}<br/>')
        
        message = ''.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Quick Fix Completed',
                'message': message,
                'type': 'success' if skipped_count == 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_sync_stock_from_zortout(self):
        """Sync stock from Zortout (create sync job)"""
        _logger.warning(f'🔘 Button clicked: action_sync_stock_from_zortout for account {self.id}: {self.name}')
        self.ensure_one()
        
        if self.channel != 'zortout':
            _logger.error(f'❌ Channel mismatch: {self.channel} (expected zortout)')
            raise UserError('This action is only available for Zortout accounts')
        
        if not self.sync_enabled:
            _logger.error(f'❌ Sync disabled for account {self.name}')
            raise UserError('Please enable sync for this account first')
        
        # Check credentials
        if not self.client_id or not self.client_secret or not self.access_token:
            _logger.error(f'❌ Missing credentials for account {self.name}')
            raise UserError('Please configure Store Name, API Key, and API Secret first')
        
        # Get warehouse code from stock_location_id or default warehouse
        warehouse_code = None
        warehouse_name = None
        _logger.warning(f'🔍 Checking stock_location_id: {self.stock_location_id.id if self.stock_location_id else None} - {self.stock_location_id.complete_name if self.stock_location_id else "None"}')
        
        if self.stock_location_id:
            _logger.warning(f'   Location name: {self.stock_location_id.name}')
            _logger.warning(f'   Location complete_name: {self.stock_location_id.complete_name}')
            _logger.warning(f'   Location warehouse_id: {self.stock_location_id.warehouse_id.id if self.stock_location_id.warehouse_id else None}')
            
            if self.stock_location_id.warehouse_id:
                warehouse = self.stock_location_id.warehouse_id
                warehouse_name = warehouse.name
                warehouse_code = warehouse.code
                _logger.warning(f'   Warehouse name: {warehouse_name}')
                _logger.warning(f'   Warehouse code (Odoo): {warehouse_code}')
                
                # Note: Odoo warehouse code (Short Name) is limited to 5 characters
                # But Zortout warehouse codes can be longer (e.g., ODS001 = 6 chars)
                # We'll try to use the Odoo code first, but if it fails, we'll sync without warehouse filter
                # The user can also manually specify the correct Zortout warehouse code in a config parameter
                
                # Try to get Zortout warehouse code from config parameter (if set)
                zortout_wh_code = self.env['ir.config_parameter'].sudo().get_param(
                    f'marketplace.zortout.warehouse_code.{warehouse.id}',
                    None
                )
                if zortout_wh_code:
                    _logger.warning(f'   Using Zortout warehouse code from config: {zortout_wh_code}')
                    warehouse_code = zortout_wh_code
                else:
                    _logger.warning(f'   Using Odoo warehouse code: {warehouse_code}')
                    _logger.warning(f'   ⚠️ Odoo warehouse code may not match Zortout code (Odoo max 5 chars, Zortout can be longer)')
                    _logger.warning(f'   💡 Tip: To use specific Zortout warehouse code, set System Parameter: marketplace.zortout.warehouse_code.{warehouse.id}')
                    _logger.warning(f'   💡 Or: Leave Stock Location empty to sync from all warehouses')
                    
                    # If Odoo warehouse code is likely incorrect (e.g., doesn't match any known Zortout codes),
                    # we'll set it to None to sync from all warehouses
                    # Known Zortout warehouse codes from the list: ODS001, ODS002, W0005, W0006
                    known_zortout_codes = ['ODS001', 'ODS002', 'W0005', 'W0006']
                    if warehouse_code not in known_zortout_codes:
                        _logger.warning(f'   ⚠️ Warehouse code "{warehouse_code}" not in known Zortout codes - will sync from all warehouses')
                        warehouse_code = None  # Don't use incorrect warehouse code
            else:
                _logger.error(f'   ❌ Location {self.stock_location_id.complete_name} has no warehouse_id!')
        else:
            _logger.error(f'   ❌ No stock_location_id configured!')
        
        if not warehouse_code:
            _logger.warning(f'⚠️ No warehouse code found - will sync all products from all warehouses')
            _logger.warning(f'💡 Tip: To sync from specific warehouse, set Stock Location with Warehouse')
            _logger.warning(f'💡 Note: If Odoo warehouse code (max 5 chars) doesn\'t match Zortout code, sync will work without warehouse filter')
        
        _logger.warning(f'✅ Validation passed. Creating job with warehouse_code: {warehouse_code or "None (all warehouses)"}')
        
        # Create sync job
        _logger.warning(f'📝 Creating marketplace job...')
        # Check batch size
        batch_size = self.stock_sync_batch_size or 0
        current_time = fields.Datetime.now()
        
        if batch_size == 0:
            # No batching - create single job
            job = self.env['marketplace.job'].create({
                'name': f'Sync Stock from Zortout - {self.name}',
                'job_type': 'sync_stock_from_zortout',
                'account_id': self.id,
                'priority': 'medium',
                'payload': {
                    'warehouse_code': warehouse_code,
                    'sku_list': [],
                    'batch_index': 0,
                    'batch_total': 1,
                    'batch_size': 0,
                },
                'state': 'pending',
                'next_run_at': current_time,
            })
        else:
            # With batching - create job with auto_split flag
            job = self.env['marketplace.job'].create({
                'name': f'Sync Stock from Zortout - {self.name}',
                'job_type': 'sync_stock_from_zortout',
                'account_id': self.id,
                'priority': 'medium',
                'payload': {
                    'warehouse_code': warehouse_code,
                    'sku_list': [],
                    'batch_index': 0,
                    'batch_total': 1,
                    'batch_size': batch_size,
                    'auto_split': True,  # Flag to indicate we should split after fetching
                },
                'state': 'pending',
                'next_run_at': current_time,
            })
        _logger.warning(f'✅ Job created: ID={job.id}, Name={job.name}, State={job.state}')
        
        # Commit transaction to ensure job is saved
        _logger.warning(f'💾 Committing transaction...')
        self.env.cr.commit()
        _logger.warning(f'✅ Transaction committed')
        
        # Post message
        self.message_post(
            body=f'Stock sync job created: <b>{job.name}</b>',
            subtype_xmlid='mail.mt_note'
        )
        
        # Trigger cron immediately to process this job
        _logger.warning(f'🚀 Triggering cron_run_jobs for stock sync job {job.id}: {job.name}')
        try:
            # Call cron_run_jobs with this specific job ID
            self.env['marketplace.job'].sudo().cron_run_jobs(job_ids=[job.id])
            _logger.warning(f'✅ cron_run_jobs completed for job {job.id}')
        except Exception as e:
            _logger.error(f'❌ Failed to trigger cron for job {job.id}: {e}', exc_info=True)
            # If cron fails, still return success - cron will pick it up later
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Stock sync job "{job.name}" has been created and will start processing shortly.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_get_warehouses(self):
        """Get list of warehouses from Zortout"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check credentials
        if not self.client_id or not self.client_secret or not self.access_token:
            raise UserError('Please configure Store Name, API Key, and API Secret first')
        
        adapter = self._get_adapter(shop=None)
        _logger.warning(f'🔍 Getting warehouses from Zortout...')
        
        try:
            result = adapter.get_warehouses(page=1, limit=500)
            warehouses = result.get('warehouses', [])
            total_count = result.get('count', 0)
            
            # Prepare message
            messages = []
            messages.append(f'<b>Found {total_count} warehouse(s):</b><br/><br/>')
            
            for idx, wh in enumerate(warehouses, 1):
                wh_code = wh.get('code', 'N/A')
                wh_name = wh.get('name', 'N/A')
                wh_id = wh.get('id', 'N/A')
                messages.append(f'<b>{idx}. {wh_name}</b><br/>')
                messages.append(f'   Code: <code>{wh_code}</code><br/>')
                messages.append(f'   ID: {wh_id}<br/>')
                if wh.get('address'):
                    messages.append(f'   Address: {wh.get("address")}<br/>')
                messages.append(f'<br/>')
            
            message = ''.join(messages)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Zortout Warehouses',
                    'message': message,
                    'type': 'info',
                    'sticky': True,
                }
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'❌ Failed to get warehouses: {error_msg}', exc_info=True)
            raise UserError(f'Failed to get warehouses from Zortout: {error_msg}')
    
    def action_test_warehouse_code(self):
        """Test warehouse code by trying to fetch products from Zortout"""
        self.ensure_one()
        
        if self.channel != 'zortout':
            raise UserError('This action is only available for Zortout accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check credentials
        if not self.client_id or not self.client_secret or not self.access_token:
            raise UserError('Please configure Store Name, API Key, and API Secret first')
        
        # Get warehouse code from stock_location_id
        warehouse_code = None
        if self.stock_location_id and self.stock_location_id.warehouse_id:
            warehouse_code = self.stock_location_id.warehouse_id.code or self.stock_location_id.warehouse_id.name
        
        # Test without warehouse code first
        adapter = self._get_adapter(shop=None)
        _logger.warning(f'🧪 Testing warehouse code connection...')
        
        # Test 1: Without warehouse code
        result_no_wh = adapter.test_warehouse_code(warehouse_code=None)
        
        # Test 2: With warehouse code (if available)
        result_with_wh = None
        if warehouse_code:
            result_with_wh = adapter.test_warehouse_code(warehouse_code=warehouse_code)
        
        # Prepare message
        messages = []
        messages.append(f'<b>Test Results:</b><br/>')
        
        messages.append(f'<b>1. Without warehouse code:</b><br/>')
        if result_no_wh['valid']:
            messages.append(f'✅ Success: Found {result_no_wh["products_count"]} products<br/>')
        else:
            messages.append(f'❌ Failed: {result_no_wh["error"]}<br/>')
        
        if warehouse_code:
            messages.append(f'<br/><b>2. With warehouse code "{warehouse_code}":</b><br/>')
            if result_with_wh['valid']:
                messages.append(f'✅ Success: Found {result_with_wh["products_count"]} products<br/>')
            else:
                messages.append(f'❌ Failed: {result_with_wh["error"]}<br/>')
        else:
            messages.append(f'<br/><b>2. With warehouse code:</b><br/>')
            messages.append(f'⚠️ No warehouse code configured<br/>')
        
        message = ''.join(messages)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Warehouse Code Test',
                'message': message,
                'type': 'info' if result_no_wh['valid'] or (result_with_wh and result_with_wh['valid']) else 'warning',
                'sticky': True,
            }
        }
    
    def action_test_woocommerce_connection(self):
        """Test WooCommerce connection by calling API"""
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            raise UserError('This action is only available for WooCommerce accounts')
        
        # Check required fields
        if not self.client_id:
            raise UserError('Please configure Store URL (Client ID) first')
        
        if not self.woocommerce_consumer_key:
            raise UserError('Please configure Consumer Key first')
        
        if not self.client_secret:
            raise UserError('Please configure Consumer Secret first')
        
        try:
            adapter = self._get_adapter(shop=None)
            _logger.warning(f'🧪 Testing WooCommerce connection for account {self.id}: {self.name}')
            
            # Test 1: Try to get system status (simple endpoint)
            try:
                system_status = adapter._make_request('GET', 'system_status')
                _logger.warning(f'✅ System status retrieved successfully')
                system_info = f"WooCommerce Version: {system_status.get('environment', {}).get('version', 'Unknown')}<br/>"
            except Exception as e:
                _logger.error(f'❌ Failed to get system status: {e}')
                system_info = f"❌ Failed to get system status: {str(e)}<br/>"
            
            # Test 2: Try to get products count
            try:
                products = adapter._make_request('GET', 'products', params={'per_page': 1})
                products_count = len(products) if isinstance(products, list) else 0
                _logger.warning(f'✅ Products API accessible, found at least {products_count} product(s)')
                products_info = f"✅ Products API accessible<br/>"
            except Exception as e:
                _logger.error(f'❌ Failed to get products: {e}')
                products_info = f"❌ Failed to get products: {str(e)}<br/>"
            
            # Test 3: Try to get orders count
            try:
                orders = adapter._make_request('GET', 'orders', params={'per_page': 1})
                orders_count = len(orders) if isinstance(orders, list) else 0
                _logger.warning(f'✅ Orders API accessible, found at least {orders_count} order(s)')
                orders_info = f"✅ Orders API accessible<br/>"
            except Exception as e:
                _logger.error(f'❌ Failed to get orders: {e}')
                orders_info = f"❌ Failed to get orders: {str(e)}<br/>"
            
            # Determine overall status
            has_error = '❌' in system_info or '❌' in products_info or '❌' in orders_info
            status_type = 'success' if not has_error else 'warning'
            status_title = 'Connection Test: Success ✅' if not has_error else 'Connection Test: Partial Success ⚠️'
            
            # Auto-create shop if connection is successful and no shop exists
            shop_created = False
            if not has_error:
                shop_created = self._auto_create_woocommerce_shop()
            
            # Prepare message (use plain text for better compatibility)
            message_lines = []
            message_lines.append(status_title)
            message_lines.append('')
            message_lines.append('1. System Status:')
            message_lines.append(system_info.replace('<br/>', '').strip())
            message_lines.append('')
            message_lines.append('2. Products API:')
            message_lines.append(products_info.replace('<br/>', '').replace('✔', '✓').strip())
            message_lines.append('')
            message_lines.append('3. Orders API:')
            message_lines.append(orders_info.replace('<br/>', '').replace('✔', '✓').strip())
            message_lines.append('')
            message_lines.append(f'Store URL: {self.client_id}')
            consumer_key_display = self.woocommerce_consumer_key[:10] + '...' + (self.woocommerce_consumer_key[-10:] if len(self.woocommerce_consumer_key) > 20 else '')
            message_lines.append(f'Consumer Key: {consumer_key_display}')
            
            if shop_created:
                message_lines.append('')
                message_lines.append('✅ Shop created automatically!')
            
            message = '\n'.join(message_lines)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': status_title,
                    'message': message,
                    'type': status_type,
                    'sticky': True,
                }
            }
            
        except Exception as e:
            _logger.error(f'❌ WooCommerce connection test failed: {e}', exc_info=True)
            error_message = f'''Connection Test: Failed ❌

Error: {str(e)}

Please check:
• Store URL is correct (e.g., https://yourstore.com)
• Consumer Key is correct (starts with ck_)
• Consumer Secret is correct (starts with cs_)
• WooCommerce REST API is enabled in your store
• API key has Read/Write permissions'''
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Connection Test: Failed ❌',
                    'message': error_message,
                    'type': 'danger',
                    'sticky': True,
                }
            }
    
    def _auto_create_woocommerce_shop(self):
        """Auto-create WooCommerce shop if it doesn't exist"""
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            return False
        
        # Check if shop already exists
        existing_shop = self.env['marketplace.shop'].search([
            ('account_id', '=', self.id),
        ], limit=1)
        
        if existing_shop:
            _logger.info(f'Shop already exists for WooCommerce account {self.id}: {existing_shop.name}')
            return False
        
        # Get store name from URL
        store_name = 'WooCommerce Store'
        if self.client_id:
            # Extract domain from URL (e.g., https://onthisdayco.com -> onthisdayco.com)
            from urllib.parse import urlparse
            try:
                parsed_url = urlparse(self.client_id)
                domain = parsed_url.netloc or parsed_url.path
                if domain:
                    store_name = f'WooCommerce - {domain}'
            except:
                pass
        
        # Get default warehouse
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id),
        ], limit=1)
        
        # Create shop
        shop_vals = {
            'name': store_name,
            'external_shop_id': '1',  # WooCommerce typically has one store, use '1' as default
            'account_id': self.id,
            'active': True,
            'timezone': 'Asia/Bangkok',
        }
        
        if warehouse:
            shop_vals['warehouse_id'] = warehouse.id
        
        shop = self.env['marketplace.shop'].sudo().create(shop_vals)
        _logger.info(f'✅ Auto-created WooCommerce shop: {shop.name} (ID: {shop.id})')
        
        # Post message
        self.message_post(body=f'✅ Shop created automatically: {shop.name}')
        
        return True
    
    def action_push_stock_to_woocommerce(self):
        """Push stock to WooCommerce for all product bindings"""
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            raise UserError('This action is only available for WooCommerce accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check if shop exists
        if not self.shop_ids:
            raise UserError('Please create a shop first. Use "Test Connection" button to auto-create shop.')
        
        # Create push stock job for all shops
        shop_ids = self.shop_ids.ids
        jobs_created = []
        
        for shop_id in shop_ids:
            shop = self.env['marketplace.shop'].browse(shop_id)
            
            # Check if there are any product bindings
            bindings = self.env['marketplace.product.binding'].search([
                ('shop_id', '=', shop_id),
                ('active', '=', True),
                ('exclude_push', '=', False),
            ])
            
            if not bindings:
                continue
            
            binding_ids = bindings.ids
            batch_size = self.push_stock_batch_size or 0  # 0 = no batching
            current_time = fields.Datetime.now()
            
            # If batch_size is 0 or bindings <= batch_size, create single job
            if batch_size == 0 or len(binding_ids) <= batch_size:
                job = self.env['marketplace.job'].create({
                    'name': f'Push Stock to WooCommerce - {shop.name}',
                    'job_type': 'push_stock',
                    'account_id': self.id,
                    'shop_id': shop_id,
                    'priority': 'medium',
                    'payload': {
                        'binding_ids': binding_ids,
                    },
                    'state': 'pending',
                    'next_run_at': current_time,
                })
                jobs_created.append(job)
            else:
                # Split into batches
                total_bindings = len(binding_ids)
                batch_count = (total_bindings + batch_size - 1) // batch_size  # Ceiling division
                
                for batch_idx in range(batch_count):
                    start_idx = batch_idx * batch_size
                    end_idx = min(start_idx + batch_size, total_bindings)
                    batch_binding_ids = binding_ids[start_idx:end_idx]
                    
                    # Stagger jobs: each batch starts 5 seconds after previous
                    batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                    
                    job = self.env['marketplace.job'].create({
                        'name': f'Push Stock to WooCommerce - {shop.name} (Batch {batch_idx + 1}/{batch_count})',
                        'job_type': 'push_stock',
                        'account_id': self.id,
                        'shop_id': shop_id,
                        'priority': 'medium',
                        'payload': {
                            'binding_ids': batch_binding_ids,
                            'batch_index': batch_idx,
                            'batch_total': batch_count,
                            'batch_size': batch_size,
                        },
                        'state': 'pending',
                        'next_run_at': batch_next_run,
                    })
                    jobs_created.append(job)
        
        if not jobs_created:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Products to Push',
                    'message': 'No active product bindings found. Please create product bindings first.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        message = f'Created {len(jobs_created)} stock push job(s). They will be processed shortly.'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Stock Push Queued',
                'message': message,
                'type': 'success',
            'sticky': False,
        }
    }
    
    def action_populate_product_ids(self):
        """Populate external_product_id for bindings that don't have it yet
        
        This helps improve push stock performance by caching WooCommerce product IDs.
        """
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            raise UserError('This action is only available for WooCommerce accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Get bindings without external_product_id
        bindings = self.env['marketplace.product.binding'].search([
            ('shop_id', 'in', self.shop_ids.ids),
            ('active', '=', True),
            ('external_product_id', '=', False),
        ])
        
        if not bindings:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Bindings to Update',
                    'message': 'All bindings already have product IDs cached.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        _logger.warning(f'🔄 Starting to populate product IDs for {len(bindings)} bindings')
        
        # Process bindings in batches
        batch_size = 50  # Process 50 at a time to avoid timeout
        total_bindings = len(bindings)
        updated_count = 0
        error_count = 0
        errors = []
        
        adapter = None
        for shop in self.shop_ids:
            if not adapter:
                adapter = self._get_adapter(shop)
            
            # Get bindings for this shop
            shop_bindings = bindings.filtered(lambda b: b.shop_id.id == shop.id)
            
            if not shop_bindings:
                continue
            
            _logger.warning(f'📦 Processing {len(shop_bindings)} bindings for shop {shop.name}')
            
            # Process in batches
            for i in range(0, len(shop_bindings), batch_size):
                batch = shop_bindings[i:i+batch_size]
                _logger.warning(f'  Processing batch {i//batch_size + 1}/{(len(shop_bindings) + batch_size - 1)//batch_size} ({len(batch)} bindings)')
                
                import time
                
                for binding in batch:
                    try:
                        # Small delay to avoid rate limiting (100ms between requests)
                        time.sleep(0.1)
                        
                        # Find product by SKU
                        products = adapter._make_request('GET', 'products', params={
                            'sku': binding.external_sku,
                            'per_page': 1,
                        })
                        
                        if not products:
                            error_count += 1
                            error_msg = f'Product with SKU {binding.external_sku} not found in WooCommerce'
                            errors.append(error_msg)
                            _logger.warning(f'  ⚠️  {error_msg}')
                            continue
                        
                        product = products[0]
                        product_id = product['id']
                        product_type = product.get('type', 'simple')
                        parent_id = product.get('parent_id')
                        
                        # Store product_id in format "parent_id:variation_id" for variations
                        if product_type == 'variation' and parent_id:
                            external_product_id = f"{parent_id}:{product_id}"
                        else:
                            external_product_id = str(product_id)
                        
                        # Update binding
                        binding.write({
                            'external_product_id': external_product_id,
                        })
                        
                        updated_count += 1
                        
                        if updated_count % 10 == 0:
                            _logger.warning(f'  ✅ Updated {updated_count}/{total_bindings} bindings')
                            # Commit periodically to avoid long transaction
                            self.env.cr.commit()
                        elif updated_count % 5 == 0:
                            # Log progress every 5 bindings
                            _logger.info(f'  Progress: {updated_count}/{total_bindings} bindings updated')
                    
                    except Exception as e:
                        error_count += 1
                        error_msg = f'Error updating binding {binding.external_sku}: {str(e)}'
                        errors.append(error_msg)
                        _logger.error(error_msg, exc_info=True)
                        
                        # If rate limited, wait a bit longer
                        if '429' in str(e) or 'rate limit' in str(e).lower():
                            _logger.warning(f'  ⏸️  Rate limited, waiting 5 seconds...')
                            time.sleep(5)
        
        # Final commit
        self.env.cr.commit()
        
        _logger.warning(f'✅ Completed: {updated_count} updated, {error_count} errors')
        
        # Prepare result message
        message_parts = []
        message_parts.append(f'<b>Product ID Population Completed:</b><br/>')
        message_parts.append(f'✅ Updated: {updated_count} bindings<br/>')
        message_parts.append(f'📦 Total bindings processed: {total_bindings}<br/>')
        if error_count > 0:
            message_parts.append(f'⚠️ Errors: {error_count} bindings<br/>')
            if errors:
                message_parts.append(f'<br/><b>Errors (first 10):</b><br/>')
                for error in errors[:10]:
                    message_parts.append(f'• {error}<br/>')
        
        message = ''.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Product ID Population Completed',
                'message': message,
                'type': 'success' if error_count == 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_create_bindings_from_orders(self):
        """Create product bindings from missing SKUs in marketplace orders"""
        self.ensure_one()
        
        if not self.shop_ids:
            raise UserError('No shops found for this account')
        
        _logger.warning(f'🔧 Creating product bindings from orders for account {self.name}')
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        # Get all shops for this account
        for shop in self.shop_ids.filtered('active'):
            # Get all marketplace orders for this shop
            orders = self.env['marketplace.order'].search([
                ('shop_id', '=', shop.id),
            ])
            
            # Collect unique SKUs from order lines
            skus_to_bind = set()
            for order in orders:
                for line in order.order_line_ids:
                    if line.external_sku:
                        # Check if binding already exists
                        existing = self.env['marketplace.product.binding'].search([
                            ('external_sku', '=', line.external_sku),
                            ('shop_id', '=', shop.id),
                            ('active', '=', True),
                        ], limit=1)
                        
                        if not existing:
                            skus_to_bind.add(line.external_sku)
            
            _logger.warning(f'📦 Found {len(skus_to_bind)} unique SKUs without bindings for shop {shop.name}')
            
            # Create bindings for each SKU
            for sku in skus_to_bind:
                try:
                    # Find product by SKU (default_code)
                    # First try with company filter
                    product = self.env['product.product'].search([
                        ('default_code', '=', sku),
                        ('company_id', '=', self.company_id.id),
                    ], limit=1)
                    
                    if not product:
                        # Try without company filter (for shared products)
                        product = self.env['product.product'].search([
                            ('default_code', '=', sku),
                            ('company_id', '=', False),
                        ], limit=1)
                    
                    if not product:
                        # Try searching without company filter at all
                        product = self.env['product.product'].search([
                            ('default_code', '=', sku),
                        ], limit=1)
                    
                    if product:
                        # Check if binding already exists (race condition check)
                        existing = self.env['marketplace.product.binding'].search([
                            ('external_sku', '=', sku),
                            ('shop_id', '=', shop.id),
                        ], limit=1)
                        
                        if existing:
                            skipped_count += 1
                            continue
                        
                        # Create binding
                        binding = self.env['marketplace.product.binding'].create({
                            'product_id': product.id,
                            'shop_id': shop.id,
                            'external_sku': sku,
                            'active': True,
                        })
                        created_count += 1
                        _logger.warning(f'✅ Created binding: {sku} -> {product.name}')
                    else:
                        skipped_count += 1
                        error_msg = f'SKU {sku}: Product not found in Odoo'
                        errors.append(error_msg)
                        _logger.warning(f'⚠️  {error_msg}')
                
                except Exception as e:
                    skipped_count += 1
                    error_msg = f'SKU {sku}: {str(e)}'
                    errors.append(error_msg)
                    _logger.error(error_msg, exc_info=True)
        
        # Prepare result message
        message_parts = []
        message_parts.append(f'Product Bindings Created:\n')
        message_parts.append(f'✅ Created: {created_count} bindings\n')
        message_parts.append(f'📦 Skipped: {skipped_count} SKUs\n')
        
        if errors:
            message_parts.append(f'\nErrors ({min(len(errors), 10)} of {len(errors)}):\n')
            for error in errors[:10]:
                message_parts.append(f'• {error}\n')
        
        message = ''.join(message_parts)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bindings Created',
                'message': message,
                'type': 'success' if created_count > 0 else 'warning',
                'sticky': True,
            }
        }
    
    def action_sync_products_from_woocommerce(self):
        """Sync products from WooCommerce and create product bindings automatically by SKU"""
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            raise UserError('This action is only available for WooCommerce accounts')
        
        if not self.sync_enabled:
            raise UserError('Please enable sync for this account first')
        
        # Check if shop exists
        if not self.shop_ids:
            raise UserError('Please create a shop first. Use "Test Connection" button to auto-create shop.')
        
        # Check credentials
        if not self.client_id or not self.woocommerce_consumer_key or not self.client_secret:
            raise UserError('Please configure Store URL, Consumer Key, and Consumer Secret first')
        
        # Check if there's already a pending or in_progress job for this account
        existing_job = self.env['marketplace.job'].search([
            ('account_id', '=', self.id),
            ('job_type', '=', 'sync_products_from_woocommerce'),
            ('state', 'in', ['pending', 'in_progress']),
        ], limit=1)
        
        if existing_job:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Job Already Queued',
                    'message': f'Product sync job is already queued (Job ID: {existing_job.id}). Please wait for it to complete.',
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Create background job instead of running synchronously
        # This prevents timeout and connection issues
        job = self.env['marketplace.job'].create({
            'name': f'Sync Products from WooCommerce - {self.name}',
            'job_type': 'sync_products_from_woocommerce',
            'account_id': self.id,
            'shop_id': self.shop_ids[0].id if self.shop_ids else False,
            'priority': 'medium',
            'payload': {},
            'next_run_at': fields.Datetime.now(),
        })
        
        _logger.warning(f'✅ Created background job {job.id} for product sync: {self.name}')
        
        # Post message
        self.message_post(body=f'Product sync job created (Job ID: {job.id}). Job will start processing shortly. You can track progress in the Jobs page.')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Product sync job has been created (Job ID: {job.id}).\n\nThe job will start processing in the background shortly. You can track progress in the Jobs page.',
                'type': 'success',
                'sticky': True,
            }
        }
    
    def action_sync_products_from_woocommerce_sync(self, job=None):
        """Internal method: Sync products from WooCommerce (called by background job)
        Args:
            job: Optional marketplace.job record for progress tracking
        """
        self.ensure_one()
        
        if self.channel != 'woocommerce':
            raise ValueError('This method is only available for WooCommerce accounts')
        
        if not self.sync_enabled:
            raise ValueError('Sync is disabled for this account')
        
        if not self.shop_ids:
            raise ValueError('Please create a shop first')
        
        # Check credentials
        if not self.client_id or not self.woocommerce_consumer_key or not self.client_secret:
            raise ValueError('Please configure Store URL, Consumer Key, and Consumer Secret first')
        
        adapter = self._get_adapter(shop=None)
        _logger.warning(f'🔄 Syncing products from WooCommerce for account {self.id}: {self.name}')
        
        # Fetch all products from WooCommerce
        all_products = []
        page = 1
        per_page = 100
        
        # Initialize progress tracking
        if job:
            job.write({
                'total_items': 0,  # Will be updated after fetching
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()
        else:
            # Fallback: search for in_progress job
            job = self.env['marketplace.job'].search([
                ('account_id', '=', self.id),
                ('job_type', '=', 'sync_products_from_woocommerce'),
                ('state', '=', 'in_progress'),
            ], limit=1, order='create_date desc')
            if job:
                job.write({
                    'total_items': 0,  # Will be updated after fetching
                    'processed_items': 0,
                    'progress': 0.0,
                })
                self.env.cr.commit()
        
        while True:
            try:
                products = adapter._make_request('GET', 'products', params={
                    'per_page': per_page,
                    'page': page,
                })
                
                if not products:
                    break
                
                all_products.extend(products)
                _logger.warning(f'📦 Fetched page {page}: {len(products)} products')
                
                # Check if we got less than per_page (last page)
                if len(products) < per_page:
                    break
                
                page += 1
                
            except Exception as e:
                _logger.error(f'Error fetching products page {page}: {e}')
                break
        
        _logger.warning(f'✅ Total products fetched from WooCommerce: {len(all_products)}')
        
        # Map products by SKU and create bindings
        created_count = 0
        updated_count = 0
        skipped_count = 0
        not_found_count = 0
        variations_created = 0
        variations_updated = 0
        variations_not_found = 0
        errors = []
        
        # Store skipped/not found products for export
        skipped_products = []  # List of dicts with product details
        not_found_products = []  # List of dicts with product details
        variations_not_found_list = []  # List of dicts with variation details
        
        # Get shop (use first shop)
        shop = self.shop_ids[0]
        
        # Step 1: Collect all SKUs (from simple products and variations)
        all_skus = []
        simple_products_data = []  # (wc_product, wc_sku, wc_product_id)
        variable_products_data = []  # (wc_product_id, variations)
        
        for wc_product in all_products:
            wc_product_id = str(wc_product.get('id', ''))
            wc_product_type = wc_product.get('type', 'simple')
            
            if wc_product_type == 'variable':
                # Will handle variations separately
                variable_products_data.append((wc_product_id, wc_product))
            else:
                wc_sku = wc_product.get('sku', '').strip()
                if wc_sku:
                    all_skus.append(wc_sku)
                    simple_products_data.append((wc_product, wc_sku, wc_product_id))
        
        # Step 2: Fetch variations for all variable products (optimized: concurrent requests)
        all_variations_data = []  # (wc_product_id, variation)
        total_variable_products = len(variable_products_data)
        
        if total_variable_products > 0:
            _logger.warning(f'📦 Fetching variations for {total_variable_products} variable products (concurrent)...')
            
            # Use concurrent requests to speed up variation fetching
            import concurrent.futures
            import threading
            import requests
            from requests.auth import HTTPBasicAuth
            
            # Create a thread-safe function to fetch variations
            # Each thread needs its own adapter instance or we need to make requests directly
            def fetch_variations(wc_product_id):
                """Fetch variations for a single product (thread-safe)"""
                try:
                    # Make request directly (thread-safe) instead of using adapter
                    # adapter.base_url already includes wp-json/wc/v3/
                    url = f"{adapter.base_url}products/{wc_product_id}/variations"
                    
                    # Get credentials (same logic as adapter._get_auth)
                    account = adapter.account
                    consumer_key = account.woocommerce_consumer_key
                    if not consumer_key:
                        # Fallback to system parameter
                        consumer_key = account.env['ir.config_parameter'].sudo().get_param(
                            'marketplace.woocommerce.consumer_key'
                        )
                    if not consumer_key:
                        # Last fallback: use client_secret
                        consumer_key = account.client_secret
                    
                    consumer_secret = account.client_secret  # Consumer Secret is stored in client_secret field
                    
                    if not consumer_secret:
                        return (wc_product_id, [], 'Consumer Secret is required')
                    
                    auth = HTTPBasicAuth(consumer_key, consumer_secret)
                    params = {'per_page': 100}
                    
                    response = requests.get(url, auth=auth, params=params, timeout=30)
                    response.raise_for_status()
                    variations = response.json()
                    
                    return (wc_product_id, variations, None)
                except Exception as e:
                    return (wc_product_id, [], str(e))
            
            # Fetch variations concurrently (max 10 concurrent requests to avoid rate limiting)
            max_workers = min(10, total_variable_products)
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_product = {
                    executor.submit(fetch_variations, wc_product_id): wc_product_id
                    for wc_product_id, _ in variable_products_data
                }
                
                # Process completed tasks
                completed = 0
                for future in concurrent.futures.as_completed(future_to_product):
                    completed += 1
                    wc_product_id, variations, error = future.result()
                    
                    if error:
                        error_msg = f"Error fetching variations for product {wc_product_id}: {error}"
                        errors.append(error_msg)
                        _logger.error(error_msg)
                    else:
                        for variation in variations:
                            var_sku = variation.get('sku', '').strip()
                            if var_sku:
                                all_skus.append(var_sku)
                                all_variations_data.append((wc_product_id, variation))
                    
                    # Log progress every 10 products
                    if completed % 10 == 0 or completed == total_variable_products:
                        _logger.info(f'📦 Fetched variations: {completed}/{total_variable_products} products ({len(all_variations_data)} variations so far)')
            
            _logger.warning(f'✅ Completed fetching variations: {len(all_variations_data)} variations from {completed} products')
        
        _logger.warning(f'📦 Processing {len(simple_products_data)} simple products and {len(all_variations_data)} variations')
        
        # Step 3: Bulk search all Odoo products by SKU (1 query instead of N queries)
        odoo_products_by_sku = {}
        if all_skus:
            # Search with company filter first
            products_with_company = self.env['product.product'].search([
                ('default_code', 'in', all_skus),
                ('company_id', '=', self.company_id.id),
            ])
            for product in products_with_company:
                if product.default_code:
                    odoo_products_by_sku[product.default_code] = product
            
            # Search shared products (company_id = False) for SKUs not found
            found_skus = set(odoo_products_by_sku.keys())
            missing_skus = [sku for sku in all_skus if sku not in found_skus]
            if missing_skus:
                products_shared = self.env['product.product'].search([
                    ('default_code', 'in', missing_skus),
                    ('company_id', '=', False),
                ])
                for product in products_shared:
                    if product.default_code:
                        odoo_products_by_sku[product.default_code] = product
        
        # Step 4: Bulk search all existing bindings (1 query instead of N queries)
        existing_bindings_map = {}  # (product_id, shop_id) -> binding
        if odoo_products_by_sku:
            product_ids = [p.id for p in odoo_products_by_sku.values()]
            existing_bindings = self.env['marketplace.product.binding'].search([
                ('product_id', 'in', product_ids),
                ('shop_id', '=', shop.id),
            ])
            for binding in existing_bindings:
                key = (binding.product_id.id, binding.shop_id.id)
                existing_bindings_map[key] = binding
        
        # Step 5: Prepare bulk create/update operations
        bindings_to_create = []
        bindings_to_update = []
        batch_size = 200  # Increased batch size for better performance (was 100)
        
        # Process simple products
        for wc_product, wc_sku, wc_product_id in simple_products_data:
            try:
                odoo_product = odoo_products_by_sku.get(wc_sku)
                if not odoo_product:
                    not_found_count += 1
                    _logger.warning(f'⚠️ Product with SKU {wc_sku} not found in Odoo')
                    # Store for export
                    not_found_products.append({
                        'product_id': wc_product_id,
                        'name': wc_product.get('name', ''),
                        'sku': wc_sku,
                        'type': wc_product.get('type', 'simple'),
                        'reason': 'SKU not found in Odoo',
                    })
                    continue
                
                key = (odoo_product.id, shop.id)
                existing_binding = existing_bindings_map.get(key)
                
                if existing_binding:
                    bindings_to_update.append((existing_binding, {
                        'external_sku': wc_sku,
                        'external_product_id': wc_product_id,
                        'active': True,
                    }))
                else:
                    bindings_to_create.append({
                        'product_id': odoo_product.id,
                        'shop_id': shop.id,
                        'external_sku': wc_sku,
                        'external_product_id': wc_product_id,
                        'active': True,
                    })
            except Exception as e:
                error_msg = f"Error processing product {wc_product.get('name', 'Unknown')} (SKU: {wc_sku}): {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg, exc_info=True)
        
        # Process variations
        for wc_product_id, variation in all_variations_data:
            try:
                var_sku = variation.get('sku', '').strip()
                var_id = str(variation.get('id', ''))
                
                if not var_sku:
                    continue
                
                odoo_product = odoo_products_by_sku.get(var_sku)
                if not odoo_product:
                    variations_not_found += 1
                    _logger.warning(f'⚠️ Variation with SKU {var_sku} not found in Odoo')
                    # Store for export
                    variations_not_found_list.append({
                        'parent_product_id': wc_product_id,
                        'variation_id': var_id,
                        'name': variation.get('name', ''),
                        'sku': var_sku,
                        'reason': 'SKU not found in Odoo',
                    })
                    continue
                
                external_product_id = f"{wc_product_id}:{var_id}"
                key = (odoo_product.id, shop.id)
                existing_binding = existing_bindings_map.get(key)
                
                if existing_binding:
                    bindings_to_update.append((existing_binding, {
                        'external_sku': var_sku,
                        'external_product_id': external_product_id,
                        'active': True,
                    }))
                else:
                    bindings_to_create.append({
                        'product_id': odoo_product.id,
                        'shop_id': shop.id,
                        'external_sku': var_sku,
                        'external_product_id': external_product_id,
                        'active': True,
                    })
            except Exception as e:
                error_msg = f"Error processing variation {variation.get('id', 'Unknown')} (SKU: {variation.get('sku', 'N/A')}): {str(e)}"
                errors.append(error_msg)
                _logger.error(error_msg, exc_info=True)
        
        # Step 6: Bulk update existing bindings (optimized: use recordset.write() for better performance)
        if bindings_to_update:
            # Group bindings by update values to minimize write operations
            update_groups = {}  # tuple(vals) -> list of bindings
            
            for binding, vals in bindings_to_update:
                # Create a key from sorted vals items for grouping
                vals_key = tuple(sorted(vals.items()))
                if vals_key not in update_groups:
                    update_groups[vals_key] = []
                update_groups[vals_key].append(binding)
            
            # Update bindings in groups using recordset.write() (faster than individual writes)
            total_updated = 0
            for vals_key, bindings in update_groups.items():
                try:
                    # Convert tuple back to dict
                    vals = dict(vals_key)
                    # Create recordset from list of bindings and write once
                    binding_recordset = self.env['marketplace.product.binding'].browse([b.id for b in bindings])
                    binding_recordset.write(vals)
                    
                    # Count updates (check if variation by external_product_id format)
                    # Check external_product_id from vals instead of refreshing (faster)
                    is_variation = vals.get('external_product_id', '').find(':') != -1 if vals.get('external_product_id') else False
                    for binding in bindings:
                        if is_variation:
                            variations_updated += 1
                        else:
                            updated_count += 1
                        total_updated += 1
                except Exception as e:
                    _logger.error(f'Failed to update {len(bindings)} bindings: {e}', exc_info=True)
            
            # Commit after all updates (single commit instead of per-binding)
            self.env.cr.commit()
            _logger.warning(f'✅ Updated {total_updated} bindings in {len(update_groups)} groups')
        
        # Step 7: Bulk create new bindings (in batches)
        if bindings_to_create:
            for batch_start in range(0, len(bindings_to_create), batch_size):
                batch = bindings_to_create[batch_start:batch_start + batch_size]
                try:
                    new_bindings = self.env['marketplace.product.binding'].create(batch)
                    for binding in new_bindings:
                        if binding.external_product_id and ':' in binding.external_product_id:
                            variations_created += 1
                        else:
                            created_count += 1
                    
                    # Commit after each batch
                    self.env.cr.commit()
                    _logger.warning(f'✅ Created batch {batch_start // batch_size + 1}: {len(batch)} bindings')
                except Exception as e:
                    _logger.error(f'Failed to create batch of bindings: {e}', exc_info=True)
                    error_count = len(batch)
                    errors.append(f'Failed to create {error_count} bindings in batch')
        
        # Count skipped (variable parent products and products without SKU)
        # Track which variable products have variations that were successfully synced
        # Check after bindings are created/updated to see which variations actually have bindings
        variable_products_with_synced_variations = set()
        
        # After processing variations, check which variable products have successfully synced variations
        # A variation is considered synced if:
        # 1. It has a matching Odoo product (found in odoo_products_by_sku)
        # 2. It was added to bindings_to_create or bindings_to_update (or already exists)
        for wc_product_id, variation in all_variations_data:
            var_sku = variation.get('sku', '').strip()
            if var_sku:
                # Check if this variation has matching Odoo product
                odoo_product = odoo_products_by_sku.get(var_sku)
                if odoo_product:
                    # Check if binding exists, will be created, or will be updated
                    key = (odoo_product.id, shop.id)
                    
                    # Check 1: Existing binding (will be updated)
                    if key in existing_bindings_map:
                        variable_products_with_synced_variations.add(wc_product_id)
                        continue
                    
                    # Check 2: Will be created
                    for binding_data in bindings_to_create:
                        if binding_data.get('product_id') == odoo_product.id and binding_data.get('shop_id') == shop.id:
                            variable_products_with_synced_variations.add(wc_product_id)
                            break
                    
                    # Check 3: Will be updated (check bindings_to_update)
                    if wc_product_id not in variable_products_with_synced_variations:
                        for binding, vals in bindings_to_update:
                            if binding.product_id.id == odoo_product.id and binding.shop_id.id == shop.id:
                                variable_products_with_synced_variations.add(wc_product_id)
                                break
        
        skipped_count = 0
        
        # Store skipped products (variable parents and products without SKU)
        for wc_product in all_products:
            wc_product_id = str(wc_product.get('id', ''))
            wc_product_type = wc_product.get('type', 'simple')
            wc_sku = wc_product.get('sku', '').strip()
            
            # Variable parent products (no SKU at parent level)
            if wc_product_type == 'variable':
                # Only mark as skipped if no variations were successfully synced
                if wc_product_id not in variable_products_with_synced_variations:
                    skipped_count += 1
                    skipped_products.append({
                        'product_id': wc_product_id,
                        'name': wc_product.get('name', ''),
                        'sku': '',
                        'type': 'variable',
                        'reason': 'Variable parent product (no SKU at parent level, and no variations synced)',
                    })
                # If variations were synced, don't mark parent as skipped
                # (this is expected behavior - parent doesn't need SKU, variations do)
            # Simple products without SKU
            elif not wc_sku:
                skipped_count += 1
                skipped_products.append({
                    'product_id': wc_product_id,
                    'name': wc_product.get('name', ''),
                    'sku': '',
                    'type': 'simple',
                    'reason': 'No SKU',
                })
        
        # Prepare summary message (use plain text for better compatibility)
        summary_lines = []
        summary_lines.append('Product Sync Summary:')
        summary_lines.append('')
        summary_lines.append(f'✅ Created: {created_count} bindings (simple products)')
        summary_lines.append(f'🔄 Updated: {updated_count} bindings (simple products)')
        summary_lines.append(f'📦 Variations Created: {variations_created} bindings')
        summary_lines.append(f'🔄 Variations Updated: {variations_updated} bindings')
        # Calculate total variable parents
        total_variable_parents = len(variable_products_data)
        synced_variable_parents = len(variable_products_with_synced_variations)
        
        if total_variable_parents > 0:
            summary_lines.append(f'📦 Variable Products: {total_variable_parents} parents ({synced_variable_parents} with synced variations)')
            if skipped_count > 0:
                summary_lines.append(f'⏭️ Skipped: {skipped_count} products (no SKU or variable parent with no synced variations)')
        else:
            summary_lines.append(f'⏭️ Skipped: {skipped_count} products (no SKU)')
        summary_lines.append(f'⚠️ Not Found: {not_found_count} products (SKU not found in Odoo)')
        summary_lines.append(f'⚠️ Variations Not Found: {variations_not_found} variations (SKU not found in Odoo)')
        summary_lines.append(f'❌ Errors: {len(errors)}')
        summary_lines.append('')
        summary_lines.append(f'Total Products in WooCommerce: {len(all_products)}')
        summary_lines.append(f'Total Bindings: {created_count + updated_count + variations_created + variations_updated}')
        
        if errors:
            summary_lines.append('')
            summary_lines.append('Errors:')
            for error in errors[:10]:  # Show first 10 errors
                summary_lines.append(f'• {error}')
            if len(errors) > 10:
                summary_lines.append(f'... and {len(errors) - 10} more errors')
        
        summary = '\n'.join(summary_lines)
        
        # Store export data for CSV download
        export_data = {
            'skipped_products': skipped_products,
            'not_found_products': not_found_products,
            'variations_not_found': variations_not_found_list,
            'sync_date': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'account_name': self.name,
        }
        self.write({'sync_export_data': json.dumps(export_data, ensure_ascii=False)})
        
        # Post message with download link if there are skipped/not found products
        message_body = f'Product sync completed: {created_count + variations_created} created, {updated_count + variations_updated} updated, {not_found_count + variations_not_found} not found (including {variations_created + variations_updated} variations)'
        
        if skipped_count > 0 or not_found_count > 0 or variations_not_found > 0:
            # Add download button/link to message
            # Use direct method call via button in form view
            message_body += f'<br/><br/>📥 <strong>Download Report:</strong> ใช้ปุ่ม "Download Skipped Products Report" ในหน้า Account หรือคลิกที่ <a href="#" onclick="window.location.href=\'/web#id={self.id}&model=marketplace.account&action=otd_marketplace_stock.action_download_skipped_products\'">ลิงก์นี้</a>'
        
        self.message_post(body=message_body)
        
        # Update job progress to 100%
        # Use the job parameter if provided, otherwise search for it
        if not job:
            job = self.env['marketplace.job'].search([
                ('account_id', '=', self.id),
                ('job_type', '=', 'sync_products_from_woocommerce'),
                ('state', '=', 'in_progress'),
            ], limit=1, order='create_date desc')
        
        if job:
            total_processed = created_count + updated_count + variations_created + variations_updated
            job._update_progress(total_processed, max(total_processed, 1))
        
        _logger.warning(f'✅ Product sync completed: {summary}')
        
        # Return result for job
        return {
            'summary': summary,
            'created': created_count + variations_created,
            'updated': updated_count + variations_updated,
            'skipped': skipped_count,
            'not_found': not_found_count + variations_not_found,
            'errors': errors,
        }

    # -------------------------------------------------------------------------
    # Lazada integration helpers
    # -------------------------------------------------------------------------

    def _lazada_import_products(self, shop, payload=None, job=None):
        """Import products and create/update bindings for Lazada shop"""
        self.ensure_one()
        if self.channel != 'lazada':
            raise ValueError('Lazada import only available for Lazada accounts')
        if not self.sync_enabled:
            raise ValueError('Sync is disabled for this account')
        if not shop:
            raise ValueError('Shop is required for Lazada import')

        payload = payload or {}
        adapter = self._get_adapter(shop)
        products = adapter.fetch_all_products()

        sku_entries = []
        for product in products:
            sku_entries.extend(adapter.extract_sku_info(product))

        total_items = len(sku_entries)
        if job:
            job.write({
                'total_items': total_items,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()

        binding_model = self.env['marketplace.product.binding'].sudo()
        product_template_model = self.env['product.template'].sudo()
        created = 0
        updated = 0
        skipped = 0
        errors = []
        created_products = 0
        processed = 0
        default_category = self.env.ref('product.product_category_all', raise_if_not_found=False)
        default_uom = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        purchase_uom_field = 'uom_po_id' if product_template_model._fields.get('uom_po_id') else False

        for sku_info in sku_entries:
            processed += 1
            sku = sku_info.get('seller_sku')
            if not sku:
                skipped += 1
                if job:
                    job._update_progress(processed, total_items or 1)
                continue

            product_record = self.env['product.product'].sudo().search([
                ('default_code', '=', sku),
                ('company_id', 'in', [self.company_id.id, False]),
            ], limit=1, order='company_id desc')

            if not product_record:
                product_name = sku_info.get('name') or sku_info.get('product_name') or sku
                template_vals = {
                    'name': product_name,
                    'type': 'consu',
                    'sale_ok': True,
                    'purchase_ok': True,
                    'company_id': self.company_id.id or False,
                    'categ_id': default_category.id if default_category else False,
                    'uom_id': default_uom.id if default_uom else False,
                }
                if purchase_uom_field and default_uom:
                    template_vals[purchase_uom_field] = default_uom.id

                try:
                    template = product_template_model.create(template_vals)
                    product_record = template.product_variant_id
                    product_record.sudo().write({'default_code': sku})
                    created_products += 1
                except Exception as e:
                    skipped += 1
                    errors.append({
                        'sku': sku,
                        'name': product_name,
                        'error': str(e),
                    })
                    if job:
                        job._update_progress(processed, total_items or 1)
                    continue

            if not product_record:
                skipped += 1
                if job:
                    job._update_progress(processed, total_items or 1)
                continue

            binding = binding_model.search([
                ('shop_id', '=', shop.id),
                ('external_sku', '=', sku),
            ], limit=1)

            binding_vals = {
                'product_id': product_record.id,
                'shop_id': shop.id,
                'external_sku': sku,
                'external_product_id': sku_info.get('item_id') or sku_info.get('sku_id'),
                'active': sku_info.get('is_active', True),
            }
            if sku_info.get('quantity') is not None:
                binding_vals['current_online_qty'] = sku_info.get('quantity')

            if binding:
                binding.sudo().write(binding_vals)
                updated += 1
            else:
                binding_model.sudo().create(binding_vals)
                created += 1

            if job:
                job._update_progress(processed, total_items or 1)
            if processed % 50 == 0:
                self.env.cr.commit()

        result = {
            'message': f'Imported Lazada products for {shop.name}',
            'created_bindings': created,
            'updated_bindings': updated,
            'skipped': skipped,
            'not_found': len(errors),
            'products_created': created_products,
        }

        if errors:
            result['error_details'] = errors[:20]

        return result

    def _lazada_update_images(self, shop, payload=None, job=None):
        """Update Odoo images using Lazada images"""
        self.ensure_one()
        if self.channel != 'lazada':
            raise ValueError('Lazada image update only available for Lazada accounts')
        if not shop:
            raise ValueError('Shop is required for Lazada image update')

        payload = payload or {}
        update_existing = bool(payload.get('update_existing_images'))

        adapter = self._get_adapter(shop)
        products = adapter.fetch_all_products()
        sku_image_map = adapter.get_sku_image_map(products)

        bindings = self.env['marketplace.product.binding'].sudo().search([
            ('shop_id', '=', shop.id),
            ('active', '=', True),
        ])

        total = len(bindings)
        if job:
            job.write({
                'total_items': total,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()

        updated = 0
        skipped_existing = 0
        skipped_no_image = 0
        errors = 0
        processed = 0

        for binding in bindings:
            processed += 1
            sku = binding.external_sku
            image_urls = sku_image_map.get(sku) or []

            product_template = binding.product_id.product_tmpl_id.sudo()
            if product_template:
                if not image_urls:
                    skipped_no_image += 1
                elif not update_existing and product_template.image_1920:
                    skipped_existing += 1
                else:
                    image_data = adapter.download_image(image_urls[0])
                    if image_data:
                        product_template.write({'image_1920': image_data})
                        updated += 1
                    else:
                        errors += 1
            else:
                errors += 1

            if job:
                job._update_progress(processed, total or 1)
            if processed % 20 == 0:
                self.env.cr.commit()

        return {
            'message': f'Updated Lazada images for {shop.name}',
            'updated': updated,
            'skipped_existing': skipped_existing,
            'skipped_no_image': skipped_no_image,
            'errors': errors,
        }

    def _lazada_backfill_orders(self, shop, payload=None, job=None):
        """Backfill orders for a specific date from Lazada"""
        self.ensure_one()
        if self.channel != 'lazada':
            raise ValueError('Lazada order backfill only available for Lazada accounts')
        if not shop:
            raise ValueError('Shop is required for Lazada backfill')

        payload = payload or {}
        sync_date = payload.get('sync_date')
        if not sync_date:
            raise ValueError('sync_date is required for Lazada backfill')

        date_obj = fields.Date.from_string(sync_date)
        date_from = datetime.combine(date_obj, datetime.min.time())
        date_to = date_from + timedelta(days=1)

        adapter = self._get_adapter(shop)
        if self.channel == 'shopee':
            detailed_payloads = adapter.fetch_orders_list_with_details(
                since=date_from,
                until=date_to,
                time_range_field='create_time',
                page_size=100,
            )
            orders_payload = [adapter.parse_order_payload(p) for p in (detailed_payloads or [])]
        else:
            orders_payload = adapter.fetch_orders(date_from, date_to)

        total_orders = len(orders_payload)
        if job:
            job.write({
                'total_items': total_orders,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()

        result = self.env['marketplace.order'].sudo().create_from_payloads_bulk(
            shop, orders_payload, self.channel, batch_size=20)

        shop.sudo().write({'last_order_sync_at': date_to})
        self.env.cr.commit()

        message = (
            f"Imported Lazada orders for {shop.name} on {sync_date}. "
            f"Created: {result.get('created', 0)}, Updated: {result.get('updated', 0)}, "
            f"Errors: {result.get('errors', 0)}"
        )

        return {
            'message': message,
            'created': result.get('created', 0),
            'updated': result.get('updated', 0),
            'errors': result.get('errors', 0),
        }

