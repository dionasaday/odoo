# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import timedelta


class LazadaImportProductsWizard(models.TransientModel):
    _name = 'lazada.import.products.wizard'
    _description = 'Import products from Lazada'

    shop_id = fields.Many2one('marketplace.shop', string='Shop', required=True, readonly=True)
    confirm_text = fields.Char(string="Type 'confirm' to continue", required=True)

    def action_confirm(self):
        self.ensure_one()
        if (self.confirm_text or '').strip().lower() != 'confirm':
            raise UserError("Please type 'confirm' to continue.")

        shop = self.shop_id
        job = self.env['marketplace.job'].sudo().create({
            'name': f'Import products from Lazada - {shop.name}',
            'job_type': 'lazada_import_products',
            'account_id': shop.account_id.id,
            'shop_id': shop.id,
            'payload': {},
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
        })

        message = (
            f"📦 Scheduled Lazada product import job #{job.id} for shop <b>{shop.name}</b>."
            "<br/>Job will run shortly via the marketplace job queue."
        )
        shop.message_post(body=message, subtype_xmlid='mail.mt_note')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Lazada product import job #{job.id} has been created.',
                'type': 'success',
                'sticky': False,
            },
        }


class LazadaUpdateImagesWizard(models.TransientModel):
    _name = 'lazada.update.images.wizard'
    _description = 'Update Lazada product images'

    shop_id = fields.Many2one('marketplace.shop', string='Shop', required=True, readonly=True)
    confirm_text = fields.Char(string="Type 'confirm' to continue", required=True)
    update_existing_images = fields.Boolean(
        string='Update existing images in Odoo',
        default=False,
        help='If enabled, existing product images in Odoo will be replaced with Lazada images.'
    )

    def action_confirm(self):
        self.ensure_one()
        if (self.confirm_text or '').strip().lower() != 'confirm':
            raise UserError("Please type 'confirm' to continue.")

        shop = self.shop_id
        payload = {
            'update_existing_images': self.update_existing_images,
        }
        job = self.env['marketplace.job'].sudo().create({
            'name': f'Update images from Lazada - {shop.name}',
            'job_type': 'lazada_update_images',
            'account_id': shop.account_id.id,
            'shop_id': shop.id,
            'payload': payload,
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
        })

        message = (
            f"🖼️ Scheduled Lazada image update job #{job.id} for shop <b>{shop.name}</b>."
            "<br/>Job will run shortly via the marketplace job queue."
        )
        shop.message_post(body=message, subtype_xmlid='mail.mt_note')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Lazada image update job #{job.id} has been created.',
                'type': 'success',
                'sticky': False,
            },
        }


class LazadaPushStockWizard(models.TransientModel):
    _name = 'lazada.push.stock.wizard'
    _description = 'Push stock to Lazada'

    shop_id = fields.Many2one('marketplace.shop', string='Shop', required=True, readonly=True)
    confirm_text = fields.Char(string="Type 'confirm' to continue", required=True)

    def action_confirm(self):
        self.ensure_one()
        if (self.confirm_text or '').strip().lower() != 'confirm':
            raise UserError("Please type 'confirm' to continue.")

        shop = self.shop_id
        job = self.env['marketplace.job'].sudo().create({
            'name': f'Sync stock to Lazada - {shop.name}',
            'job_type': 'lazada_push_stock',
            'account_id': shop.account_id.id,
            'shop_id': shop.id,
            'payload': {},
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
        })

        message = (
            f"📦 Scheduled Lazada stock sync job #{job.id} for shop <b>{shop.name}</b>."
            "<br/>Job will run shortly via the marketplace job queue."
        )
        shop.message_post(body=message, subtype_xmlid='mail.mt_note')

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Job Created',
                'message': f'Lazada stock sync job #{job.id} has been created.',
                'type': 'success',
                'sticky': False,
            },
        }


class LazadaBackfillOrdersWizard(models.TransientModel):
    _name = 'lazada.backfill.orders.wizard'
    _description = 'Backfill Lazada orders by date'

    shop_id = fields.Many2one('marketplace.shop', string='Shop', required=True, readonly=True)
    sync_date = fields.Date(string='Order Date', required=True)
    confirm_text = fields.Char(string="Type 'confirm' to continue", required=True)

    def action_confirm(self):
        self.ensure_one()
        if (self.confirm_text or '').strip().lower() != 'confirm':
            raise UserError("Please type 'confirm' to continue.")

        shop = self.shop_id
        sync_date = self.sync_date or fields.Date.context_today(self)
        sync_date_str = fields.Date.to_string(sync_date)
        start_dt = fields.Datetime.from_string(f"{sync_date_str} 00:00:00")
        end_dt = fields.Datetime.now()

        payload = {
            'sync_date': sync_date_str,
            'start_datetime': fields.Datetime.to_string(start_dt),
            'end_datetime': fields.Datetime.to_string(end_dt),
        }
        job = self.env['marketplace.job'].sudo().create({
            'name': f'Import Lazada orders ({self.sync_date}) - {shop.name}',
            'job_type': 'lazada_backfill_orders',
            'account_id': shop.account_id.id,
            'shop_id': shop.id,
            'payload': payload,
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
        })

        message = (
            f"🧾 Scheduled Lazada order backfill job #{job.id} for shop <b>{shop.name}</b>."
            f"<br/>Target date: {self.sync_date}."
        )
        shop.message_post(body=message, subtype_xmlid='mail.mt_note')

        try:
            self.env.user.notify_success(message=f'Lazada order backfill job #{job.id} has been created.')
        except Exception:
            pass

        return {'type': 'ir.actions.act_window_close'}


class WooCommerceBackfillOrdersWizard(models.TransientModel):
    _name = 'woocommerce.backfill.orders.wizard'
    _description = 'Backfill WooCommerce orders by date'

    shop_id = fields.Many2one('marketplace.shop', string='Shop', required=True, readonly=True)
    sync_date = fields.Date(string='Order Date', required=True)
    confirm_text = fields.Char(string="Type 'confirm' to continue", required=True)

    def action_confirm(self):
        self.ensure_one()
        if (self.confirm_text or '').strip().lower() != 'confirm':
            raise UserError("Please type 'confirm' to continue.")

        shop = self.shop_id
        if shop.account_id.channel != 'woocommerce':
            raise UserError('WooCommerce order backfill is only available for WooCommerce shops.')

        sync_date = self.sync_date or fields.Date.context_today(self)
        sync_date_str = fields.Date.to_string(sync_date)
        start_dt = fields.Datetime.from_string(f"{sync_date_str} 00:00:00")
        end_dt = start_dt + timedelta(days=1)

        payload = {
            'sync_date': sync_date_str,
            'start_datetime': fields.Datetime.to_string(start_dt),
            'end_datetime': fields.Datetime.to_string(end_dt),
        }

        job = self.env['marketplace.job'].sudo().create({
            'name': f'Import WooCommerce orders ({sync_date}) - {shop.name}',
            'job_type': 'woocommerce_backfill_orders',
            'account_id': shop.account_id.id,
            'shop_id': shop.id,
            'payload': payload,
            'state': 'pending',
            'next_run_at': fields.Datetime.now(),
        })

        message = (
            f"🧾 Scheduled WooCommerce order backfill job #{job.id} for shop <b>{shop.name}</b>."
            f"<br/>Target date: {sync_date}."
        )
        shop.message_post(body=message, subtype_xmlid='mail.mt_note')

        try:
            self.env.user.notify_success(message=f'WooCommerce order backfill job #{job.id} has been created.')
        except Exception:
            pass

        return {'type': 'ir.actions.act_window_close'}


