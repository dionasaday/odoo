# -*- coding: utf-8 -*-

from .adapters import MarketplaceAdapter
from odoo import fields
from datetime import datetime, timedelta
import logging
import requests
import time

_logger = logging.getLogger(__name__)

# LOCKED: Stable schema – ห้ามแก้ signature/logic ที่เป็นสัญญากับ client
class ZortoutAdapter(MarketplaceAdapter):
    """Zortout API adapter for product and stock synchronization"""
    
    def _get_base_url(self):
        """Get Zortout API base URL"""
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.zortout.base_url',
            'https://open-api.zortout.com/v4'
        )
        return base_url
    
    def _get_headers(self):
        """Get Zortout API headers with authentication"""
        return {
            'storename': self.account.client_id or '',  # storename
            'apikey': self.account.client_secret or '',  # apikey
            'apisecret': self.account.access_token or '',  # apisecret (stored in access_token field)
        }
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None):
        """Make API request to Zortout"""
        url = f"{self.base_url}{endpoint}"
        
        _logger.warning(f'🌐 Zortout API Request: {method.upper()} {url}')
        _logger.warning(f'   Params: {params}')
        _logger.warning(f'   Data: {data}')
        
        if headers is None:
            headers = {}
        
        # Add Zortout authentication headers
        zortout_headers = self._get_headers()
        _logger.warning(f'   Headers (storename): {zortout_headers.get("storename", "NOT SET")}')
        _logger.warning(f'   Headers (apikey): {"SET" if zortout_headers.get("apikey") else "NOT SET"}')
        _logger.warning(f'   Headers (apisecret): {"SET" if zortout_headers.get("apisecret") else "NOT SET"}')
        headers.update(zortout_headers)
        headers.setdefault('Content-Type', 'application/json')
        
        for attempt in range(self.max_retries):
            try:
                _logger.warning(f'   Attempt {attempt + 1}/{self.max_retries}')
                if method.upper() == 'GET':
                    response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                else:
                    response = requests.post(url, json=data, headers=headers, timeout=self.timeout)
                
                _logger.warning(f'   Response Status: {response.status_code}')
                _logger.warning(f'   Response Headers: {dict(response.headers)}')
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    _logger.warning(f'⚠️ Zortout rate limited, waiting {retry_after} seconds')
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                
                # Try to parse JSON
                try:
                    result = response.json()
                    _logger.warning(f'   Response JSON keys: {list(result.keys()) if isinstance(result, dict) else "Not a dict"}')
                    _logger.warning(f'   Response JSON (first 500 chars): {str(result)[:500]}')
                except Exception as json_error:
                    _logger.error(f'   ❌ Failed to parse JSON: {json_error}')
                    _logger.error(f'   Response text (first 1000 chars): {response.text[:1000]}')
                    raise
                
                # Zortout response format: { "resCode": "200", "resDesc": "...", "list": [...], "count": ... }
                # Check both 'res' (old format) and 'resCode' (new format)
                res_code = result.get('resCode') or result.get('res')
                
                # Ensure res_code is a string
                if isinstance(res_code, dict):
                    res_code = res_code.get('resCode') or res_code.get('res') or 'N/A'
                elif res_code is None:
                    res_code = 'N/A'
                else:
                    res_code = str(res_code)
                
                if res_code == '200' or (response.status_code == 200 and res_code == 'N/A'):
                    _logger.warning(f'   ✅ API call successful (resCode: {res_code})')
                    return result
                else:
                    error_msg = result.get('resDesc', 'Unknown error') or 'Unknown error'
                    _logger.error(f'   ❌ Zortout API error: resCode={res_code}, resDesc={error_msg}')
                    _logger.error(f'   Full response: {result}')
                    raise Exception(f'Zortout API error (resCode: {res_code}): {error_msg}')
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    _logger.error(f'   ❌ Zortout API request failed: {e}', exc_info=True)
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            _logger.error(f'   Error response JSON: {error_detail}')
                        except:
                            _logger.error(f'   Error response text: {e.response.text[:1000]}')
                    raise
                wait_time = 2 ** attempt
                _logger.warning(f'   ⚠️ Request failed, retrying in {wait_time}s: {e}')
                time.sleep(wait_time)
        
        raise Exception('Zortout request failed after retries')
    
    # OAuth methods (not required for Zortout - API key based)
    def get_authorize_url(self):
        """Zortout uses API key authentication, not OAuth"""
        raise NotImplementedError('Zortout uses API key authentication, not OAuth')
    
    def exchange_code(self, code):
        """Zortout uses API key authentication, not OAuth"""
        raise NotImplementedError('Zortout uses API key authentication, not OAuth')
    
    def refresh_access_token(self):
        """Zortout uses API key authentication, no token refresh needed"""
        return {'access_token': self.account.access_token, 'refresh_token': None, 'expires_in': 0}
    
    # Zortout-specific methods
    def fetch_products(self, page=1, limit=500, warehouse_code=None, **filters):
        """Fetch products from Zortout
        
        Args:
            page: Page number (default: 1)
            limit: Limit per page (max: 500, default: 500)
            warehouse_code: Warehouse code filter
            **filters: Additional filters (createdafter, createdbefore, keyword, etc.)
        
        Returns:
            dict with 'list' (products) and 'count' (total)
        """
        params = {
            'page': page,
            'limit': min(limit, 500),  # Max 500
        }
        
        if warehouse_code:
            params['warehousecode'] = warehouse_code
        
        # Add filters
        if filters.get('createdafter'):
            params['createdafter'] = filters['createdafter']
        if filters.get('createdbefore'):
            params['createdbefore'] = filters['createdbefore']
        if filters.get('updatedafter'):
            params['updatedafter'] = filters['updatedafter']
        if filters.get('updatedbefore'):
            params['updatedbefore'] = filters['updatedbefore']
        if filters.get('keyword'):
            params['keyword'] = filters['keyword']
        if filters.get('searchsku'):
            params['searchsku'] = filters['searchsku']
        if filters.get('variationid'):
            params['variationid'] = filters['variationid']
        if filters.get('categoryid'):
            params['categoryid'] = filters['categoryid']
        if filters.get('activestatus'):
            params['activestatus'] = filters['activestatus']
        
        _logger.warning(f'🔍 Zortout Fetch Products - Page: {page}, Limit: {limit}, Warehouse: {warehouse_code}, Params: {params}')
        
        try:
            response = self._make_request(
                'GET',
                '/Product/GetProducts',
                params=params
            )
            
            _logger.warning(f'📥 Zortout API Response keys: {list(response.keys()) if isinstance(response, dict) else "Not a dict"}')
            
            products = response.get('list', [])
            total_count = response.get('count', 0)
            
            _logger.warning(f'✅ Zortout Fetch Products - Found {len(products)} products (Total: {total_count})')
            
            if len(products) == 0:
                _logger.warning(f'⚠️ No products returned from API. Response: {response}')
            
            return {
                'products': products,
                'count': total_count,
                'page': page,
                'limit': limit,
            }
        except Exception as e:
            _logger.error(f'❌ Zortout Fetch Products Error: {e}', exc_info=True)
            raise
    
    def fetch_all_products(self, warehouse_code=None, **filters):
        """Fetch all products from Zortout with pagination"""
        _logger.warning(f'🔍 Zortout Fetch All Products - Starting (Warehouse: {warehouse_code}, Filters: {filters})')
        all_products = []
        page = 1
        limit = 500
        
        while True:
            _logger.warning(f'📄 Fetching page {page} (current total: {len(all_products)} products)')
            try:
                result = self.fetch_products(page=page, limit=limit, warehouse_code=warehouse_code, **filters)
                products = result.get('products', [])
                total_count = result.get('count', 0)
                _logger.warning(f'📦 Page {page}: Got {len(products)} products (Total count from API: {total_count})')
                
                all_products.extend(products)
                
                # Check if there are more pages
                if len(products) < limit:
                    _logger.warning(f'✅ Reached last page (got {len(products)} products, limit is {limit})')
                    break
                
                page += 1
                # Safety limit
                if page > 1000:  # Max 1000 pages
                    _logger.warning('⚠️ Reached maximum page limit (1000)')
                    break
            except Exception as e:
                _logger.error(f'❌ Error fetching page {page}: {e}', exc_info=True)
                # Re-raise the exception so the caller knows there was an error
                # Don't silently return empty list on authentication errors
                raise
        
        _logger.warning(f'✅ Zortout Fetch All Products - Total: {len(all_products)} products')
        return all_products
    
    def fetch_products_by_skus(self, sku_list, warehouse_code=None):
        """Fetch specific products by SKU list and return combined results"""
        if not sku_list:
            return []
        
        collected_products = []
        for sku in sku_list:
            try:
                result = self.fetch_products(
                    page=1,
                    limit=1,
                    warehouse_code=warehouse_code,
                    searchsku=sku,
                )
                products = result.get('products', [])
                if products:
                    collected_products.extend(products)
                else:
                    _logger.warning(f'⚠️ Zortout: SKU {sku} not found during targeted fetch')
            except Exception as e:
                _logger.error(f'❌ Zortout: Failed to fetch SKU {sku}: {e}', exc_info=True)
                continue
        
        return collected_products
    
    def get_product_detail(self, product_id, warehouse_code=None):
        """Get product detail from Zortout
        
        Args:
            product_id: Product ID
            warehouse_code: Warehouse code (optional)
        
        Returns:
            Product detail dict
        """
        params = {'id': product_id}
        if warehouse_code:
            params['warehousecode'] = warehouse_code
        
        response = self._make_request(
            'GET',
            '/Product/GetProductDetail',
            params=params
        )
        
        return response
    
    def get_warehouses(self, page=1, limit=500):
        """Get list of warehouses from Zortout
        
        Args:
            page: Page number (default: 1)
            limit: Limit per page (max: 500, default: 500)
        
        Returns:
            dict with 'list' (warehouses) and 'count' (total)
        """
        params = {
            'page': page,
            'limit': min(limit, 500),  # Max 500
        }
        
        _logger.warning(f'🔍 Zortout Get Warehouses - Page: {page}, Limit: {limit}')
        
        try:
            response = self._make_request(
                'GET',
                '/Warehouse/GetWarehouses',
                params=params
            )
            
            # Zortout API uses 'res' (not 'resCode') for warehouse endpoint
            res_code = response.get('res') or response.get('resCode')
            
            # Ensure res_code is a string
            if isinstance(res_code, dict):
                res_code = res_code.get('resCode') or res_code.get('res') or 'N/A'
            elif res_code is None:
                res_code = 'N/A'
            else:
                res_code = str(res_code)
            
            if res_code == '200':
                warehouses = response.get('list', [])
                total_count = response.get('count', 0)
                _logger.warning(f'✅ Zortout Get Warehouses - Found {len(warehouses)} warehouses (Total: {total_count})')
                return {
                    'warehouses': warehouses,
                    'count': total_count,
                    'page': page,
                    'limit': limit,
                }
            else:
                error_msg = response.get('resDesc', 'Unknown error') or 'Unknown error'
                _logger.error(f'❌ Zortout Get Warehouses error: resCode={res_code}, resDesc={error_msg}')
                raise Exception(f'Zortout API error (resCode: {res_code}): {error_msg}')
        except Exception as e:
            _logger.error(f'❌ Zortout Get Warehouses Error: {e}', exc_info=True)
            raise
    
    def test_warehouse_code(self, warehouse_code=None):
        """Test if warehouse code is valid by trying to fetch products
        
        Args:
            warehouse_code: Warehouse code to test (None = test without warehouse code)
        
        Returns:
            dict with 'valid': bool, 'products_count': int, 'error': str or None
        """
        _logger.warning(f'🧪 Testing warehouse code: {warehouse_code or "None (no warehouse code)"}')
        
        try:
            # Try to fetch products with or without warehouse code
            result = self.fetch_products(
                page=1,
                limit=1,  # Just need 1 product to verify
                warehouse_code=warehouse_code,
                activestatus=1
            )
            
            products = result.get('products', [])
            total_count = result.get('count', 0)
            
            _logger.warning(f'✅ Warehouse code test successful: {len(products)} products, total: {total_count}')
            
            return {
                'valid': True,
                'products_count': total_count,
                'error': None
            }
        except Exception as e:
            error_msg = str(e)
            _logger.error(f'❌ Warehouse code test failed: {error_msg}')
            return {
                'valid': False,
                'products_count': 0,
                'error': error_msg
            }
    
    def update_stock(self, stocks, warehouse_code):
        """Update product stock in Zortout
        
        Args:
            stocks: List of stock dicts with 'sku' or 'productid', 'stock', 'cost'
            warehouse_code: Warehouse code (required)
        
        Returns:
            dict with update results
        """
        if not warehouse_code:
            raise ValueError('warehouse_code is required for stock update')
        
        data = {
            'stocks': stocks
        }
        
        params = {
            'warehousecode': warehouse_code
        }
        
        _logger.info(f'🔍 Zortout Update Stock - Warehouse: {warehouse_code}, Items: {len(stocks)}')
        
        response = self._make_request(
            'POST',
            '/Product/UpdateProductStockList',
            params=params,
            data=data
        )
        
        _logger.info(f'✅ Zortout Update Stock - Response: {response.get("resDesc", "Success")}')
        
        return response
    
    # MarketplaceAdapter abstract methods (not used for Zortout but required)
    def fetch_orders(self, since, until=None):
        """Zortout is stock management, not marketplace orders"""
        return []
    
    def update_inventory(self, items):
        """Update inventory on Zortout
        
        Args:
            items: list of tuples (external_sku, quantity) or dicts with 'sku' and 'stock'
        
        Returns:
            dict with results
        """
        # Get warehouse code from shop or account
        warehouse_code = None
        if self.shop and self.shop.warehouse_id:
            warehouse_code = self.shop.warehouse_id.code or self.shop.warehouse_id.name
        
        if not warehouse_code:
            # Try to get from account config
            warehouse_code = self.account.stock_location_id.warehouse_id.code if self.account.stock_location_id else None
        
        if not warehouse_code:
            raise ValueError('Warehouse code is required for Zortout stock update')
        
        # Convert items to Zortout format
        stocks = []
        for item in items:
            if isinstance(item, tuple):
                sku, quantity = item
                stock_dict = {'sku': sku, 'stock': quantity}
            elif isinstance(item, dict):
                stock_dict = item.copy()
            else:
                continue
            
            stocks.append(stock_dict)
        
        return self.update_stock(stocks, warehouse_code)
    
    def verify_webhook(self, headers, body):
        """Verify webhook signature (if Zortout supports webhooks)"""
        # Zortout may not have webhook verification
        return True
    
    def parse_order_payload(self, payload):
        """Parse order payload (not used for Zortout)"""
        return payload


# Register adapter
from . import adapters
adapters.MarketplaceAdapters.register_adapter('zortout', ZortoutAdapter)

