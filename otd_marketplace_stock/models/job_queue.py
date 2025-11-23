# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from datetime import datetime, timedelta
from odoo.tools import float_utils
import logging
import json
import base64
import requests

_logger = logging.getLogger(__name__)

# Import StockSyncService for calculating available quantity
from ..models.stock_sync import StockSyncService


class MarketplaceJob(models.Model):
    _name = 'marketplace.job'
    _description = 'Marketplace Job Queue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, next_run_at asc, id asc'

    name = fields.Char(string='Job Name', required=True, index=True)
    job_id_display = fields.Char(string='Job ID', compute='_compute_job_id_display', store=False)
    job_type = fields.Selection([
        ('pull_order', 'Pull Orders'),
        ('push_stock', 'Push Stock'),
        ('sync_product', 'Sync Product'),
        ('sync_product_from_zortout', 'Sync Products from Zortout'),
        ('sync_products_from_woocommerce', 'Sync Products from WooCommerce'),
        ('sync_stock_from_zortout', 'Sync Stock from Zortout'),
        ('lazada_import_products', 'Lazada: Import Products'),
        ('lazada_update_images', 'Lazada: Update Product Images'),
        ('lazada_push_stock', 'Lazada: Sync Stock'),
        ('lazada_backfill_orders', 'Lazada: Backfill Orders'),
        ('woocommerce_backfill_orders', 'WooCommerce: Backfill Orders'),
        ('webhook', 'Process Webhook'),
    ], string='Job Type', required=True, index=True)
    
    def _compute_job_id_display(self):
        """Compute Job ID as string without comma formatting"""
        for record in self:
            # Read id directly without depending on it
            # Use format to ensure no comma formatting
            if record.id:
                record.job_id_display = f"{record.id}"
            else:
                record.job_id_display = ''
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('failed', 'Failed'),
        ('dead', 'Dead Letter'),
    ], string='State', default='pending', index=True, tracking=True)
    
    priority = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low'),
    ], string='Priority', default='medium', index=True)
    
    # Progress tracking
    progress = fields.Float(string='Progress (%)', default=0.0, digits=(5, 2))
    processed_items = fields.Integer(string='Processed Items', default=0)
    total_items = fields.Integer(string='Total Items', default=0)
    
    # Retry logic
    retries = fields.Integer(string='Retries', default=0)
    max_retries = fields.Integer(string='Max Retries', default=3)
    
    # Timing
    next_run_at = fields.Datetime(string='Next Run At', index=True)
    started_at = fields.Datetime(string='Started At', readonly=True)
    completed_at = fields.Datetime(string='Completed At', readonly=True)
    duration_seconds = fields.Float(string='Duration (seconds)', compute='_compute_duration_seconds', store=True)
    
    # Job data
    payload = fields.Text(string='Payload', default='{}', help='JSON payload for job execution')
    result = fields.Text(string='Result', readonly=True, help='JSON result from job execution')
    last_error = fields.Text(string='Last Error', readonly=True)
    
    # Relations
    account_id = fields.Many2one('marketplace.account', string='Account', ondelete='cascade', index=True)
    shop_id = fields.Many2one('marketplace.shop', string='Shop', ondelete='cascade', index=True)

    @api.depends('started_at', 'completed_at')
    def _compute_duration_seconds(self):
        """Compute duration in seconds"""
        for job in self:
            if job.started_at and job.completed_at:
                delta = job.completed_at - job.started_at
                job.duration_seconds = delta.total_seconds()
            else:
                job.duration_seconds = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        """Auto-set priority based on job type if not explicitly set
        Also ensure next_run_at is set for pending jobs
        """
        now = fields.Datetime.now()
        for vals in vals_list:
            if 'priority' not in vals:
                if vals.get('job_type') == 'pull_order':
                    vals['priority'] = 'high'
                elif vals.get('job_type') in ['sync_product_from_zortout', 'sync_products_from_woocommerce', 'lazada_import_products', 'lazada_update_images', 'lazada_backfill_orders', 'woocommerce_backfill_orders']:
                    vals['priority'] = 'medium'
                elif vals.get('job_type') in ['push_stock', 'sync_stock_from_zortout', 'lazada_push_stock']:
                    vals['priority'] = 'medium'
            
            # Ensure payload is JSON string
            if 'payload' in vals and isinstance(vals['payload'], dict):
                vals['payload'] = json.dumps(vals['payload'], ensure_ascii=False)
            
            # Ensure next_run_at is set for pending jobs
            # If not provided or is False/None, set to now
            job_state = vals.get('state', 'pending')
            if job_state == 'pending':
                if 'next_run_at' not in vals or not vals.get('next_run_at'):
                    vals['next_run_at'] = now
        
        jobs = super().create(vals_list)
        
        # Double-check: if any job still has next_run_at=False, fix it
        jobs_to_fix = jobs.filtered(lambda j: j.state == 'pending' and not j.next_run_at)
        if jobs_to_fix:
            jobs_to_fix.write({'next_run_at': now})
            _logger.warning(f'Fixed {len(jobs_to_fix)} jobs with missing next_run_at')
        
        return jobs

    def write(self, vals):
        """Ensure payload is JSON string when writing"""
        if 'payload' in vals and isinstance(vals['payload'], dict):
            vals['payload'] = json.dumps(vals['payload'], ensure_ascii=False)
        return super().write(vals)

    def _update_progress(self, processed, total):
        """Update job progress
        Args:
            processed: Number of items processed
            total: Total number of items to process
        """
        self.ensure_one()
        if total > 0:
            progress = (processed / total) * 100.0
            self.write({
                'progress': min(100.0, max(0.0, progress)),
                'processed_items': processed,
                'total_items': total,
            })
            # Commit progress update to make it visible in real-time
            self.env.cr.commit()

    def _get_payload_dict(self):
        """Return payload as dictionary"""
        self.ensure_one()
        if not self.payload:
            return {}
        if isinstance(self.payload, dict):
            return self.payload
        try:
            return json.loads(self.payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    def _select_jobs_to_process(self, limit=10):
        """Select jobs to process based on priority and constraints
        Args:
            limit: Maximum number of jobs to select
        Returns:
            Recordset of jobs to process
        """
        now = fields.Datetime.now()
        
        # Get jobs ready to run (pending and next_run_at <= now)
        # Prioritize pull_order jobs - they should run first
        all_jobs = self.search([
            ('state', '=', 'pending'),
            ('next_run_at', '<=', now),
        ], order='priority desc, next_run_at asc, id asc', limit=limit * 3)  # Get more to filter
        
        # Separate pull_order jobs (high priority) from other jobs
        pull_order_jobs = all_jobs.filtered(lambda j: j.job_type == 'pull_order')
        other_jobs = all_jobs - pull_order_jobs
        
        # Combine: pull_order jobs first, then other jobs (both sorted by priority)
        jobs = pull_order_jobs + other_jobs
        
        # Group by account and limit concurrent jobs per account
        selected_jobs = self.env['marketplace.job']
        account_job_counts = {}  # account_id -> count of in_progress jobs
        
        for job in jobs:
            account_id = job.account_id.id if job.account_id else None
            
            # Skip Shopee pull_order jobs for accounts that are not fully connected
            if job.job_type == 'pull_order' and job.account_id and job.account_id.channel == 'shopee':
                account = job.account_id
                has_access_token = bool(account.access_token)
                has_refresh_token = bool(account.refresh_token)
                if not has_access_token or not has_refresh_token:
                    _logger.debug(f'Skipping pull_order job #{job.id} for Shopee account {account.name} - not fully connected (access_token: {has_access_token}, refresh_token: {has_refresh_token})')
                    continue
            
            # Check max concurrent jobs per account
            if account_id:
                max_concurrent = job.account_id.max_concurrent_jobs or 3
                if account_id not in account_job_counts:
                    # Count in_progress jobs for this account
                    account_job_counts[account_id] = self.search_count([
                        ('account_id', '=', account_id),
                        ('state', '=', 'in_progress'),
                    ])
                
                if account_job_counts[account_id] >= max_concurrent:
                    continue  # Skip this job, account is at max concurrent jobs
                
                account_job_counts[account_id] += 1
            
            selected_jobs |= job
            
            if len(selected_jobs) >= limit:
                break
        
        # Sort batch jobs by batch_index within each priority level
        # Note: After sorting, we need to re-validate max_concurrent_jobs constraint
        # because batch jobs might be reordered
        if selected_jobs:
            # Helper function to parse payload safely
            def get_payload_dict(job):
                if not job.payload:
                    return {}
                if isinstance(job.payload, dict):
                    return job.payload
                try:
                    return json.loads(job.payload)
                except (json.JSONDecodeError, TypeError):
                    return {}
            
            # Separate batch and non-batch jobs
            batch_jobs = selected_jobs.filtered(lambda j: get_payload_dict(j).get('batch_index') is not None)
            non_batch_jobs = selected_jobs - batch_jobs
            
            # Sort batch jobs by batch_index
            batch_jobs_list = sorted(batch_jobs, key=lambda j: (
                j.priority == 'high' and 0 or j.priority == 'medium' and 1 or 2,
                get_payload_dict(j).get('batch_index', 0),
                j.next_run_at
            ))
            
            # Combine: non-batch first, then batch jobs
            selected_jobs = non_batch_jobs | self.env['marketplace.job'].browse([j.id for j in batch_jobs_list])
            
            # Re-validate max_concurrent_jobs constraint after sorting
            # This ensures we don't exceed limit even after reordering
            final_selected_jobs = self.env['marketplace.job']
            account_final_counts = {}
            
            for job in selected_jobs:
                account_id = job.account_id.id if job.account_id else None
                
                if account_id:
                    max_concurrent = job.account_id.max_concurrent_jobs or 3
                    
                    # Get current in_progress count from database
                    if account_id not in account_final_counts:
                        account_final_counts[account_id] = self.search_count([
                            ('account_id', '=', account_id),
                            ('state', '=', 'in_progress'),
                        ])
                    
                    # Check if adding this job would exceed limit
                    if account_final_counts[account_id] >= max_concurrent:
                        _logger.debug(f'Skipping job #{job.id} for account {job.account_id.name} - max concurrent reached ({account_final_counts[account_id]}/{max_concurrent})')
                        continue
                    
                    account_final_counts[account_id] += 1
                
                final_selected_jobs |= job
                
                if len(final_selected_jobs) >= limit:
                    break
            
            selected_jobs = final_selected_jobs
        
        return selected_jobs[:limit]

    def _execute(self):
        """Execute the job based on its type"""
        self.ensure_one()
        
        try:
            # Execute based on job type
            if self.job_type == 'pull_order':
                result = self._execute_pull_order()
            elif self.job_type == 'push_stock':
                result = self._execute_push_stock()
            elif self.job_type == 'sync_product':
                result = self._execute_sync_product()
            elif self.job_type == 'sync_product_from_zortout':
                result = self._execute_sync_product_from_zortout()
            elif self.job_type == 'sync_products_from_woocommerce':
                result = self._execute_sync_products_from_woocommerce()
            elif self.job_type == 'sync_stock_from_zortout':
                result = self._execute_sync_stock_from_zortout()
            elif self.job_type == 'lazada_import_products':
                result = self._execute_lazada_import_products()
            elif self.job_type == 'lazada_update_images':
                result = self._execute_lazada_update_images()
            elif self.job_type == 'lazada_push_stock':
                result = self._execute_lazada_push_stock()
            elif self.job_type == 'lazada_backfill_orders':
                result = self._execute_lazada_backfill_orders()
            elif self.job_type == 'woocommerce_backfill_orders':
                result = self._execute_woocommerce_backfill_orders()
            elif self.job_type == 'webhook':
                result = self._execute_webhook()
            else:
                raise ValueError(f'Unknown job type: {self.job_type}')
            
            return result
        except Exception as e:
            _logger.error(f'Error executing job {self.id} ({self.name}): {e}', exc_info=True)
            raise

    def _execute_with_retry(self):
        """Execute job with retry logic"""
        self.ensure_one()
        
        try:
            # Initialize job state
            self.write({
                'state': 'in_progress',
                'started_at': fields.Datetime.now(),
                'progress': 0.0,
                'total_items': 0,
                'processed_items': 0,
            })
            self.env.cr.commit()
            
            # Execute job
            result = self._execute()
            
            # Success
            self.write({
                'state': 'done',
                'completed_at': fields.Datetime.now(),
                'result': json.dumps(result, ensure_ascii=False) if result else '',
                'last_error': False,
                'progress': 100.0,  # Mark as 100% complete
            })
            # Commit transaction to ensure state is saved to database
            # This prevents jobs from getting stuck in 'in_progress' state
            self.env.cr.commit()
            
            # Post success message (wrapped in try-except to prevent errors)
            try:
                self.message_post(body=f'Job completed successfully: {self.name}')
            except Exception as msg_error:
                _logger.warning(f'Failed to post success message for job {self.id}: {msg_error}')
            
            return result
            
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'Job {self.id} ({self.name}) failed: {error_msg}', exc_info=True)
            
            # Check if we should retry
            if self.retries < self.max_retries:
                # Retry with exponential backoff
                backoff_minutes = 2 ** self.retries  # 2, 4, 8 minutes
                self.write({
                    'state': 'pending',
                    'next_run_at': fields.Datetime.now() + timedelta(minutes=backoff_minutes),
                    'last_error': error_msg,
                    'retries': self.retries + 1,
                })
                # Commit transaction to ensure state is saved
                self.env.cr.commit()
                
                _logger.warning(f'Job {self.id} will retry in {backoff_minutes} minutes (attempt {self.retries + 1}/{self.max_retries})')
            else:
                # Move to dead letter
                self.write({
                    'state': 'dead',
                    'completed_at': fields.Datetime.now(),
                    'last_error': error_msg,
                })
                # Commit transaction to ensure state is saved
                self.env.cr.commit()
                
                _logger.error(f'Job {self.id} moved to dead letter after {self.max_retries} retries')
                
                # Post error message (wrapped in try-except to prevent errors)
                try:
                    self.message_post(body=f'Job failed after {self.max_retries} retries: {error_msg}')
                except Exception as msg_error:
                    _logger.warning(f'Failed to post error message for job {self.id}: {msg_error}')
            
            raise

    @api.model
    def cron_run_jobs(self, job_ids=None):
        """Cron method to run pending jobs
        Args:
            job_ids: Optional list of specific job IDs to run (for testing)
        """
        if job_ids:
            jobs = self.browse(job_ids)
        else:
            jobs = self._select_jobs_to_process(limit=10)
        
        if not jobs:
            return
        
        _logger.warning(f'🔄 Processing {len(jobs)} jobs')
        
        # Double-check max_concurrent_jobs constraint before executing
        # This prevents race conditions where multiple cron processes might select the same jobs
        account_execution_counts = {}
        jobs_to_execute = self.env['marketplace.job']
        
        for job in jobs:
            account_id = job.account_id.id if job.account_id else None
            
            if account_id:
                max_concurrent = job.account_id.max_concurrent_jobs or 3
                
                # Get current in_progress count from database (real-time check)
                if account_id not in account_execution_counts:
                    account_execution_counts[account_id] = self.search_count([
                        ('account_id', '=', account_id),
                        ('state', '=', 'in_progress'),
                    ])
                
                # Check if executing this job would exceed limit
                if account_execution_counts[account_id] >= max_concurrent:
                    _logger.warning(f'⏸️  Skipping job #{job.id} ({job.name}) for account {job.account_id.name} - max concurrent reached ({account_execution_counts[account_id]}/{max_concurrent})')
                    continue
                
                account_execution_counts[account_id] += 1
            
            jobs_to_execute |= job
        
        if jobs_to_execute:
            _logger.warning(f'✅ Executing {len(jobs_to_execute)} jobs (skipped {len(jobs) - len(jobs_to_execute)} due to max_concurrent limit)')
        
        # Execute jobs
        for job in jobs_to_execute:
            try:
                job._execute_with_retry()
            except Exception as e:
                _logger.error(f'Failed to process job {job.id}: {e}', exc_info=True)
                continue

    def _execute_pull_order(self):
        """Execute pull order job"""
        self.ensure_one()
        account = self.account_id
        if not account:
            raise ValueError('Account is required for pull_order job')
        
        shop = self.shop_id
        if not shop:
            raise ValueError('Shop is required for pull_order job')
        
        if account.channel == 'zortout':
            _logger.warning(f'⏸️  Skipping pull_order job #{self.id} for Zortout account {account.name} - pull orders not supported')
            self.write({
                'state': 'done',
                'completed_at': fields.Datetime.now(),
                'result': json.dumps({
                    'orders_fetched': 0,
                    'orders_created': 0,
                    'message': 'Skipped: Zortout does not support order pulling',
                    'skipped': True,
                }, ensure_ascii=False),
                'progress': 100.0,
            })
            self.env.cr.commit()
            return {
                'orders_fetched': 0,
                'orders_created': 0,
                'message': 'Skipped: Zortout does not support order pulling',
                'skipped': True,
            }
        
        # Skip Shopee accounts that are not fully connected (no access_token or refresh_token)
        if account.channel == 'shopee':
            has_access_token = bool(account.access_token)
            has_refresh_token = bool(account.refresh_token)
            if not has_access_token or not has_refresh_token:
                _logger.warning(f'⏸️  Skipping pull_order job #{self.id} for Shopee account {account.name} (ID: {account.id}) - not fully connected (access_token: {has_access_token}, refresh_token: {has_refresh_token})')
                # Mark job as done with a message instead of failing
                self.write({
                    'state': 'done',
                    'completed_at': fields.Datetime.now(),
                    'result': json.dumps({
                        'orders_fetched': 0,
                        'orders_created': 0,
                        'message': 'Skipped: Shopee account not fully connected (missing access_token or refresh_token)',
                        'skipped': True,
                    }, ensure_ascii=False),
                    'progress': 100.0,
                })
                self.env.cr.commit()
                return {
                    'orders_fetched': 0,
                    'orders_created': 0,
                    'message': 'Skipped: Shopee account not fully connected',
                    'skipped': True,
                }
        
        adapter = account._get_adapter(shop=shop)
        
        # Parse payload
        payload = json.loads(self.payload) if self.payload else {}
        date_from = payload.get('date_from')
        date_to = payload.get('date_to')
        
        # If no date range provided, use last_order_sync_at from shop or default to 7 days ago
        if not date_from:
            if shop.last_order_sync_at:
                date_from = shop.last_order_sync_at
            else:
                date_from = fields.Datetime.now() - timedelta(days=7)
        
        if not date_to:
            date_to = fields.Datetime.now()
        
        # Fetch orders
        # LOCKED: Shopee order pulling must pass RAW detailed payloads forward.
        # Rationale:
        # - `create_from_payload(s)` layer is responsible for parsing via adapter.parse_order_payload(...)
        #   and for safely persisting `raw_payload` using json.dumps. Pre‑parsing here can introduce
        #   non‑serializable objects (e.g., datetime) which caused "Object of type datetime is not JSON serializable".
        # - Therefore DO NOT change this to map/parse here. Keep it as RAW payloads.
        if account.channel == 'shopee':
            detailed_payloads = adapter.fetch_orders_list_with_details(
                since=date_from,
                until=date_to,
                time_range_field='create_time',
                page_size=100,
            )
            # Pass RAW payloads forward; downstream create_* methods will parse and
            # also store raw_payload safely (avoids datetime serialization errors).
            orders = detailed_payloads or []
        else:
            # Debug visibility for non-Shopee channels (e.g., Lazada/TikTok)
            if account.channel == 'lazada':
                _logger.warning(
                    "🛰️  Lazada pull window: %s .. %s (shop=%s, account=%s)",
                    date_from, date_to, self.shop_id.name, account.name
                )
            # Lazada: ใช้ updated window เป็นค่าเริ่มต้นเพื่อกันออเดอร์ที่ถูกแก้ไขภายหลัง
            if account.channel == 'lazada':
                orders = adapter.fetch_orders(since=date_from, until=date_to, time_field='updated')
            else:
                orders = adapter.fetch_orders(since=date_from, until=date_to)
            if account.channel == 'lazada':
                try:
                    sample_ids = []
                    for o in (orders or [])[:5]:
                        sample_ids.append(
                            o.get('order_id') or o.get('OrderId') or o.get('order_number') or o.get('OrderNumber')
                        )
                    _logger.warning(
                        "📦 Lazada pull result: count=%s sample_ids=%s",
                        len(orders or []), sample_ids
                    )
                except Exception:
                    pass
        
        if not orders:
            _logger.warning(f'No orders found for shop {shop.name} between {date_from} and {date_to}')
            # Try wider date range (30 days) if no orders found and no last_order_sync_at
            if not shop.last_order_sync_at:
                date_from = fields.Datetime.now() - timedelta(days=30)
                # LOCKED: Same rule as above (see note) — keep RAW payloads for Shopee.
                if account.channel == 'shopee':
                    detailed_payloads = adapter.fetch_orders_list_with_details(
                        since=date_from,
                        until=date_to,
                        time_range_field='create_time',
                        page_size=100,
                    )
                    orders = detailed_payloads or []
                else:
                    if account.channel == 'lazada':
                        orders = adapter.fetch_orders(since=date_from, until=date_to, time_field='updated')
                    else:
                        orders = adapter.fetch_orders(since=date_from, until=date_to)
                _logger.warning(f'Trying wider date range (30 days): found {len(orders)} orders')
        
        if not orders:
            # Even if no orders were returned, persist the attempted sync time
            try:
                shop.write({'last_order_sync_at': date_to})
            except Exception as e:
                _logger.warning(f'Failed to update last_order_sync_at for shop {shop.name}: {e}')
            return {'orders_fetched': 0, 'orders_created': 0, 'message': 'No orders found'}
        
        # Initialize progress tracking
        total_orders = len(orders)
        if total_orders > 0:
            self.write({
                'total_items': total_orders,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()
        
        # Process orders using bulk operations for better performance
        # Use bulk operations if we have multiple orders (>= 3), otherwise use single create
        # Reduced threshold from 5 to 3 for faster processing
        created_count = 0
        # Force Salesperson to ON THIS DAY Bot (superuser / base.user_root) when created by cron
        bot_user = self.env.ref('base.user_root', raise_if_not_found=False)
        order_model_env = self.env['marketplace.order'].sudo()
        if bot_user:
            # active_test=False is not strictly needed for create, but keeps future searches consistent
            order_model_env = order_model_env.with_context(
                default_user_id=bot_user.id,
                active_test=False,
            )
        if total_orders >= 3:
            _logger.info(f'Using bulk operations for {total_orders} orders')
            try:
                # Increased batch_size from 20 to 50 for faster processing (fewer commits)
                result = order_model_env.create_from_payloads_bulk(
                    self.shop_id, orders, account.channel, batch_size=50
                )
                created_count = result['created'] + result['updated']
                error_count = result['errors']
                
                # Update progress to 100%
                if total_orders > 0:
                    self._update_progress(total_orders, total_orders)
                
                if error_count > 0:
                    _logger.warning(f'Failed to create {error_count} orders out of {total_orders}')
            except Exception as e:
                _logger.error(f'Bulk create failed, falling back to single create: {e}', exc_info=True)
                # Fallback to single create (use order_model_env to preserve default_user_id context)
                created_count = 0
                for idx, order_payload in enumerate(orders, 1):
                    try:
                        order_model_env.create_from_payload(
                            self.shop_id, order_payload, account.channel
                        )
                        created_count += 1
                        
                        # Update progress every 10 orders
                        if idx % 10 == 0 or idx == total_orders:
                            self._update_progress(idx, total_orders)
                    except Exception as order_error:
                        _logger.error(f'Failed to create order: {order_error}', exc_info=True)
                        # Still update progress even if order creation failed
                        if idx % 10 == 0 or idx == total_orders:
                            self._update_progress(idx, total_orders)
        else:
            # Use single create for small number of orders
            _logger.info(f'Using single create for {total_orders} orders')
            created_count = 0
            for idx, order_payload in enumerate(orders, 1):
                try:
                    order_model_env.create_from_payload(
                        self.shop_id, order_payload, account.channel
                    )
                    created_count += 1
                    
                    # Update progress every 10 orders
                    if idx % 10 == 0 or idx == total_orders:
                        self._update_progress(idx, total_orders)
                except Exception as e:
                    _logger.error(f'Failed to create order: {e}', exc_info=True)
                    # Still update progress even if order creation failed
                    if idx % 10 == 0 or idx == total_orders:
                        self._update_progress(idx, total_orders)
        
        # Update last_order_sync_at on shop if any orders were fetched in the window
        # Even when all were existing (created_count=0), we still consider the pull successful
        if total_orders > 0:
            try:
                shop.write({'last_order_sync_at': date_to})
            except Exception as e:
                _logger.warning(f'Failed to update last_order_sync_at for shop {shop.name}: {e}')
        
        return {
            'orders_fetched': total_orders,
            'orders_created': created_count,
            'message': f'Pulled {created_count} orders',
        }

    def _execute_push_stock(self):
        """Execute push stock job"""
        self.ensure_one()
        account = self.account_id
        if not account:
            raise ValueError('Account is required for push_stock job')
        if account.channel == 'zortout':
            _logger.info('Skipping push_stock job %s for Zortout account %s (inbound-only)', self.id, account.name)
            return {
                'message': 'Zortout integration is inbound-only; stock push skipped.',
                'count': 0,
                'skipped': True,
            }
        
        adapter = account._get_adapter(shop=self.shop_id)
        
        # Parse payload
        payload = json.loads(self.payload) if self.payload else {}
        binding_ids = payload.get('binding_ids', [])
        
        if not binding_ids:
            return {'message': 'No bindings to push', 'count': 0}
        
        # Get bindings
        bindings = self.env['marketplace.product.binding'].browse(binding_ids)
        bindings = bindings.filtered(lambda b: b.active and not b.exclude_push and b.shop_id.account_id == account)
        
        if not bindings:
            return {'message': 'No valid bindings to push', 'count': 0}
        
        # Group by shop
        shop_bindings = {}
        for binding in bindings:
            shop_id = binding.shop_id.id
            if shop_id not in shop_bindings:
                shop_bindings[shop_id] = []
            shop_bindings[shop_id].append(binding)
        
        # Calculate total items for progress tracking
        total_bindings_to_push = sum(len(bindings) for bindings in shop_bindings.values())
        if total_bindings_to_push > 0:
            self.write({
                'total_items': total_bindings_to_push,
                'processed_items': 0,
                'progress': 0.0,
            })
            self.env.cr.commit()
        
        # Push stock for each shop
        total_processed = 0
        total_updated = 0
        total_errors = 0
        
        for shop_id, bindings in shop_bindings.items():
            shop = self.env['marketplace.shop'].browse(shop_id)
            shop_adapter = shop.account_id._get_adapter(shop=shop)
            
            # Prepare items to push (with external_product_id if available)
            items_to_push = []
            # Get stock sync service
            stock_sync = StockSyncService(self.env)
            
            for binding in bindings:
                # Use stock_sync service to calculate available quantity
                available_qty = stock_sync.calculate_available_qty(binding)
                
                item = {
                    'sku': binding.external_sku or binding.product_id.default_code,
                    'quantity': available_qty,
                }
                
                # Add external_product_id if available (for WooCommerce performance optimization)
                if binding.external_product_id:
                    item['external_product_id'] = binding.external_product_id
                
                if item['quantity'] is not None:
                    items_to_push.append(item)
            
            if not items_to_push:
                continue
            
            # Push stock
            try:
                result = shop_adapter.update_inventory(items_to_push)
                
                # Handle new result format (with 'results' key) or old format (direct dict)
                if isinstance(result, dict) and 'results' in result:
                    # New format: {'results': {...}, 'updated': X, 'errors': Y}
                    inventory_results = result.get('results', {})
                    total_updated += result.get('updated', 0)
                    total_errors += result.get('errors', 0)
                else:
                    # Old format: direct dict with results
                    inventory_results = result
                    total_updated += sum(1 for r in result.values() if r.get('success', False))
                    total_errors += sum(1 for r in result.values() if not r.get('success', False))
                
                # Update external_product_id for bindings that were pushed successfully
                # This caches the product ID for future pushes
                bindings_to_update = []
                for binding, item in zip(bindings, items_to_push):
                    sku = item.get('sku') or item.get('external_sku')
                    item_result = inventory_results.get(sku) if isinstance(inventory_results, dict) else None
                    
                    if item_result and item_result.get('success'):
                        # Cache product_id for future pushes
                        product_id = item_result.get('product_id')
                        parent_id = item_result.get('parent_id')
                        
                        if product_id:
                            # Format: "parent_id:variation_id" for variations, or just "product_id" for simple products
                            if parent_id:
                                external_product_id = f"{parent_id}:{product_id}"
                            else:
                                external_product_id = str(product_id)
                            
                            # Only update if different from current value
                            if binding.external_product_id != external_product_id:
                                bindings_to_update.append((binding.id, external_product_id))
                
                # Bulk update bindings to reduce database queries
                if bindings_to_update:
                    for binding_id, external_product_id in bindings_to_update:
                        binding = self.env['marketplace.product.binding'].browse(binding_id)
                        binding.write({'external_product_id': external_product_id})
                
                # Commit after all bindings are updated for this batch
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(f'Failed to push stock for shop {shop.name}: {e}', exc_info=True)
                total_errors += len(items_to_push)
            
            total_processed += len(items_to_push)
            # Update progress (cumulative across all shops)
            if total_bindings_to_push > 0:
                self._update_progress(total_processed, total_bindings_to_push)
        
        # Calculate performance metrics
        duration_seconds = (fields.Datetime.now() - self.started_at).total_seconds() if self.started_at else 0
        products_per_second = total_processed / duration_seconds if duration_seconds > 0 else 0
        
        _logger.info(f'📊 Push Stock Performance: {total_processed} products in {duration_seconds:.2f}s ({products_per_second:.2f} products/sec)')
        
        return {
            'message': f'Pushed stock for {total_processed} products',
            'updated': total_updated,
            'errors': total_errors,
            'count': total_processed,
            'duration_seconds': duration_seconds,
            'products_per_second': products_per_second,
        }
    # LOCKED-REGION: สามารถดึงสต็อกจาก Zortout อัตโนมัติ ได้แล้ว ห้ามแก้ตรรกะนี้
    def _execute_sync_stock_from_zortout(self):
        """Execute sync stock from Zortout job"""
        self.ensure_one()
        account = self.account_id
        if not account or account.channel != 'zortout':
            raise ValueError('Zortout account is required for sync_stock_from_zortout job')
        
        adapter = account._get_adapter(shop=None)
        
        # Parse payload
        payload = json.loads(self.payload) if self.payload else {}
        warehouse_code = payload.get('warehouse_code')
        sku_list = payload.get('sku_list', [])
        auto_split = payload.get('auto_split', False)
        batch_size = payload.get('batch_size', 0)
        batch_index = payload.get('batch_index', 0)
        batch_total = payload.get('batch_total', 1)
        
        # Determine stock location
        location = account.stock_location_id
        if not location and warehouse_code:
            warehouse = self.env['stock.warehouse'].sudo().search([
                '|',
                ('code', '=', warehouse_code),
                ('name', '=', warehouse_code),
            ], limit=1)
            if warehouse:
                location = warehouse.lot_stock_id
        if not location and account.company_id:
            warehouse = self.env['stock.warehouse'].sudo().search([
                ('company_id', '=', account.company_id.id),
            ], limit=1)
            if warehouse:
                location = warehouse.lot_stock_id
        if not location:
            location = self.env['stock.location'].sudo().search([
                ('usage', '=', 'internal'),
                ('company_id', '=', account.company_id.id if account.company_id else False),
            ], limit=1)
        if not location:
            raise UserError('No internal stock location found for Zortout stock sync')
        
        location = location.sudo()
        
        # Batch processing constants
        BATCH_COMMIT_SIZE = 50  # Commit every 50 products
        
        # Fetch products from Zortout
        if sku_list:
            products = adapter.fetch_products_by_skus(sku_list)
        else:
            products = adapter.fetch_all_products(warehouse_code=warehouse_code)
        
        if not products:
            return {'message': 'No products found', 'count': 0}
        
        # Initialize progress tracking
        all_products = list(products.values()) if isinstance(products, dict) else products
        total_products = len(all_products)
        self.write({
            'total_items': total_products,
            'processed_items': 0,
            'progress': 0.0,
        })
        self.env.cr.commit()
        
        # Process products in batches
        quant_model = self.env['stock.quant'].sudo().with_company(account.company_id.id if account.company_id else False)
        product_model = self.env['product.product'].sudo().with_company(account.company_id.id if account.company_id else False)
        product_template_model = self.env['product.template'].sudo().with_company(account.company_id.id if account.company_id else False)
        default_uom = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        default_category = self.env.ref('product.product_category_all', raise_if_not_found=False)
        processed_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        created_products = 0
        images_downloaded = 0
        
        for product_data in all_products:
            try:
                sku = product_data.get('sku') or product_data.get('SKU')
                if not sku:
                    processed_count += 1
                    skipped_count += 1
                    continue
                
                # Get stock quantity
                raw_qty = product_data.get('qty')
                if raw_qty is None:
                    raw_qty = product_data.get('quantity')
                if raw_qty is None:
                    raw_qty = product_data.get('stock_quantity')
                if raw_qty is None:
                    raw_qty = product_data.get('stock')
                if raw_qty is None:
                    raw_qty = product_data.get('availablestock')
                try:
                    qty = float(raw_qty or 0.0)
                except (TypeError, ValueError):
                    _logger.warning(f'⚠️ Invalid quantity "{raw_qty}" for SKU {sku}, skipping')
                    processed_count += 1
                    skipped_count += 1
                    continue
                
                # Find Odoo product by SKU
                product_domain = [('default_code', '=', sku)]
                products = product_model.search(product_domain)
                odoo_product = False
                if products:
                    if account.company_id:
                        preferred_products = products.filtered(lambda p: p.company_id and p.company_id.id == account.company_id.id)
                        fallback_products = products.filtered(lambda p: not p.company_id)
                        if preferred_products:
                            odoo_product = preferred_products[:1]
                        elif fallback_products:
                            odoo_product = fallback_products[:1]
                    else:
                        odoo_product = products[:1]
                
                if not odoo_product:
                    # Auto-create product in Odoo if it doesn't exist
                    product_name = product_data.get('name') or sku
                    template_vals = {
                        'name': product_name,
                        'type': 'consu',
                        'is_storable': True,
                        'tracking': 'none',  # Track inventory by quantity by default
                        'sale_ok': True,
                        'purchase_ok': True,
                        'default_code': sku,
                        'barcode': product_data.get('barcode') or False,
                        'company_id': account.company_id.id if account.company_id else False,
                    }
                    if account.company_id:
                        sale_tax = account.company_id.account_sale_tax_id
                        purchase_tax = account.company_id.account_purchase_tax_id
                        if sale_tax:
                            template_vals['taxes_id'] = [(6, 0, sale_tax.ids)]
                        if purchase_tax:
                            template_vals['supplier_taxes_id'] = [(6, 0, purchase_tax.ids)]
                    if default_category:
                        template_vals['categ_id'] = default_category.id
                    if default_uom:
                        template_vals['uom_id'] = default_uom.id
                    sell_price = product_data.get('sellprice') or product_data.get('sell_price')
                    cost_price = product_data.get('purchaseprice') or product_data.get('cost_price')
                    try:
                        if sell_price is not None:
                            template_vals['list_price'] = float(sell_price)
                    except (TypeError, ValueError):
                        pass
                    try:
                        if cost_price is not None:
                            template_vals['standard_price'] = float(cost_price)
                    except (TypeError, ValueError):
                        pass

                    image_url = product_data.get('imagepath') or ''
                    image_list = product_data.get('imageList') or []
                    if not image_url and image_list:
                        image_url = image_list[0]

                    try:
                        template = product_template_model.create(template_vals)
                        odoo_product = template.product_variant_id
                        created_products += 1
                        if image_url:
                            try:
                                image_response = requests.get(image_url, timeout=30)
                                image_response.raise_for_status()
                                template.write({'image_1920': base64.b64encode(image_response.content)})
                                images_downloaded += 1
                            except Exception as image_err:
                                _logger.warning(
                                    'Failed to download image for SKU %s from %s: %s',
                                    sku, image_url, image_err
                                )
                    except Exception as create_err:
                        self.env.cr.rollback()
                        _logger.error(
                            'Failed to auto-create product for SKU %s: %s',
                            sku, create_err, exc_info=True
                        )
                        error_count += 1
                        processed_count += 1
                        continue
                else:
                    template = odoo_product.product_tmpl_id
                    update_vals = {}
                    if template.type != 'consu':
                        update_vals['type'] = 'consu'
                    if not template.is_storable:
                        update_vals['is_storable'] = True
                    if template.tracking not in ('none', False):
                        update_vals['tracking'] = 'none'
                    if update_vals:
                        template_to_write = template.with_company(account.company_id.id) if account.company_id else template
                        try:
                            template_to_write.write(update_vals)
                            odoo_product.invalidate_recordset(['type', 'tracking', 'is_storable'])
                        except Exception as write_err:
                            _logger.warning(
                                'Failed to update template %s (%s) with values %s: %s',
                                template.display_name, sku, update_vals, write_err
                            )
                    if account.company_id:
                        try:
                            company_ctx_template = template.with_company(account.company_id.id)
                            sale_tax = account.company_id.account_sale_tax_id
                            if sale_tax and not company_ctx_template.taxes_id:
                                company_ctx_template.write({
                                    'taxes_id': [(6, 0, sale_tax.ids)],
                                })
                            purchase_tax = account.company_id.account_purchase_tax_id
                            if purchase_tax and not company_ctx_template.supplier_taxes_id:
                                company_ctx_template.write({
                                    'supplier_taxes_id': [(6, 0, purchase_tax.ids)],
                                })
                        except Exception as tax_err:
                            _logger.warning(
                                'Failed to update taxes for product %s (%s): %s',
                                template.display_name, sku, tax_err
                            )
                
                # Determine difference from current available quantity
                available_qty = quant_model._get_available_quantity(
                    odoo_product, location, lot_id=False, package_id=False, owner_id=False, strict=False
                )
                difference = qty - available_qty
                if float_utils.float_is_zero(difference, precision_rounding=odoo_product.uom_id.rounding):
                    skipped_count += 1
                    processed_count += 1
                    continue
                
                try:
                    quant_model._update_available_quantity(
                        odoo_product, location, difference, lot_id=False, package_id=False, owner_id=False
                    )
                    updated_count += 1
                    processed_count += 1
                    
                    if processed_count % BATCH_COMMIT_SIZE == 0:
                        self.env.cr.commit()
                        self._update_progress(processed_count, total_products)
                except Exception as e:
                    self.env.cr.rollback()
                    _logger.error(f'Failed to process product {product_data.get("sku", "unknown")}: {e}', exc_info=True)
                    error_count += 1
                    processed_count += 1
            except Exception as e:
                self.env.cr.rollback()
                _logger.error(f'Failed to process product data: {e}', exc_info=True)
                error_count += 1
                processed_count += 1
        
        # Final commit and progress update
        self.env.cr.commit()
        if total_products > 0:
            self._update_progress(total_products, total_products)
        
        return {
            'message': f'Synced stock for {updated_count} products',
            'updated': updated_count,
            'errors': error_count,
            'skipped': skipped_count,
            'created_products': created_products,
            'images_downloaded': images_downloaded,
            'count': processed_count,
        }
    # END-LOCKED-REGION     
    def _execute_lazada_import_products(self):
        """Execute Lazada product import job"""
        self.ensure_one()
        if not self.account_id or self.account_id.channel != 'lazada':
            raise ValueError('Lazada account is required for lazada_import_products job')
        payload = self._get_payload_dict()
        return self.account_id._lazada_import_products(self.shop_id, payload, job=self)

    def _execute_lazada_update_images(self):
        """Execute Lazada image update job"""
        self.ensure_one()
        if not self.account_id or self.account_id.channel != 'lazada':
            raise ValueError('Lazada account is required for lazada_update_images job')
        payload = self._get_payload_dict()
        return self.account_id._lazada_update_images(self.shop_id, payload, job=self)

    def _execute_lazada_push_stock(self):
        """Execute Lazada stock sync job (reuse push_stock logic)"""
        self.ensure_one()
        return self._execute_push_stock()

    def _execute_lazada_backfill_orders(self):
        """Execute Lazada order backfill job"""
        self.ensure_one()
        if not self.account_id or self.account_id.channel != 'lazada':
            raise ValueError('Lazada account is required for lazada_backfill_orders job')
        payload = self._get_payload_dict()
        return self.account_id._lazada_backfill_orders(self.shop_id, payload, job=self)

    def _execute_woocommerce_backfill_orders(self):
        """Execute WooCommerce order backfill job"""
        self.ensure_one()
        if not self.account_id or self.account_id.channel != 'woocommerce':
            raise ValueError('WooCommerce account is required for woocommerce_backfill_orders job')
        payload = self._get_payload_dict()
        return self.account_id._woocommerce_backfill_orders(self.shop_id, payload, job=self)

    def _execute_sync_products_from_woocommerce(self):
        """Execute sync products from WooCommerce job (background)"""
        self.ensure_one()
        _logger.warning(f'🚀 Starting _execute_sync_products_from_woocommerce for job {self.id}: {self.name}')
        
        account = self.account_id
        if not account or account.channel != 'woocommerce':
            raise ValueError('WooCommerce account is required for sync_products_from_woocommerce')
        
        if not account.sync_enabled:
            return {'skipped': 'Sync disabled for account'}
        
        # Call the sync method from marketplace.account
        # This method will be called from background job, so it won't timeout
        try:
            # Pass the current job for progress updates
            # Note: action_sync_products_from_woocommerce_sync accepts optional job parameter
            result = account.sudo().action_sync_products_from_woocommerce_sync(job=self)
            
            return {
                'message': 'Product sync completed successfully',
                'status': 'success',
                'created': result.get('created', 0),
                'updated': result.get('updated', 0),
                'skipped': result.get('skipped', 0),
                'not_found': result.get('not_found', 0),
            }
        except Exception as e:
            _logger.error(f'❌ WooCommerce product sync failed in job {self.id}: {e}', exc_info=True)
            raise

    def _execute_sync_product(self):
        """Execute sync product job (placeholder)"""
        self.ensure_one()
        return {'message': 'Sync product not implemented', 'count': 0}

    def _execute_sync_product_from_zortout(self):
        """Execute sync product from Zortout job"""
        self.ensure_one()

        account = self.account_id
        if not account:
            raise ValueError('Account is required for sync_product_from_zortout job')

        if account.channel != 'zortout':
            raise ValueError('Zortout account is required for sync_product_from_zortout job')

        payload = {}
        if self.payload:
            if isinstance(self.payload, dict):
                payload = self.payload
            else:
                try:
                    payload = json.loads(self.payload)
                except (json.JSONDecodeError, TypeError):
                    _logger.warning(
                        '⚠️ Zortout job %s has invalid JSON payload: %s',
                        self.id, self.payload
                    )

        try:
            result = account.sudo().action_import_products_from_zortout_sync(
                job=self,
                payload=payload,
            )
            return result or {'message': 'Zortout product import completed'}
        except Exception as exc:
            _logger.error(
                '❌ Zortout product import failed in job %s (%s): %s',
                self.id, self.name, exc,
                exc_info=True
            )
            raise

    def _execute_webhook(self):
        """Execute webhook job (placeholder)"""
        self.ensure_one()
        return {'message': 'Webhook not implemented', 'count': 0}

    def action_run_all_pull_orders_now(self):
        """Run all pending pull_order jobs immediately (priority queue)"""
        self.ensure_one()
        if self.job_type != 'pull_order':
            raise UserError('This action is only available for pull_order jobs')
        
        # Find all pending pull_order jobs for this account/shop
        domain = [
            ('job_type', '=', 'pull_order'),
            ('state', '=', 'pending'),
        ]
        
        if self.account_id:
            domain.append(('account_id', '=', self.account_id.id))
        if self.shop_id:
            domain.append(('shop_id', '=', self.shop_id.id))
        
        pending_jobs = self.search(domain)
        
        if not pending_jobs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Pending Jobs',
                    'message': 'No pending pull_order jobs found.',
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
    
    def action_run_now(self):
        """Action to run job immediately"""
        self.ensure_one()
        if self.state not in ['pending', 'failed']:
            raise UserError('Job can only be run when in pending or failed state')
        
        self.write({
            'next_run_at': fields.Datetime.now(),
            'state': 'pending',
        })
        
        # Trigger cron to process this job
        self.env['marketplace.job'].sudo().cron_run_jobs(job_ids=[self.id])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Started',
                'message': f'Job {self.name} has been started.',
                'type': 'success',
            }
        }

    def action_retry(self):
        """Action to retry failed job"""
        self.ensure_one()
        if self.state not in ['failed', 'dead']:
            raise UserError('Job can only be retried when in failed or dead state')
        
        self.write({
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
            'retries': 0,
            'last_error': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Retried',
                'message': f'Job {self.name} has been retried.',
                'type': 'success',
            }
        }

    def action_move_to_dead(self):
        """Action to move job to dead letter"""
        self.ensure_one()
        if self.state == 'dead':
            raise UserError('Job is already in dead letter')
        
        self.write({
            'state': 'dead',
            'completed_at': fields.Datetime.now(),
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Moved to Dead Letter',
                'message': f'Job {self.name} has been moved to dead letter.',
                'type': 'warning',
            }
        }

    def action_reset_stuck_jobs(self):
        """Action to reset stuck jobs"""
        stuck_threshold = fields.Datetime.now() - timedelta(minutes=60)
        
        # Find stuck jobs (including those with progress = 100% but still in_progress)
        stuck_jobs = self.env['marketplace.job'].search([
            ('state', '=', 'in_progress'),
            '|',
            ('started_at', '<', stuck_threshold),  # Stuck for more than threshold
            ('progress', '=', 100.0),  # Progress = 100% but still in_progress (likely completed but not marked as done)
        ])
        
        if not stuck_jobs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Stuck Jobs',
                    'message': 'No stuck jobs found.',
                    'type': 'info',
                }
            }
        
        count = len(stuck_jobs)
        stuck_jobs.write({
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
            'progress': 0.0,
            'processed_items': 0,
            'total_items': 0,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Stuck Jobs Reset',
                'message': f'Reset {count} stuck job(s).',
                'type': 'success',
            }
        }

    @api.model
    def cron_reset_stuck_jobs(self):
        """Cron method to reset stuck jobs"""
        return self.action_reset_stuck_jobs()

    def action_cleanup_duplicate_jobs(self):
        """Action to cleanup duplicate jobs"""
        # Find duplicate pending jobs (same job_type, account_id, shop_id)
        duplicates = self.env['marketplace.job'].search([
            ('state', '=', 'pending'),
        ])
        
        # Group by (job_type, account_id, shop_id)
        job_groups = {}
        for job in duplicates:
            key = (job.job_type, job.account_id.id if job.account_id else None, job.shop_id.id if job.shop_id else None)
            if key not in job_groups:
                job_groups[key] = []
            job_groups[key].append(job)
        
        # Keep only the latest job in each group, delete others
        deleted_count = 0
        for key, jobs in job_groups.items():
            if len(jobs) > 1:
                # Sort by create_date desc, keep first (latest), delete rest
                jobs_sorted = sorted(jobs, key=lambda j: j.create_date, reverse=True)
                to_delete = jobs_sorted[1:]
                for job in to_delete:
                    job.unlink()
                    deleted_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Duplicate Jobs Cleaned',
                'message': f'Deleted {deleted_count} duplicate job(s).',
                'type': 'success',
            }
        }
    
    def action_cleanup_old_done_jobs(self):
        """Action button to cleanup old done jobs (default: 7 days)"""
        return self.sudo().env['marketplace.job'].action_cleanup_old_done_jobs(days=7, job_types=None, keep_count=None)
    
    @api.model
    def action_cleanup_old_done_jobs(self, days=7, job_types=None, keep_count=None):
        """Action to cleanup old done jobs
        
        Args:
            days: Number of days to keep (default: 7)
            job_types: List of job types to cleanup (None = all types)
            keep_count: Number of recent jobs to keep per job_type (None = no limit)
        
        Returns:
            dict with cleanup result
        """
        now = fields.Datetime.now()
        cutoff_date = now - timedelta(days=days)
        
        # Build domain
        domain = [
            ('state', '=', 'done'),
            ('completed_at', '!=', False),
            ('completed_at', '<', cutoff_date),
        ]
        
        if job_types:
            domain.append(('job_type', 'in', job_types))
        
        # Find old done jobs
        old_jobs = self.env['marketplace.job'].search(domain, order='completed_at asc')
        
        if not old_jobs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Old Jobs',
                    'message': f'No done jobs older than {days} days found.',
                    'type': 'info',
                }
            }
        
        # If keep_count is specified, keep the most recent N jobs per job_type
        if keep_count and keep_count > 0:
            # Group by job_type
            jobs_by_type = {}
            for job in old_jobs:
                job_type = job.job_type
                if job_type not in jobs_by_type:
                    jobs_by_type[job_type] = []
                jobs_by_type[job_type].append(job)
            
            # Keep only the most recent jobs per type
            jobs_to_delete = []
            for job_type, jobs in jobs_by_type.items():
                # Sort by completed_at desc
                jobs_sorted = sorted(jobs, key=lambda j: j.completed_at or j.create_date, reverse=True)
                # Keep the most recent N jobs
                to_keep = jobs_sorted[:keep_count]
                # Delete the rest
                to_delete = jobs_sorted[keep_count:]
                jobs_to_delete.extend(to_delete)
            
            old_jobs = jobs_to_delete
        
        # Delete jobs
        deleted_count = len(old_jobs)
        job_types_deleted = {}
        for job in old_jobs:
            job_type = job.job_type
            job_types_deleted[job_type] = job_types_deleted.get(job_type, 0) + 1
        
        # Delete in batches to avoid timeout
        batch_size = 100
        for i in range(0, len(old_jobs), batch_size):
            batch = old_jobs[i:i + batch_size]
            batch.unlink()
            self.env.cr.commit()
        
        # Build summary message
        summary = f'Deleted {deleted_count} old done job(s)'
        if job_types_deleted:
            type_summary = ', '.join([f'{k}: {v}' for k, v in job_types_deleted.items()])
            summary += f' ({type_summary})'
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Old Jobs Cleaned',
                'message': summary,
                'type': 'success',
            }
        }
    
    @api.model
    def cron_cleanup_old_done_jobs(self):
        """Cron method to cleanup old done jobs automatically"""
        # Get cleanup settings from accounts
        accounts = self.env['marketplace.account'].search([
            ('job_cleanup_enabled', '=', True),
            ('job_cleanup_retention_days', '>', 0),
        ])
        
        total_deleted = 0
        for account in accounts:
            try:
                days = account.job_cleanup_retention_days
                job_types = account.job_cleanup_job_types.split(',') if account.job_cleanup_job_types else None
                keep_count = account.job_cleanup_keep_count if account.job_cleanup_keep_count > 0 else None
                
                # Get jobs for this account
                domain = [
                    ('state', '=', 'done'),
                    ('account_id', '=', account.id),
                    ('completed_at', '!=', False),
                    ('completed_at', '<', fields.Datetime.now() - timedelta(days=days)),
                ]
                
                if job_types:
                    domain.append(('job_type', 'in', job_types))
                
                old_jobs = self.search(domain, order='completed_at asc')
                
                if keep_count and keep_count > 0:
                    # Group by job_type and keep only the most recent N jobs
                    jobs_by_type = {}
                    for job in old_jobs:
                        job_type = job.job_type
                        if job_type not in jobs_by_type:
                            jobs_by_type[job_type] = []
                        jobs_by_type[job_type].append(job)
                    
                    jobs_to_delete = []
                    for job_type, jobs in jobs_by_type.items():
                        jobs_sorted = sorted(jobs, key=lambda j: j.completed_at, reverse=True)
                        to_delete = jobs_sorted[keep_count:]
                        jobs_to_delete.extend(to_delete)
                    
                    old_jobs = jobs_to_delete
                
                # Delete jobs in batches
                if old_jobs:
                    batch_size = 100
                    for i in range(0, len(old_jobs), batch_size):
                        batch = old_jobs[i:i + batch_size]
                        batch.unlink()
                        self.env.cr.commit()
                    
                    total_deleted += len(old_jobs)
                    _logger.info(f'Cleaned up {len(old_jobs)} old done jobs for account {account.name}')
            
            except Exception as e:
                _logger.error(f'Failed to cleanup old jobs for account {account.name}: {e}', exc_info=True)
        
        if total_deleted > 0:
            _logger.info(f'Total cleaned up {total_deleted} old done jobs')
        
        return True
