# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
import json

_logger = logging.getLogger(__name__)


class MarketplaceShop(models.Model):
    _name = 'marketplace.shop'
    _description = 'Marketplace Shop'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(string='Shop Name', required=True, tracking=True)
    external_shop_id = fields.Char(
        string='External Shop ID', required=True, tracking=True,
        help='Shop ID from marketplace platform'
    )
    account_id = fields.Many2one(
        'marketplace.account', string='Account', required=True,
        ondelete='cascade', tracking=True
    )
    channel = fields.Selection(
        related='account_id.channel', string='Channel', readonly=True, store=True
    )
    company_id = fields.Many2one(
        related='account_id.company_id', string='Company',
        readonly=True, store=True
    )
    active = fields.Boolean(string='Active', default=True, tracking=True)
    
    # Configuration
    timezone = fields.Selection(
        [
            ('Asia/Bangkok', 'Asia/Bangkok (UTC+7)'),
            ('UTC', 'UTC'),
        ],
        string='Timezone', default='Asia/Bangkok'
    )
    warehouse_id = fields.Many2one(
        'stock.warehouse', string='Warehouse',
        help='Warehouse to use for orders from this shop'
    )
    team_id = fields.Many2one(
        'crm.team', string='Sales Team',
        help='Sales team for orders from this shop'
    )
    
    # Sync tracking
    last_order_sync_at = fields.Datetime(
        string='Last Order Sync', readonly=True
    )
    last_stock_sync_at = fields.Datetime(
        string='Last Stock Sync', readonly=True
    )
    
    # Lazada sync dashboard fields
    lazada_product_import_job_id = fields.Many2one(
        'marketplace.job', compute='_compute_lazada_sync_status', store=False,
        string='Lazada Product Import Job', compute_sudo=True
    )
    lazada_product_import_status = fields.Selection(
        [
            ('never', 'Never'),
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('dead', 'Dead Letter'),
        ],
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Product Import Status'
    )
    lazada_product_import_date = fields.Datetime(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Product Import Date'
    )
    lazada_product_import_message = fields.Text(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Product Import Message'
    )
    
    lazada_image_update_job_id = fields.Many2one(
        'marketplace.job', compute='_compute_lazada_sync_status', store=False,
        string='Lazada Image Update Job', compute_sudo=True
    )
    lazada_image_update_status = fields.Selection(
        [
            ('never', 'Never'),
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('dead', 'Dead Letter'),
        ],
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Image Update Status'
    )
    lazada_image_update_date = fields.Datetime(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Image Update Date'
    )
    lazada_image_update_message = fields.Text(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Image Update Message'
    )
    
    lazada_stock_sync_job_id = fields.Many2one(
        'marketplace.job', compute='_compute_lazada_sync_status', store=False,
        string='Lazada Stock Sync Job', compute_sudo=True
    )
    lazada_stock_sync_status = fields.Selection(
        [
            ('never', 'Never'),
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('dead', 'Dead Letter'),
        ],
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Stock Sync Status'
    )
    lazada_stock_sync_date = fields.Datetime(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Stock Sync Date'
    )
    lazada_stock_sync_message = fields.Text(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Stock Sync Message'
    )
    
    lazada_order_backfill_job_id = fields.Many2one(
        'marketplace.job', compute='_compute_lazada_sync_status', store=False,
        string='Lazada Order Backfill Job', compute_sudo=True
    )
    lazada_order_backfill_status = fields.Selection(
        [
            ('never', 'Never'),
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('done', 'Done'),
            ('failed', 'Failed'),
            ('dead', 'Dead Letter'),
        ],
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Order Backfill Status'
    )
    lazada_order_backfill_date = fields.Datetime(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Order Backfill Date'
    )
    lazada_order_backfill_message = fields.Text(
        compute='_compute_lazada_sync_status', store=False, compute_sudo=True,
        string='Order Backfill Message'
    )
    
    # Statistics
    order_count = fields.Integer(
        string='Order Count', compute='_compute_order_count'
    )
    binding_count = fields.Integer(
        string='Product Binding Count', compute='_compute_binding_count'
    )

    @api.depends('account_id')
    def _compute_order_count(self):
        for shop in self:
            shop.order_count = self.env['marketplace.order'].search_count([
                ('shop_id', '=', shop.id)
            ])

    @api.depends('account_id')
    def _compute_binding_count(self):
        for shop in self:
            shop.binding_count = self.env['marketplace.product.binding'].search_count([
                ('shop_id', '=', shop.id)
            ])
    
    def _compute_lazada_sync_status(self):
        """Compute last Lazada job status/messages for dashboard cards"""
        job_model = self.env['marketplace.job'].sudo()
        
        def extract_message(job_record):
            message = job_record.last_error or ''
            if not message and job_record.result:
                try:
                    result_payload = job_record.result
                    if isinstance(result_payload, str):
                        result_payload = json.loads(result_payload)
                    if isinstance(result_payload, dict):
                        message = result_payload.get('message', '')
                        if not message:
                            # try standard keys
                            message = result_payload.get('status') or ''
                    else:
                        message = str(job_record.result)
                except (ValueError, TypeError, json.JSONDecodeError):
                    message = job_record.result if isinstance(job_record.result, str) else ''
            return message

        def get_job_data(shop_id, job_type):
            job = job_model.search([
                ('shop_id', '=', shop_id),
                ('job_type', '=', job_type),
            ], limit=1, order='id desc')
            if job:
                status = job.state or 'pending'
                when = job.completed_at or job.started_at or job.create_date
                message = extract_message(job)
            else:
                job = False
                status = 'never'
                when = False
                message = ''
            return job, status, when, message
        
        for shop in self:
            if shop.channel == 'woocommerce':
                # Reset Lazada-specific job info
                shop.lazada_product_import_job_id = False
                shop.lazada_product_import_status = 'never'
                shop.lazada_product_import_date = False
                shop.lazada_product_import_message = ''

                shop.lazada_image_update_job_id = False
                shop.lazada_image_update_status = 'never'
                shop.lazada_image_update_date = False
                shop.lazada_image_update_message = ''

                shop.lazada_stock_sync_job_id = False
                shop.lazada_stock_sync_status = 'never'
                shop.lazada_stock_sync_date = False
                shop.lazada_stock_sync_message = ''

                job, status, when, message = get_job_data(shop.id, 'woocommerce_backfill_orders')
                shop.lazada_order_backfill_job_id = job
                shop.lazada_order_backfill_status = status
                shop.lazada_order_backfill_date = when
                shop.lazada_order_backfill_message = message
                continue

            if shop.channel != 'lazada':
                shop.lazada_product_import_job_id = False
                shop.lazada_product_import_status = 'never'
                shop.lazada_product_import_date = False
                shop.lazada_product_import_message = ''
                
                shop.lazada_image_update_job_id = False
                shop.lazada_image_update_status = 'never'
                shop.lazada_image_update_date = False
                shop.lazada_image_update_message = ''
                
                shop.lazada_stock_sync_job_id = False
                shop.lazada_stock_sync_status = 'never'
                shop.lazada_stock_sync_date = False
                shop.lazada_stock_sync_message = ''
                
                # Standardize Backfill/Pull status for non-Lazada channels
                # - WooCommerce: use woocommerce_backfill_orders
                # - Shopee/TikTok: use generic pull_order job status
                if shop.channel == 'woocommerce':
                    job, status, when, message = get_job_data(shop.id, 'woocommerce_backfill_orders')
                    shop.lazada_order_backfill_job_id = job
                    shop.lazada_order_backfill_status = status
                    shop.lazada_order_backfill_date = when
                    shop.lazada_order_backfill_message = message
                elif shop.channel in ['shopee', 'tiktok']:
                    job, status, when, message = get_job_data(shop.id, 'pull_order')
                    shop.lazada_order_backfill_job_id = job
                    shop.lazada_order_backfill_status = status
                    shop.lazada_order_backfill_date = when
                    shop.lazada_order_backfill_message = message
                else:
                    shop.lazada_order_backfill_job_id = False
                    shop.lazada_order_backfill_status = 'never'
                    shop.lazada_order_backfill_date = False
                    shop.lazada_order_backfill_message = ''
                continue
            
            job, status, when, message = get_job_data(shop.id, 'lazada_import_products')
            shop.lazada_product_import_job_id = job
            shop.lazada_product_import_status = status
            shop.lazada_product_import_date = when
            shop.lazada_product_import_message = message
            
            job, status, when, message = get_job_data(shop.id, 'lazada_update_images')
            shop.lazada_image_update_job_id = job
            shop.lazada_image_update_status = status
            shop.lazada_image_update_date = when
            shop.lazada_image_update_message = message
            
            job, status, when, message = get_job_data(shop.id, 'lazada_push_stock')
            shop.lazada_stock_sync_job_id = job
            shop.lazada_stock_sync_status = status
            shop.lazada_stock_sync_date = when
            shop.lazada_stock_sync_message = message
            
            job, status, when, message = get_job_data(shop.id, 'lazada_backfill_orders')
            shop.lazada_order_backfill_job_id = job
            shop.lazada_order_backfill_status = status
            shop.lazada_order_backfill_date = when
            shop.lazada_order_backfill_message = message

    @api.constrains('external_shop_id', 'account_id')
    def _check_unique_shop(self):
        for shop in self:
            duplicate = self.search([
                ('external_shop_id', '=', shop.external_shop_id),
                ('account_id', '=', shop.account_id.id),
                ('id', '!=', shop.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    f'Shop with ID {shop.external_shop_id} already exists for this account'
                )

    def action_view_orders(self):
        """View orders for this shop"""
        self.ensure_one()
        return {
            'name': 'Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.order',
            'view_mode': 'list,form,kanban',
            'domain': [('shop_id', '=', self.id)],
            'context': {'default_shop_id': self.id},
        }

    def action_view_bindings(self):
        """View product bindings for this shop"""
        self.ensure_one()
        return {
            'name': 'Product Bindings',
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.product.binding',
            'view_mode': 'list,form',
            'domain': [('shop_id', '=', self.id)],
            'context': {'default_shop_id': self.id},
        }

    # Lazada dashboard buttons
    def action_open_lazada_import_wizard(self):
        self.ensure_one()
        return {
            'name': 'Import Lazada Products',
            'type': 'ir.actions.act_window',
            'res_model': 'lazada.import.products.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shop_id': self.id,
            },
        }

    def action_open_lazada_update_images_wizard(self):
        self.ensure_one()
        return {
            'name': 'Update Lazada Product Images',
            'type': 'ir.actions.act_window',
            'res_model': 'lazada.update.images.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shop_id': self.id,
            },
        }

    def action_open_lazada_push_stock_wizard(self):
        self.ensure_one()
        return {
            'name': 'Sync Stock to Lazada',
            'type': 'ir.actions.act_window',
            'res_model': 'lazada.push.stock.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shop_id': self.id,
            },
        }

    # LOCKED: Lazada backfill button behavior
    # - This action only opens the 'lazada.backfill.orders.wizard' in a modal
    # - Context must include 'default_shop_id' only; the wizard is responsible for
    #   validating input and creating the corresponding background job
    # - Do NOT modify return structure or context keys without coordinated changes
    #   in the wizard and job handlers
    def action_open_lazada_backfill_orders_wizard(self):
        self.ensure_one()
        return {
            'name': 'Import Lazada Orders (Backfill)',
            'type': 'ir.actions.act_window',
            'res_model': 'lazada.backfill.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shop_id': self.id,
            },
        }

    def action_open_woocommerce_backfill_orders_wizard(self):
        self.ensure_one()
        return {
            'name': 'Import WooCommerce Orders (Backfill)',
            'type': 'ir.actions.act_window',
            'res_model': 'woocommerce.backfill.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_shop_id': self.id,
            },
        }

    def action_open_shopee_backfill_orders_wizard(self):
        """Open Pull Orders Wizard for Shopee (backfill orders)"""
        self.ensure_one()
        return {
            'name': 'Pull Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'marketplace.pull.orders.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_account_id': self.account_id.id,
                'default_shop_id': self.id,
            },
        }

