# -*- coding: utf-8 -*-

from .adapters import MarketplaceAdapter
from odoo import fields
from datetime import datetime, timedelta
import logging
import requests
import base64
from urllib.parse import urljoin

_logger = logging.getLogger(__name__)

# LOCKED: Stable schema – ห้ามแก้ signature/logic ที่เป็นสัญญากับ client
class WooCommerceAdapter(MarketplaceAdapter):
    """WooCommerce marketplace adapter using REST API"""
    
    def _get_base_url(self):
        """Get WooCommerce API base URL"""
        # WooCommerce REST API base URL format: https://yourstore.com/wp-json/wc/v3/
        # Store URL is stored in client_id field
        # Note: For WooCommerce, Client ID field should contain the store URL (e.g., https://yourstore.com)
        store_url = self.account.client_id or ''
        if not store_url:
            raise ValueError(
                'Store URL is required for WooCommerce. '
                'Please enter your WooCommerce store URL (e.g., https://yourstore.com) in the Client ID field.'
            )
        
        # Remove trailing slash if present, then add wp-json path
        store_url = store_url.rstrip('/')
        
        # WooCommerce REST API endpoint
        api_url = urljoin(store_url + '/', 'wp-json/wc/v3/')
        return api_url
    
    def _get_auth(self):
        """Get Basic Auth credentials for WooCommerce API"""
        # WooCommerce uses Consumer Key:Consumer Secret for Basic Auth
        # Note: For WooCommerce:
        # - Client ID field = Store URL (used for base URL)
        # - Client Secret field = Consumer Secret (used for authentication)
        # - woocommerce_consumer_key field = Consumer Key (used for authentication)
        
        # Get Consumer Key from account field (preferred) or fallback to system parameter
        consumer_key = self.account.woocommerce_consumer_key
        
        if not consumer_key:
            # Fallback to system parameter (for backward compatibility)
            consumer_key = self.env['ir.config_parameter'].sudo().get_param(
                'marketplace.woocommerce.consumer_key'
            )
        
        if not consumer_key:
            # Last fallback: use client_secret (may not work, but better than error)
            _logger.warning(
                'Consumer Key not found. Please set Consumer Key in account settings. '
                'Using Client Secret as fallback (may not work).'
            )
            consumer_key = self.account.client_secret
        
        consumer_secret = self.account.client_secret  # Consumer Secret
        
        if not consumer_secret:
            raise ValueError(
                'Consumer Secret is required for WooCommerce API. '
                'Please enter your WooCommerce Consumer Secret in the Client Secret field.'
            )
        
        # Basic Auth: base64 encode "consumer_key:consumer_secret"
        # WooCommerce REST API uses Basic Authentication with Consumer Key:Consumer Secret
        credentials = f"{consumer_key}:{consumer_secret}"
        encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
        return f'Basic {encoded_credentials}'
    
    def _get_session(self):
        """Get or create a requests session for connection reuse"""
        if not hasattr(self, '_session'):
            self._session = requests.Session()
            # Set default timeout
            self._session.timeout = self.timeout
        return self._session
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None):
        """Make API request to WooCommerce REST API (optimized with session reuse)"""
        url = urljoin(self.base_url, endpoint.lstrip('/'))
        
        if headers is None:
            headers = {}
        
        # Add Basic Auth
        headers['Authorization'] = self._get_auth()
        headers.setdefault('Content-Type', 'application/json')
        
        # Use session for connection reuse (better performance)
        session = self._get_session()
        
        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    response = session.get(url, params=params, headers=headers, timeout=self.timeout)
                elif method.upper() == 'POST':
                    response = session.post(url, json=data, headers=headers, timeout=self.timeout)
                elif method.upper() == 'PUT':
                    response = session.put(url, json=data, headers=headers, timeout=self.timeout)
                else:
                    response = session.request(method, url, params=params, json=data, headers=headers, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    _logger.warning(f'Rate limited, waiting {retry_after} seconds')
                    import time
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    _logger.error(f'WooCommerce API request failed: {e}')
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            _logger.error(f'Error response: {error_detail}')
                        except:
                            _logger.error(f'Error response text: {e.response.text}')
                    raise
                wait_time = 2 ** attempt
                _logger.warning(f'Request failed, retrying in {wait_time}s: {e}')
                import time
                time.sleep(wait_time)
        
        raise Exception('Request failed after retries')
    
    def get_authorize_url(self):
        """WooCommerce doesn't use OAuth, uses API keys instead"""
        # WooCommerce uses Consumer Key/Secret (API keys) for authentication
        # No OAuth flow needed
        raise NotImplementedError(
            'WooCommerce uses API keys (Consumer Key/Secret) for authentication. '
            'Please configure Consumer Key and Consumer Secret in account settings. '
            'No OAuth authorization is required.'
        )
    
    def exchange_code(self, code):
        """WooCommerce doesn't use OAuth code exchange"""
        raise NotImplementedError('WooCommerce uses API keys, not OAuth')
    
    def refresh_access_token(self):
        """WooCommerce doesn't use access tokens"""
        raise NotImplementedError('WooCommerce uses API keys, not OAuth tokens')
    
    def fetch_orders(self, since, until=None):
        """Fetch orders from WooCommerce
        
        Args:
            since: datetime or string - start time
            until: datetime or string (optional) - end time
        
        Returns:
            list of order payloads
        """
        # Convert datetime to ISO format string
        if isinstance(since, datetime):
            since_str = since.strftime('%Y-%m-%dT%H:%M:%S')
        else:
            since_str = str(since)
        
        params = {
            'after': since_str,
            'per_page': 100,  # WooCommerce default max is 100
            'orderby': 'date',
            'order': 'asc',
        }
        
        if until:
            if isinstance(until, datetime):
                until_str = until.strftime('%Y-%m-%dT%H:%M:%S')
            else:
                until_str = str(until)
            params['before'] = until_str
        
        all_orders = []
        page = 1
        
        while True:
            params['page'] = page
            try:
                orders = self._make_request('GET', 'orders', params=params)
                
                if not orders:
                    break
                
                all_orders.extend(orders)
                
                # Check if we got less than per_page (last page)
                if len(orders) < params['per_page']:
                    break
                
                page += 1
                
            except Exception as e:
                _logger.error(f'Error fetching WooCommerce orders: {e}')
                break
        
        _logger.info(f'Fetched {len(all_orders)} orders from WooCommerce')
        return all_orders
    
    def update_inventory(self, items):
        """Update inventory on WooCommerce (optimized with concurrent requests)
        
        Args:
            items: list of tuples (external_sku, quantity) or list of dicts with 'external_sku', 'quantity', and optional 'external_product_id'
        
        Returns:
            dict with results per item and summary statistics
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        # If we have many items, use concurrent requests for better performance
        # WooCommerce API typically allows 2-5 concurrent requests per second
        # Adjust workers based on item count:
        # - 1-5 items: sequential (no overhead)
        # - 6-15 items: 2 workers
        # - 16+ items: 3-5 workers (scale up to 5 for very large batches)
        item_count = len(items)
        if item_count <= 5:
            use_concurrent = False
            max_workers = 1
        elif item_count <= 15:
            use_concurrent = True
            max_workers = 2
        elif item_count <= 50:
            use_concurrent = True
            max_workers = 3
        else:
            use_concurrent = True
            max_workers = min(5, item_count // 10 + 2)  # Scale up to 5 workers max
        
        results = {}
        
        def update_single_item(item):
            """Update a single item's inventory"""
            # Support both tuple format (sku, qty) and dict format
            if isinstance(item, tuple):
                external_sku, quantity = item
                external_product_id = None
            else:
                external_sku = item.get('external_sku') or item.get('sku')
                quantity = item.get('quantity')
                external_product_id = item.get('external_product_id')
            
            try:
                product_id = None
                product_type = 'simple'
                parent_id = None
                
                # Try to use cached product_id from binding if available
                if external_product_id:
                    # external_product_id might be in format "parent_id:variation_id" for variations
                    if ':' in str(external_product_id):
                        parent_id, product_id = str(external_product_id).split(':', 1)
                        product_id = int(product_id)
                        parent_id = int(parent_id)
                        product_type = 'variation'
                    else:
                        product_id = int(external_product_id)
                        product_type = 'simple'
                
                # If no cached product_id, find product by SKU
                if not product_id:
                    # Find product by SKU (this is the slow part)
                    products = self._make_request('GET', 'products', params={
                        'sku': external_sku,
                        'per_page': 1,
                    })
                    
                    if not products:
                        return {
                            'sku': external_sku,
                            'success': False,
                            'error': f'Product with SKU {external_sku} not found'
                        }
                    
                    product = products[0]
                    product_id = product['id']
                    product_type = product.get('type', 'simple')
                    parent_id = product.get('parent_id')
                
                # Check if this is a variation product
                if product_type == 'variation' and parent_id:
                    # Use variation endpoint: /products/{parent_id}/variations/{variation_id}
                    endpoint = f'products/{parent_id}/variations/{product_id}'
                    _logger.debug(f'Updating variation product: parent_id={parent_id}, variation_id={product_id}')
                else:
                    # Use regular product endpoint: /products/{product_id}
                    endpoint = f'products/{product_id}'
                    _logger.debug(f'Updating simple product: product_id={product_id}')
                
                # Update stock quantity
                update_data = {
                    'stock_quantity': max(0, int(quantity)),  # Ensure non-negative
                }
                
                updated_product = self._make_request('PUT', endpoint, data=update_data)
                
                return {
                    'sku': external_sku,
                    'success': True,
                    'product_id': product_id,
                    'product_type': product_type,
                    'parent_id': parent_id if product_type == 'variation' else None,
                    'new_quantity': updated_product.get('stock_quantity', 0),
                }
                
            except Exception as e:
                _logger.error(f'Error updating inventory for SKU {external_sku}: {e}')
                return {
                    'sku': external_sku if 'external_sku' in locals() else 'unknown',
                    'success': False,
                    'error': str(e)
                }
        
        # Use concurrent execution for better performance
        import time as time_module
        start_time = time_module.time()
        
        if use_concurrent:
            _logger.info(f'🚀 Using concurrent requests ({max_workers} workers) for {len(items)} items')
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all tasks
                future_to_item = {executor.submit(update_single_item, item): item for item in items}
                
                # Collect results as they complete
                completed_count = 0
                for future in as_completed(future_to_item):
                    try:
                        result = future.result()
                        sku = result.get('sku', 'unknown')
                        results[sku] = result
                        completed_count += 1
                        # Log progress every 10 items
                        if completed_count % 10 == 0 or completed_count == len(items):
                            elapsed = time_module.time() - start_time
                            _logger.debug(f'Progress: {completed_count}/{len(items)} items ({elapsed:.2f}s)')
                    except Exception as e:
                        item = future_to_item[future]
                        sku = item.get('external_sku') or item.get('sku') if isinstance(item, dict) else (item[0] if isinstance(item, tuple) else 'unknown')
                        results[sku] = {
                            'success': False,
                            'error': str(e)
                        }
                        completed_count += 1
            
            elapsed_time = time_module.time() - start_time
            _logger.info(f'✅ Concurrent execution completed: {len(items)} items in {elapsed_time:.2f}s ({elapsed_time/len(items):.3f}s per item)')
        else:
            # Sequential execution for small batches
            _logger.debug(f'Using sequential execution for {len(items)} items')
            for item in items:
                result = update_single_item(item)
                sku = result.get('sku', 'unknown')
                results[sku] = result
                # Small delay to avoid overwhelming the API (only for sequential)
                time_module.sleep(0.003)  # 3ms delay for sequential execution
            
            elapsed_time = time_module.time() - start_time
            _logger.debug(f'Sequential execution completed: {len(items)} items in {elapsed_time:.2f}s')
        
        # Calculate summary statistics
        success_count = sum(1 for r in results.values() if r.get('success', False))
        error_count = len(results) - success_count
        
        _logger.info(f'Updated {success_count}/{len(items)} products successfully (errors: {error_count})')
        
        return {
            'results': results,
            'updated': success_count,
            'errors': error_count,
            'total': len(items),
        }
    
    def verify_webhook(self, headers, body):
        """Verify WooCommerce webhook signature"""
        # WooCommerce webhooks can include a signature in headers
        # This is optional but recommended for security
        # For now, we'll accept all webhooks (can be enhanced later)
        return True
    
    def parse_order_payload(self, payload):
        """Parse WooCommerce order payload to standard format
        
        Args:
            payload: WooCommerce order JSON
        
        Returns:
            dict with standardized order data
        """
        # WooCommerce order structure
        order_id = str(payload.get('id', ''))
        order_number = payload.get('number', order_id)
        order_status = payload.get('status', '')
        
        # Parse order date (WooCommerce uses ISO format: 2025-11-01T22:30:33)
        order_date_str = payload.get('date_created', '')
        if order_date_str:
            try:
                # Parse ISO format datetime
                if 'T' in order_date_str:
                    # ISO format: 2025-11-01T22:30:33 or 2025-11-01T22:30:33+00:00
                    order_date = datetime.fromisoformat(order_date_str.replace('Z', '+00:00'))
                else:
                    # Fallback to standard format
                    order_date = datetime.strptime(order_date_str, '%Y-%m-%d %H:%M:%S')
            except (ValueError, AttributeError) as e:
                _logger.warning(f'Failed to parse order date "{order_date_str}": {e}')
                order_date = datetime.now()
        else:
            order_date = datetime.now()
        
        total = float(payload.get('total', 0))
        currency = payload.get('currency', 'USD')
        
        # Parse line items
        line_items = []
        for item in payload.get('line_items', []):
            line_items.append({
                'product_id': str(item.get('product_id', '')),
                'variant_id': str(item.get('variation_id', '0')),
                'sku': item.get('sku', ''),
                'name': item.get('name', ''),
                'quantity': int(item.get('quantity', 0)),
                'price': float(item.get('price', 0)),
                'total': float(item.get('total', 0)),
            })
        
        # Parse shipping address
        shipping = payload.get('shipping', {})
        shipping_address = {
            'first_name': shipping.get('first_name', ''),
            'last_name': shipping.get('last_name', ''),
            'company': shipping.get('company', ''),
            'address_1': shipping.get('address_1', ''),
            'address_2': shipping.get('address_2', ''),
            'city': shipping.get('city', ''),
            'state': shipping.get('state', ''),
            'postcode': shipping.get('postcode', ''),
            'country': shipping.get('country', ''),
            'phone': shipping.get('phone', ''),
        }
        
        # Parse billing address
        billing = payload.get('billing', {})
        billing_address = {
            'first_name': billing.get('first_name', ''),
            'last_name': billing.get('last_name', ''),
            'company': billing.get('company', ''),
            'address_1': billing.get('address_1', ''),
            'address_2': billing.get('address_2', ''),
            'city': billing.get('city', ''),
            'state': billing.get('state', ''),
            'postcode': billing.get('postcode', ''),
            'country': billing.get('country', ''),
            'email': billing.get('email', ''),
            'phone': billing.get('phone', ''),
        }
        
        # Parse shipping methods
        shipping_lines = []
        for shipping_line in payload.get('shipping_lines', []):
            shipping_lines.append({
                'method_id': shipping_line.get('method_id', ''),
                'method_title': shipping_line.get('method_title', ''),
                'total': float(shipping_line.get('total', 0)),
            })
        
        # Format customer info from billing address
        customer_name = f"{billing_address.get('first_name', '')} {billing_address.get('last_name', '')}".strip()
        customer_email = billing_address.get('email', '')
        customer_phone = billing_address.get('phone', '')
        
        # Format customer address
        address_parts = [
            billing_address.get('address_1', ''),
            billing_address.get('address_2', ''),
            billing_address.get('city', ''),
            billing_address.get('state', ''),
            billing_address.get('postcode', ''),
            billing_address.get('country', ''),
        ]
        customer_address = ', '.join([p for p in address_parts if p])
        
        # Format order lines for create_from_payload
        lines = []
        for item in line_items:
            lines.append({
                'external_sku': item.get('sku', ''),
                'product_name': item.get('name', ''),
                'quantity': item.get('quantity', 1),
                'price_unit': item.get('price', 0.0),
            })
        
        # Get currency ID
        currency_id = False
        if currency:
            currency_record = self.env['res.currency'].search([('name', '=', currency)], limit=1)
            if currency_record:
                currency_id = currency_record.id
        
        # Map order status
        status_map = {
            'pending': 'pending',
            'processing': 'pending',
            'on-hold': 'pending',
            'completed': 'synced',
            'cancelled': 'cancelled',
            'refunded': 'cancelled',
            'failed': 'failed',
        }
        order_state = status_map.get(order_status, 'pending')
        
        return {
            'external_order_id': order_id,
            'name': order_number,  # Order name/number
            'order_date': order_date,
            'amount_total': total,
            'currency_id': currency_id,
            'customer_name': customer_name,
            'customer_email': customer_email,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
            'state': order_state,
            'lines': lines,  # Changed from line_items to lines
        }


# Register adapter
from . import adapters
adapters.MarketplaceAdapters.register_adapter('woocommerce', WooCommerceAdapter)

