# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta
import logging
import json
from ast import literal_eval

_logger = logging.getLogger(__name__)


def _load_job_payload(payload):
    """Return job payload as dict regardless of stored representation."""
    if not payload:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode('utf-8')
    if isinstance(payload, str):
        payload = payload.strip()
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            try:
                return literal_eval(payload)
            except (ValueError, SyntaxError):
                _logger.warning('Unable to parse job payload: %s', payload[:200])
                return {}
    return {}


class StockSyncService:
    """Service for calculating stock quantities for marketplace push"""
    
    def __init__(self, env):
        self.env = env
    
    def calculate_available_qty(self, binding):
        """
        Calculate available quantity for a product binding
        
        Returns: int or None (None if exclude_push or error)
        """
        if binding.exclude_push or not binding.active:
            return None
        
        product = binding.product_id
        shop = binding.shop_id
        account = shop.account_id
        
        # Get stock location
        location = account.stock_location_id or shop.warehouse_id.lot_stock_id
        if not location:
            # Try to find any internal location for company
            location = self.env['stock.location'].search([
                ('usage', '=', 'internal'),
                ('company_id', '=', shop.company_id.id),
            ], limit=1)
        
        if not location:
            _logger.warning(f'No stock location found for binding {binding.id}')
            return None
        
        # Get available quantity
        qty_available = product.with_context(location=location.id).qty_available
        
        # Get sync rule
        rule = self.env['marketplace.sync.rule'].get_rule_for_binding(binding)
        
        # Apply buffer
        if binding.buffer_qty_override is not False and binding.buffer_qty_override is not None:
            buffer = binding.buffer_qty_override
        elif rule and rule.buffer_qty is not False and rule.buffer_qty is not None:
            buffer = rule.buffer_qty
        else:
            buffer = account.push_buffer_qty or 0
        
        # Apply minimum
        if binding.min_qty_override is not False and binding.min_qty_override is not None:
            min_qty = binding.min_qty_override
        elif rule and rule.min_qty is not False and rule.min_qty is not None:
            min_qty = rule.min_qty
        else:
            min_qty = account.min_online_qty or 0
        
        # Apply rounding
        rounding = None
        if rule and rule.rounding:
            rounding = rule.rounding
        
        # Calculate
        available_qty = qty_available - buffer
        
        # Apply minimum
        if available_qty < min_qty:
            available_qty = 0
        
        # Apply rounding
        if rounding and available_qty > 0:
            available_qty = (available_qty // rounding) * rounding
        
        return max(0, int(available_qty))


class StockMove(models.Model):
    _inherit = 'stock.move'
    
    def _action_done(self, cancel_backorder=False):
        """Override to queue stock push jobs when moves are completed"""
        result = super()._action_done(cancel_backorder)
        
        # Queue stock push for affected products
        self._queue_stock_push_for_moves()
        
        return result
    
    def _queue_stock_push_for_moves(self):
        """Queue stock push jobs for products affected by these moves"""
        # Get affected products
        product_ids = self.mapped('product_id').ids
        if not product_ids:
            return
        
        # Find bindings for these products
        bindings = self.env['marketplace.product.binding'].search([
            ('product_id', 'in', product_ids),
            ('active', '=', True),
            ('exclude_push', '=', False),
            ('shop_id.account_id.channel', '!=', 'zortout'),
        ])
        
        if not bindings:
            return
        
        # Group by shop to minimize API calls
        shop_bindings = {}
        for binding in bindings:
            shop_id = binding.shop_id.id
            if shop_id not in shop_bindings:
                shop_bindings[shop_id] = []
            shop_bindings[shop_id].append(binding.id)
        
        # Create jobs per shop (with debounce - check if recent job exists)
        current_time = fields.Datetime.now()
        for shop_id, binding_ids in shop_bindings.items():
            shop = self.env['marketplace.shop'].browse(shop_id)
            account = shop.account_id

            if account.channel == 'zortout':
                continue
            
            if not account.sync_enabled:
                continue
            
            # Check batch size from account settings
            batch_size = account.push_stock_batch_size or 0  # 0 = no batching
            
            # Check for recent job (debounce within 10 minutes) first
            recent_job = self.env['marketplace.job'].search([
                ('job_type', '=', 'push_stock'),
                ('shop_id', '=', shop_id),
                ('state', '=', 'pending'),
                ('create_date', '>=', current_time - timedelta(minutes=10)),
            ], order='create_date desc', limit=1)
            
            if recent_job:
                recent_payload = _load_job_payload(recent_job.payload)
                # Merge new bindings into existing job
                existing_bindings = set(recent_payload.get('binding_ids', []))
                existing_bindings.update(binding_ids)
                merged_binding_ids = list(existing_bindings)
                
                # After merging, check if we need to split into batches
                # This handles the case where merged bindings exceed batch_size
                if batch_size > 0 and len(merged_binding_ids) > batch_size:
                    # Delete the existing job and create batch jobs instead
                    _logger.warning(f'📦 Merged bindings ({len(merged_binding_ids)}) exceed batch_size ({batch_size}) - splitting into batches for shop {shop.name}')
                    recent_job.unlink()
                    
                    # Create batch jobs
                    total_bindings = len(merged_binding_ids)
                    batch_count = (total_bindings + batch_size - 1) // batch_size
                    
                    for batch_idx in range(batch_count):
                        start_idx = batch_idx * batch_size
                        end_idx = min(start_idx + batch_size, total_bindings)
                        batch_binding_ids = merged_binding_ids[start_idx:end_idx]
                        
                        batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                        
                        batch_payload = {
                            'binding_ids': batch_binding_ids,
                            'batch_index': batch_idx,
                            'batch_total': batch_count,
                            'batch_size': batch_size,
                        }
                        self.env['marketplace.job'].sudo().create({
                            'name': f'Push stock for shop {shop.name} (Batch {batch_idx + 1}/{batch_count})',
                            'job_type': 'push_stock',
                            'shop_id': shop_id,
                            'account_id': account.id,
                            'priority': 'medium',
                            'payload': json.dumps(batch_payload, ensure_ascii=False),
                            'next_run_at': batch_next_run,
                        })
                else:
                    # Update existing job (bindings still within batch_size or batching disabled)
                    recent_job.write({
                        'payload': json.dumps({'binding_ids': merged_binding_ids}, ensure_ascii=False),
                        'next_run_at': current_time,
                    })
            else:
                # No recent job - create new job(s)
                if batch_size == 0 or len(binding_ids) <= batch_size:
                    # Create single job
                    payload_vals = {'binding_ids': binding_ids}
                    self.env['marketplace.job'].sudo().create({
                        'name': f'Push stock for shop {shop.name}',
                        'job_type': 'push_stock',
                        'shop_id': shop_id,
                        'account_id': account.id,
                        'priority': 'medium',
                        'payload': json.dumps(payload_vals, ensure_ascii=False),
                        'next_run_at': current_time,
                    })
                else:
                    # Split into batches
                    total_bindings = len(binding_ids)
                    batch_count = (total_bindings + batch_size - 1) // batch_size  # Ceiling division
                    
                    _logger.warning(f'📦 Splitting {total_bindings} bindings into {batch_count} batches of {batch_size} for shop {shop.name}')
                    
                    # Create batch jobs with staggered next_run_at to avoid overload
                    for batch_idx in range(batch_count):
                        start_idx = batch_idx * batch_size
                        end_idx = min(start_idx + batch_size, total_bindings)
                        batch_binding_ids = binding_ids[start_idx:end_idx]
                        
                        # Stagger jobs: each batch starts 5 seconds after previous
                        batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                        
                        batch_payload = {
                            'binding_ids': batch_binding_ids,
                            'batch_index': batch_idx,
                            'batch_total': batch_count,
                            'batch_size': batch_size,
                        }
                        self.env['marketplace.job'].sudo().create({
                            'name': f'Push stock for shop {shop.name} (Batch {batch_idx + 1}/{batch_count})',
                            'job_type': 'push_stock',
                            'shop_id': shop_id,
                            'account_id': account.id,
                            'priority': 'medium',
                            'payload': json.dumps(batch_payload, ensure_ascii=False),
                            'next_run_at': batch_next_run,
                        })


class StockQuant(models.Model):
    _inherit = 'stock.quant'
    
    def write(self, vals):
        """Override to trigger stock push on quantity changes"""
        result = super().write(vals)
        
        if 'quantity' in vals:
            # Queue stock push for affected products
            self._queue_stock_push_for_quants()
        
        return result
    
    def _queue_stock_push_for_quants(self):
        """Queue stock push for products in these quants"""
        product_ids = self.mapped('product_id').ids
        if not product_ids:
            return
        
        # Same logic as stock move
        bindings = self.env['marketplace.product.binding'].search([
            ('product_id', 'in', product_ids),
            ('active', '=', True),
            ('exclude_push', '=', False),
            ('shop_id.account_id.channel', '!=', 'zortout'),
        ])
        
        if not bindings:
            return
        
        shop_bindings = {}
        for binding in bindings:
            shop_id = binding.shop_id.id
            if shop_id not in shop_bindings:
                shop_bindings[shop_id] = []
            shop_bindings[shop_id].append(binding.id)
        
        current_time = fields.Datetime.now()
        for shop_id, binding_ids in shop_bindings.items():
            shop = self.env['marketplace.shop'].browse(shop_id)
            account = shop.account_id

            if account.channel == 'zortout':
                continue
            
            if not account.sync_enabled:
                continue
            
            # Check batch size from account settings
            batch_size = account.push_stock_batch_size or 0  # 0 = no batching
            
            # Check for recent job (debounce within 10 minutes) first
            recent_job = self.env['marketplace.job'].search([
                ('job_type', '=', 'push_stock'),
                ('shop_id', '=', shop_id),
                ('state', '=', 'pending'),
                ('create_date', '>=', current_time - timedelta(minutes=10)),
            ], order='create_date desc', limit=1)
            
            if recent_job:
                recent_payload = _load_job_payload(recent_job.payload)
                # Merge new bindings into existing job
                existing_bindings = set(recent_payload.get('binding_ids', []))
                existing_bindings.update(binding_ids)
                merged_binding_ids = list(existing_bindings)
                
                # After merging, check if we need to split into batches
                # This handles the case where merged bindings exceed batch_size
                if batch_size > 0 and len(merged_binding_ids) > batch_size:
                    # Delete the existing job and create batch jobs instead
                    _logger.warning(f'📦 Merged bindings ({len(merged_binding_ids)}) exceed batch_size ({batch_size}) - splitting into batches for shop {shop.name}')
                    recent_job.unlink()
                    
                    # Create batch jobs
                    total_bindings = len(merged_binding_ids)
                    batch_count = (total_bindings + batch_size - 1) // batch_size
                    
                    for batch_idx in range(batch_count):
                        start_idx = batch_idx * batch_size
                        end_idx = min(start_idx + batch_size, total_bindings)
                        batch_binding_ids = merged_binding_ids[start_idx:end_idx]
                        
                        batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                        
                        batch_payload = {
                            'binding_ids': batch_binding_ids,
                            'batch_index': batch_idx,
                            'batch_total': batch_count,
                            'batch_size': batch_size,
                        }
                        self.env['marketplace.job'].sudo().create({
                            'name': f'Push stock for shop {shop.name} (Batch {batch_idx + 1}/{batch_count})',
                            'job_type': 'push_stock',
                            'shop_id': shop_id,
                            'account_id': account.id,
                            'priority': 'medium',
                            'payload': json.dumps(batch_payload, ensure_ascii=False),
                            'next_run_at': batch_next_run,
                        })
                else:
                    # Update existing job (bindings still within batch_size or batching disabled)
                    recent_job.write({
                        'payload': json.dumps({'binding_ids': merged_binding_ids}, ensure_ascii=False),
                        'next_run_at': current_time,
                    })
            else:
                # No recent job - create new job(s)
                if batch_size == 0 or len(binding_ids) <= batch_size:
                    # Create single job
                    payload_vals = {'binding_ids': binding_ids}
                    self.env['marketplace.job'].sudo().create({
                        'name': f'Push stock for shop {shop.name}',
                        'job_type': 'push_stock',
                        'shop_id': shop_id,
                        'account_id': account.id,
                        'priority': 'medium',
                        'payload': json.dumps(payload_vals, ensure_ascii=False),
                        'next_run_at': current_time,
                    })
                else:
                    # Split into batches
                    total_bindings = len(binding_ids)
                    batch_count = (total_bindings + batch_size - 1) // batch_size  # Ceiling division
                    
                    _logger.warning(f'📦 Splitting {total_bindings} bindings into {batch_count} batches of {batch_size} for shop {shop.name}')
                    
                    # Create batch jobs with staggered next_run_at to avoid overload
                    for batch_idx in range(batch_count):
                        start_idx = batch_idx * batch_size
                        end_idx = min(start_idx + batch_size, total_bindings)
                        batch_binding_ids = binding_ids[start_idx:end_idx]
                        
                        # Stagger jobs: each batch starts 5 seconds after previous
                        batch_next_run = current_time + timedelta(seconds=batch_idx * 5)
                        
                        batch_payload = {
                            'binding_ids': batch_binding_ids,
                            'batch_index': batch_idx,
                            'batch_total': batch_count,
                            'batch_size': batch_size,
                        }
                        self.env['marketplace.job'].sudo().create({
                            'name': f'Push stock for shop {shop.name} (Batch {batch_idx + 1}/{batch_count})',
                            'job_type': 'push_stock',
                            'shop_id': shop_id,
                            'account_id': account.id,
                            'priority': 'medium',
                            'payload': json.dumps(batch_payload, ensure_ascii=False),
                            'next_run_at': batch_next_run,
                        })

