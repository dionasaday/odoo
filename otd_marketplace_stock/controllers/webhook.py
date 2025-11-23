# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
import logging
import json

_logger = logging.getLogger(__name__)


class MarketplaceWebhook(http.Controller):
    
    @http.route('/marketplace/webhook/<string:channel>/<string:shop_id>', 
                type='json', auth='public', methods=['POST'], csrf=False)
    def webhook(self, channel, shop_id, **kwargs):
        """Handle webhook from marketplace"""
        try:
            # Get raw payload
            payload = request.httprequest.data
            headers = dict(request.httprequest.headers)
            
            # Find shop
            shop = request.env['marketplace.shop'].sudo().search([
                ('external_shop_id', '=', shop_id),
                ('channel', '=', channel),
            ], limit=1)
            
            if not shop:
                _logger.warning(f'Shop not found: {channel}/{shop_id}')
                return {"ok": False, "error": "shop not found"}
            
            account = shop.account_id
            
            # Verify webhook signature
            adapter = account._get_adapter(shop)
            if not adapter.verify_webhook(headers, payload):
                _logger.warning(f'Invalid webhook signature: {channel}/{shop_id}')
                return {"ok": False, "error": "invalid signature"}
            
            # Parse payload
            try:
                if isinstance(payload, bytes):
                    payload_str = payload.decode('utf-8')
                else:
                    payload_str = payload
                webhook_data = json.loads(payload_str)
            except json.JSONDecodeError:
                webhook_data = {'raw': payload_str}
            
            # Queue webhook processing job
            request.env['marketplace.job'].sudo().create({
                'name': f'Process webhook {channel}/{shop_id}',
                'job_type': 'webhook',
                'shop_id': shop.id,
                'account_id': account.id,
                'payload': {
                    'channel': channel,
                    'shop_id': shop_id,
                    'webhook': webhook_data,
                    'event_type': webhook_data.get('event_type', ''),
                },
            })
            
            return {"ok": True, "message": "webhook queued"}
            
        except Exception as e:
            _logger.error(f'Webhook error: {e}', exc_info=True)
            return {"ok": False, "error": str(e)}

