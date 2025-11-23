# -*- coding: utf-8 -*-

from .adapters import MarketplaceAdapter
from odoo import fields
from datetime import datetime, timedelta, timezone
import base64
import time
import logging
import urllib.parse
import json
import hmac
import hashlib
import requests

_logger = logging.getLogger(__name__)

# LOCKED: Stable schema – ห้ามแก้ signature/logic ที่เป็นสัญญากับ client
class LazadaAdapter(MarketplaceAdapter):
    """Lazada marketplace adapter"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_redirect_uri(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        ) or ''
        callback_path = self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.lazada.callback_path',
            '/oauth/lazada/callback'
        ) or '/oauth/lazada/callback'
        if not callback_path.startswith('/'):
            callback_path = '/' + callback_path
        return base_url.rstrip('/') + callback_path

    def _get_auth_base_url(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.lazada.auth_base_url',
            'https://auth.lazada.com/rest'
        ).rstrip('/')

    def _sign_params(self, api_path, params):
        """Generate Lazada signature for given API path and parameters"""
        prepared = {
            key: self._prepare_value(value)
            for key, value in params.items()
            if value is not None
        }
        sorted_items = sorted(prepared.items(), key=lambda item: item[0])
        sign_base = api_path + ''.join(f"{key}{value}" for key, value in sorted_items)
        signature = hmac.new(
            (self.account.client_secret or '').encode('utf-8'),
            sign_base.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        return signature

    def _prepare_value(self, value):
        if value is None:
            return ''
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        return str(value)
    # LOCKED-REGION: ห้ามแก้ตรรกะนี้ ฟังก์ชันนี้เป็นตัวเตรียมลายเซ็น ใส่ access token และยิง requests.request(...) ไปยังปลายทาง /rest ของ Lazada ก่อนแปลงผลลัพธ์เป็น JSON 
    def _make_request(self, method, endpoint, params=None, data=None, files=None, include_access_token=True):
        """Signed request to Lazada REST API"""
        method = (method or 'GET').upper()
        api_path = endpoint if endpoint.startswith('/') else '/' + endpoint
        base_url = self._get_base_url().rstrip('/')
        url = f"{base_url}{api_path}"

        access_token = self._get_access_token() if include_access_token else None
        request_params = {
            'app_key': self.account.client_id,
            'sign_method': 'sha256',
            'timestamp': str(int(time.time() * 1000)),
        }
        if access_token:
            request_params['access_token'] = access_token
        if params:
            request_params.update({k: v for k, v in params.items() if v is not None})

        payload = {}
        if data:
            payload = {k: v for k, v in data.items() if v is not None}

        sign_entries = dict(request_params)
        sign_entries.update(payload)
        request_params['sign'] = self._sign_params(api_path, sign_entries)

        headers = {}
        request_data = None
        if method != 'GET' and payload:
            # Lazada expects form-urlencoded for most write APIs
            request_data = {
                key: self._prepare_value(value)
                for key, value in payload.items()
            }
            headers['Content-Type'] = 'application/x-www-form-urlencoded'

        response = requests.request(
            method,
            url,
            params=request_params,
            data=request_data,
            files=files,
            timeout=self.timeout,
        )
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            raise ValueError(f'Lazada API returned non-JSON response: {response.text[:200]}')

        if isinstance(result, dict):
            code = result.get('code')
            if code and str(code) not in ['0', '200', 'SUCCESS']:
                message = result.get('message') or result.get('detail') or result.get('msg') or 'Unknown error'
                raise ValueError(f'Lazada API error ({code}): {message}')

        return result
    # END-LOCKED
    # LOCKED-REGION: base ประเทศไทย
    def _get_base_url(self):
        """Get Lazada API base URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.lazada.base_url',
            'https://api.lazada.co.th/rest'
        )
        return base_url
    
    # ------------------------------------------------------------------
    # OAuth helpers
    # ------------------------------------------------------------------

    def get_authorize_url(self):
        """Get Lazada OAuth authorization URL"""
        redirect_uri = self._get_redirect_uri()

        params = {
            'response_type': 'code',
            'client_id': self.account.client_id,
            'redirect_uri': redirect_uri,
            'force_auth': 'true',
        }

        auth_url = 'https://auth.lazada.com/oauth/authorize'
        auth_url += '?' + urllib.parse.urlencode(params)

        return auth_url

    def exchange_code(self, code, shop_id=None):
        """Exchange authorization code for tokens"""
        _logger.info('🔍 Lazyda Token Exchange - starting token exchange')
        redirect_uri = self._get_redirect_uri()

        code_str = (code or '').strip()
        if not code_str:
            raise ValueError('Missing authorization code from Lazada callback.')

        request_params = {
            'app_key': self.account.client_id,
            'sign_method': 'sha256',
            'timestamp': str(int(time.time() * 1000)),
            'code': code_str,
        }
        if redirect_uri:
            request_params['redirect_uri'] = redirect_uri

        sorted_items = sorted(request_params.items(), key=lambda item: item[0])
        sign_source_str = ''.join(f"{key}{value}" for key, value in sorted_items)
        sign_base = f"/auth/token/create{sign_source_str}"
        _logger.debug('Lazada OAuth Sign Base: %s', sign_base)
        signature = hmac.new(
            (self.account.client_secret or '').encode('utf-8'),
            sign_base.encode('utf-8'),
            hashlib.sha256
        ).hexdigest().upper()
        request_params['sign'] = signature

        token_url = f"{self._get_auth_base_url()}/auth/token/create"

        try:
            response = requests.get(
                token_url,
                params=request_params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if 'error' in result or 'error_description' in result:
                error_msg = result.get('error', 'Unknown error')
                error_description = result.get('error_description', '')
                raise ValueError(f'Lazada API error: {error_msg}, Description: {error_description}')

            access_token = result.get('access_token') or result.get('accessToken')
            refresh_token = result.get('refresh_token') or result.get('refreshToken')
            expires_in = result.get('expires_in') or result.get('expiresIn', 3600)

            if not access_token:
                raise ValueError(f'No access_token received from Lazada API. Response: {result}')

            return {
                'access_token': access_token,
                'refresh_token': refresh_token,
                'expires_in': expires_in,
            }

        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise ValueError(f'Failed to exchange code for tokens: {str(e)}, Error Detail: {error_detail}')

    def refresh_access_token(self):
        """Refresh Lazada access token"""
        refresh_token = (self.account.refresh_token or '').strip()
        if not refresh_token:
            raise ValueError('Missing refresh token for Lazada account')

        api_path = '/auth/token/refresh'
        params = {
            'app_key': self.account.client_id,
            'refresh_token': refresh_token,
            'sign_method': 'sha256',
            'timestamp': str(int(time.time() * 1000)),
        }
        params['sign'] = self._sign_params(api_path, params)

        token_url = f"{self._get_auth_base_url()}{api_path}"
        try:
            response = requests.get(
                token_url,
                params=params,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            if 'error' in result or 'error_description' in result:
                error_msg = result.get('error', 'Unknown error')
                error_description = result.get('error_description', '')
                raise ValueError(f'Lazada API error: {error_msg}, Description: {error_description}')

            return {
                'access_token': result.get('access_token'),
                'refresh_token': result.get('refresh_token', refresh_token),
                'expires_in': result.get('expires_in', 3600),
            }
        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                except Exception:
                    error_detail = e.response.text
            raise ValueError(f'Failed to refresh token: {str(e)}, Detail: {error_detail}')
    
    def get_seller_info(self):
        """Fetch seller/shop information for the connected Lazada account"""
        try:
            response = self._make_request('GET', '/seller/get')
            if isinstance(response, dict):
                # Lazada typically wraps payload inside 'data'
                return response.get('data') or response
            return response or {}
        except Exception as e:
            _logger.warning(f'Failed to fetch Lazada seller info: {e}')
            return {}
    
    def get_shop_info(self, shop_id=None):
        """Return shop information payload (compatibility helper)"""
        info = self.get_seller_info()
        if info and shop_id and not info.get('shop_id'):
            info = dict(info)
            info['shop_id'] = shop_id
        return info
    # END-LOCKED
    # ------------------------------------------------------------------
    # Product helpers
    # ------------------------------------------------------------------

    def fetch_products(self, offset=0, limit=50, status=None):
        limit = max(1, min(int(limit or 50), 50))
        params = {
            'offset': offset,
            'limit': limit,
        }
        if status:
            params['filter'] = status
        response = self._make_request('GET', '/products/get', params=params)
        data = response.get('data') or {}
        products = data.get('products') or data.get('product') or []
        total = data.get('total_products') or data.get('total') or len(products)
        return products, int(total)

    def fetch_all_products(self, status=None):
        all_products = []
        offset = 0
        limit = 100
        total = None

        while True:
            batch, total_count = self.fetch_products(offset=offset, limit=limit, status=status)
            if not batch:
                break
            all_products.extend(batch)
            offset += len(batch)
            total = total_count
            if total is not None and offset >= total:
                break

        return all_products

    def extract_sku_info(self, product):
        info_list = []
        product_name = product.get('attributes', {}).get('name') or product.get('name') or ''
        item_id = product.get('item_id') or product.get('itemId') or product.get('itemIdString')
        product_images = product.get('images') or product.get('image') or []

        sku_rows = product.get('skus') or product.get('Sku') or []
        for sku in sku_rows:
            seller_sku = (
                sku.get('SellerSku') or
                sku.get('sellerSku') or
                sku.get('Sku') or
                sku.get('sku')
            )
            if not seller_sku:
                continue
            sku_images = sku.get('Images') or sku.get('images') or product_images
            quantity = sku.get('Available') or sku.get('available') or sku.get('quantity')
            status = sku.get('Status') or sku.get('status') or product.get('status', 'active')

            info_list.append({
                'seller_sku': seller_sku.strip(),
                'shop_sku': sku.get('ShopSku') or sku.get('shopSku'),
                'item_id': sku.get('ItemId') or sku.get('itemId') or item_id,
                'sku_id': sku.get('SkuId') or sku.get('skuId'),
                'name': sku.get('Name') or sku.get('name') or product_name,
                'product_name': product_name,
                'images': sku_images,
                'quantity': quantity,
                'is_active': str(status).lower() not in ['inactive', 'deleted'],
            })

        return info_list

    def get_sku_image_map(self, products):
        sku_map = {}
        for product in products:
            for info in self.extract_sku_info(product):
                images = info.get('images') or []
                if images:
                    sku_map[info['seller_sku']] = images
        return sku_map

    def download_image(self, url):
        if not url:
            return False
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return base64.b64encode(response.content)
        except Exception as e:
            _logger.error(f'Failed to download image {url}: {e}', exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Orders / Inventory
    # ------------------------------------------------------------------
    # LOCKED: STABLE API – ถ้าจะแก้ ต้องเพิ่ม deprecation note ก่อน
    # เพิ่มความสามารถเลือกฟิลด์เวลา (created|updated) และทำ fallback อัตโนมัติเมื่อไม่พบข้อมูล
    # พารามิเตอร์ใหม่เป็น backward‑compatible: caller เดิมไม่ต้องแก้ (ค่าเริ่มต้นคือ created)
    def fetch_orders(self, since, until=None, time_field: str = "created", fallback_to_updated: bool = True):
        if not self.shop:
            raise ValueError('Shop is required for fetching orders')

        if isinstance(since, str):
            since = datetime.fromisoformat(since)
        if until is None:
            until = datetime.now()
        elif isinstance(until, str):
            until = datetime.fromisoformat(until)

        def _fmt_with_tz(dt: datetime) -> str:
            """Format datetime with explicit timezone offset (+HH:MM) as Lazada expects."""
            # ใช้โซนเวลาไทยเป็นค่าเริ่มต้น หากไม่มี tz ให้ผูก +07:00 เพื่อให้ได้รูปแบบ ISO8601 มี offset
            try:
                tz = timezone(timedelta(hours=7))
            except Exception:
                from datetime import timezone as _tz, timedelta as _td
                tz = _tz(_td(hours=7))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            # isoformat() จะให้แบบ YYYY-MM-DDTHH:MM:SS+07:00
            return dt.isoformat(timespec='seconds')

        def _build_params(tf: str):
            """
            tf: 'created' or 'updated'
            Lazada บางเอกสารใช้ชื่อคีย์ update_after/created_after (snake_case)
            และบางที่อาจใช้ CamelCase (UpdatedAfter/CreatedAfter) — เราจึงใส่ให้ครบทั้งสองแบบ
            หมายเหตุ: เอกสารระบุว่าอย่างน้อยต้องมี *After* อย่างใดอย่างหนึ่งเสมอ
            """
            base = 'update' if tf == 'updated' else 'created'
            # รูปแบบ snake_case ตามเอกสาร
            after_snake = f'{base}_after'    # e.g. update_after / created_after
            before_snake = f'{base}_before'  # e.g. update_before / created_before
            # รูปแบบ snake_case เดิม (เผื่อบาง cluster ยอมรับ updated_after)
            alt_base = f'{tf}'               # e.g. updated / created
            after_snake_alt = f'{alt_base}_after'
            before_snake_alt = f'{alt_base}_before'
            # รูปแบบ CamelCase (กันกรณี API ต้องการ)
            after_cc = f'{base.capitalize()}After'    # UpdateAfter / CreatedAfter
            before_cc = f'{base.capitalize()}Before'  # UpdateBefore / CreatedBefore

            val_after = _fmt_with_tz(since)
            val_before = _fmt_with_tz(until)
            p = {
                after_snake:      val_after,
                before_snake:     val_before,
                after_snake_alt:  val_after,
                before_snake_alt: val_before,
                after_cc:         val_after,
                before_cc:        val_before,
                'limit': 100,
                'offset': 0,
            }
            # แนะนำให้ส่ง sort_by และ sort_direction ให้สอดคล้องกับฟิลด์เวลา
            p['sort_by'] = f'{tf}_at'  # 'created_at' หรือ 'updated_at'
            p['sort_direction'] = 'DESC'
            return p

        params = _build_params(time_field if time_field in ("created", "updated") else "created")

        all_orders = []
        offset = 0
        while True:
            params['offset'] = offset
            # Debug visibility for cron diagnostics
            _logger.warning(
                "🛰️  Lazada fetch_orders(%s): GET /orders/get shop=%s window=%s..%s offset=%s limit=%s",
                time_field,
                getattr(self.shop, 'name', self.shop),
                params.get('created_after') or params.get('updated_after'),
                params.get('created_before') or params.get('updated_before'),
                offset,
                params['limit'],
            )
            response = self._make_request('GET', '/orders/get', params=params)
            orders = response.get('data', {}).get('orders', [])
            _logger.warning(
                "📦 Lazada fetch_orders(%s): got %s orders at offset %s",
                time_field,
                len(orders),
                offset,
            )
            if not orders:
                break
            for order in orders:
                order_id = (
                    order.get('order_id')
                    or order.get('OrderId')
                    or order.get('order_number')
                    or order.get('OrderNumber')
                )
                if order_id:
                    try:
                        items_response = self._make_request(
                            'GET',
                            '/order/items/get',
                            params={'order_id': order_id},
                        )
                        if isinstance(items_response, dict):
                            items_data = items_response.get('data', items_response)
                        else:
                            items_data = items_response
                        if isinstance(items_data, list):
                            order_items = items_data
                        else:
                            order_items = (
                                items_data.get('order_items')
                                or items_data.get('OrderItems')
                                or []
                            )
                        if not order_items:
                            # Some responses use camelCase keys
                            order_items = items_data.get('items') or items_data.get('Items') or []
                        order['order_items'] = order_items
                    except Exception as item_error:
                        _logger.warning('Failed to fetch Lazada order items for %s: %s', order_id, item_error)
                        order['order_items'] = []
                else:
                    order['order_items'] = []

            all_orders.extend(orders)
            # Log a small sample of order ids for traceability
            try:
                sample_ids = [o.get('order_id') or o.get('OrderId') or o.get('order_number') or o.get('OrderNumber') for o in orders][:5]
                _logger.warning("🔎 Lazada fetch_orders(%s): sample order_ids (offset %s): %s", time_field, offset, sample_ids)
            except Exception:
                pass
            if len(orders) < params['limit']:
                break
            offset += len(orders)

        _logger.warning("✅ Lazada fetch_orders(%s): total orders fetched=%s", time_field, len(all_orders))

        # Fallback: ถ้าใช้ created แล้วไม่พบข้อมูล ให้ลองดึงด้วย updated ภายใน window เดียวกัน
        if not all_orders and fallback_to_updated and time_field == "created":
            _logger.warning("↪️  Lazada fetch_orders: no orders with created window; retrying with updated window")
            return self.fetch_orders(since, until, time_field="updated", fallback_to_updated=False)

        return all_orders

    def update_inventory(self, items):
        if not self.shop:
            raise ValueError('Shop is required for updating inventory')

        payload_items = []
        for sku, qty in items:
            payload_items.append({
                'seller_sku': sku,
                'quantity': int(qty),
            })

        payload_json = json.dumps(payload_items, ensure_ascii=False)
        data = {'payload': payload_json}

        try:
            response = self._make_request(
                'POST',
                '/product/stock/sellable/update',
                data=data,
            )
        except Exception as primary_error:
            _logger.warning('Sellable stock update failed (%s). Falling back to legacy endpoint.', primary_error)
            legacy_data = {
                'Skus': json.dumps([
                    {'SellerSku': sku, 'Quantity': int(qty)}
                    for sku, qty in items
                ], ensure_ascii=False, separators=(',', ':')),
            }
            response = self._make_request(
                'POST',
                '/product/update_quantity',
                data=legacy_data,
            )

        results = {}
        data_section = response.get('data') or {}
        detail = data_section.get('detail')

        if isinstance(detail, list):
            for item in detail:
                sku = item.get('seller_sku') or item.get('SellerSku') or ''
                results[sku] = {
                    'success': bool(item.get('success')),
                    'error': item.get('message') or item.get('error', ''),
                }
        else:
            for item in data_section.get('skus', []):
                sku = item.get('SellerSku', '')
                results[sku] = {
                    'success': item.get('Success', False),
                    'error': item.get('Message', ''),
                }

        return results

    def verify_webhook(self, headers, body):
        signature = headers.get('Authorization', '')
        if not signature:
            return False
        return True

    def parse_order_payload(self, payload):
        payload = payload or {}

        def _get_value(data, *keys, default=''):
            for key in keys:
                if key in data:
                    return data[key]
                key_lower = key.lower()
                for existing_key in data:
                    if existing_key.lower() == key_lower:
                        return data[existing_key]
            return default

        order_id = _get_value(payload, 'order_id', 'OrderId', 'order_number', 'OrderNumber')
        name = _get_value(payload, 'name', 'Name')
        if not name:
            name = f'LAZ-{order_id}' if order_id else 'LAZ-UNKNOWN'

        # Status handling
        order_status = ''
        statuses = _get_value(payload, 'statuses', 'Statuses', default=[])
        if isinstance(statuses, list) and statuses:
            status_item = statuses[0]
            if isinstance(status_item, dict):
                order_status = status_item.get('status') or status_item.get('Status') or ''
            elif isinstance(status_item, str):
                order_status = status_item
        else:
            order_status = _get_value(payload, 'status', 'Status', default='')

        status_map = {
            'pending': 'pending',
            'ready_to_ship': 'pending',
            'ready_to_ship_3pl': 'pending',
            'ready_to_ship_xd': 'pending',
            'packed': 'pending',
            'shipped': 'synced',
            'delivered': 'synced',
            'delivered_partial': 'synced',
            'completed': 'synced',
            'canceled': 'cancelled',
            'canceled_by_customer': 'cancelled',
            'returned': 'returned',
            'failed_delivery': 'returned',
        }
        state = status_map.get((order_status or '').lower(), 'pending')

        address_info = _get_value(payload, 'address_shipping', 'AddressShipping', default={}) or {}
        customer_first_name = _get_value(address_info, 'first_name', 'FirstName')
        customer_last_name = _get_value(address_info, 'last_name', 'LastName')
        customer_name = (f"{customer_first_name} {customer_last_name}").strip()
        if not customer_name:
            customer_name = _get_value(payload, 'customer_name', 'CustomerName', default='Lazada Customer')

        customer_phone = _get_value(address_info, 'phone', 'Phone')
        customer_email = _get_value(payload, 'customer_email', 'CustomerEmail')

        customer_address = ' '.join(filter(None, [
            _get_value(address_info, 'address1', 'Address1'),
            _get_value(address_info, 'address2', 'Address2'),
            _get_value(address_info, 'address3', 'Address3'),
            _get_value(address_info, 'city', 'City'),
            _get_value(address_info, 'post_code', 'PostCode'),
            _get_value(address_info, 'country', 'Country'),
        ])).strip()

        order_items = _get_value(payload, 'order_items', 'OrderItems', default=[]) or []
        lines = []
        for item in order_items:
            quantity = item.get('quantity') or item.get('Quantity') or 1
            price_unit = (
                item.get('item_price') or item.get('ItemPrice')
                or item.get('paid_price') or item.get('PaidPrice') or 0
            )
            external_sku = (
                item.get('seller_sku') or item.get('SellerSku')
                or item.get('sku') or item.get('Sku') or ''
            )
            product_name = item.get('name') or item.get('Name') or external_sku
            lines.append({
                'external_sku': external_sku,
                'product_name': product_name,
                'quantity': float(quantity or 1),
                'price_unit': float(price_unit or 0),
            })

        order_date_str = (
            _get_value(payload, 'created_at', 'CreatedAt')
            or _get_value(payload, 'created_time', 'CreatedTime')
        )
        if order_date_str:
            order_date = fields.Datetime.now()
            parsed = None
            for fmt in (
                '%Y-%m-%d %H:%M:%S %z',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%S%z',
                '%Y-%m-%dT%H:%M:%S',
            ):
                try:
                    parsed = datetime.strptime(order_date_str, fmt)
                    break
                except Exception:
                    continue
            if not parsed:
                try:
                    parsed = fields.Datetime.from_string(order_date_str)
                except Exception:
                    parsed = fields.Datetime.now()
            if isinstance(parsed, datetime) and parsed.tzinfo:
                order_date = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                order_date = parsed or fields.Datetime.now()
        else:
            order_date = fields.Datetime.now()

        amount_total = _get_value(payload, 'price', 'Price', default=0)
        try:
            amount_total = float(amount_total or 0)
        except Exception:
            amount_total = 0.0

        currency_code = _get_value(payload, 'currency', 'Currency')
        currency_id = False
        if currency_code:
            currency = self.env['res.currency'].sudo().search([('name', '=', currency_code)], limit=1)
            if currency:
                currency_id = currency.id

        return {
            'external_order_id': str(order_id) if order_id else name,
            'name': name,
            'order_date': order_date,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
            'amount_total': amount_total,
            'currency_id': currency_id or False,
            'state': state,
            'lines': lines,
        }


# Register adapter
from . import adapters
adapters.MarketplaceAdapters.register_adapter('lazada', LazadaAdapter)
