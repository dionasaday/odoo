# -*- coding: utf-8 -*-

from .adapters import MarketplaceAdapter
from odoo import fields
from datetime import datetime, timedelta
import logging
import urllib.parse
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class TikTokAdapter(MarketplaceAdapter):
    """TikTok Shop marketplace adapter"""
    
    def _get_base_url(self):
        """Get TikTok API base URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.tiktok.base_url',
            'https://open-api.tiktokglobalshop.com'
        )
        return base_url
    
    def get_authorize_url(self):
        """Get TikTok OAuth authorization URL"""
        redirect_uri = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        ) + '/marketplace/oauth/callback/tiktok'
        
        params = {
            'app_key': self.account.client_id,
            'redirect_uri': redirect_uri,
            'state': 'marketplace_auth',
        }
        
        auth_url = 'https://auth.tiktok-shops.com/oauth/authorize'
        auth_url += '?' + urllib.parse.urlencode(params)
        
        return auth_url
    
    def exchange_code(self, code):
        """Exchange authorization code for tokens"""
        data = {
            'app_key': self.account.client_id,
            'app_secret': self.account.client_secret,
            'auth_code': code,
            'grant_type': 'authorized_code',
        }
        
        response = self._make_request(
            'POST',
            '/api/token/get',
            data=data,
        )
        
        return {
            'access_token': response.get('data', {}).get('access_token'),
            'refresh_token': response.get('data', {}).get('refresh_token'),
            'expires_in': response.get('data', {}).get('expires_in', 3600),
        }
    
    def refresh_access_token(self):
        """Refresh TikTok access token"""
        data = {
            'app_key': self.account.client_id,
            'app_secret': self.account.client_secret,
            'refresh_token': self.account.refresh_token,
            'grant_type': 'refresh_token',
        }
        
        response = self._make_request(
            'POST',
            '/api/token/refresh',
            data=data,
        )
        
        return {
            'access_token': response.get('data', {}).get('access_token'),
            'refresh_token': response.get('data', {}).get('refresh_token', self.account.refresh_token),
            'expires_in': response.get('data', {}).get('expires_in', 3600),
        }
    
    def fetch_orders(self, since, until=None):
        """Fetch orders from TikTok"""
        if not self.shop:
            raise ValueError('Shop is required for fetching orders')
        
        # Convert datetime if needed
        if isinstance(since, str):
            since = datetime.fromisoformat(since)
        if until is None:
            until = datetime.now()
        elif isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        params = {
            'create_time_from': int(since.timestamp()),
            'create_time_to': int(until.timestamp()),
            'page_size': 100,
            'cursor': '',
        }
        
        all_orders = []
        cursor = ''
        
        while True:
            if cursor:
                params['cursor'] = cursor
            
            response = self._make_request(
                'GET',
                '/order/orders/search',
                params=params,
            )
            
            orders = response.get('data', {}).get('order_list', [])
            if not orders:
                break
            
            all_orders.extend(orders)
            
            cursor = response.get('data', {}).get('next_cursor')
            if not cursor:
                break
        
        return all_orders
    
    def update_inventory(self, items):
        """Update inventory on TikTok"""
        if not self.shop:
            raise ValueError('Shop is required for updating inventory')
        
        # TikTok batch update
        sku_list = []
        for sku, qty in items:
            sku_list.append({
                'seller_sku': sku,
                'available_stock': int(qty),
            })
        
        data = {
            'sku_list': sku_list,
        }
        
        response = self._make_request(
            'POST',
            '/product/inventory/update',
            data=data,
        )
        
        results = {}
        for item in response.get('data', {}).get('failed_sku_list', []):
            results[item.get('seller_sku')] = {
                'success': False,
                'error': item.get('fail_reason', ''),
            }
        
        # Success items
        for item in response.get('data', {}).get('success_sku_list', []):
            results[item.get('seller_sku')] = {
                'success': True,
            }
        
        return results
    
    def verify_webhook(self, headers, body):
        """Verify TikTok webhook signature"""
        signature = headers.get('X-TikTok-Signature', '')
        if not signature:
            return False
        
        # TikTok uses HMAC-SHA256
        secret = self.account.client_secret or ''
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body.encode('utf-8') if isinstance(body, str) else body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def parse_order_payload(self, payload):
        """Parse TikTok order payload to standard format"""
        order_id = payload.get('order_id', '')
        order_status = payload.get('order_status', '')
        
        status_map = {
            'UNPAID': 'pending',
            'AWAITING_SHIPMENT': 'pending',
            'AWAITING_COLLECTION': 'pending',
            'IN_TRANSIT': 'synced',
            'DELIVERED': 'synced',
            'COMPLETED': 'synced',
            'CANCELLED': 'cancelled',
            'RETURNED': 'returned',
        }
        
        state = status_map.get(order_status, 'pending')
        
        # Parse customer info
        recipient = payload.get('recipient', {})
        customer_name = recipient.get('name', '')
        customer_phone = recipient.get('phone_number', '')
        address = recipient.get('full_address', {})
        customer_address = f"{address.get('address_line1', '')} {address.get('address_line2', '')} {address.get('city', '')} {address.get('region', '')} {address.get('postal_code', '')}"
        
        # Parse order lines
        lines = []
        for item in payload.get('item_list', []):
            lines.append({
                'external_sku': item.get('seller_sku', ''),
                'product_name': item.get('product_name', ''),
                'quantity': float(item.get('quantity', 1)),
                'price_unit': float(item.get('price', {}).get('original_price', 0)),
            })
        
        return {
            'external_order_id': order_id,
            'name': f'TIK-{order_id}',
            'order_date': datetime.fromtimestamp(payload.get('create_time', 0)),
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_address': customer_address.strip(),
            'amount_total': float(payload.get('payment_info', {}).get('total_amount', 0)),
            'state': state,
            'lines': lines,
        }

