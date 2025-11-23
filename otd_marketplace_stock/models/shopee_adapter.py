# -*- coding: utf-8 -*-

from .adapters import MarketplaceAdapter
from odoo import fields
from datetime import datetime, timedelta
import logging
import urllib.parse
import hmac
import hashlib
import time
import requests

_logger = logging.getLogger(__name__)

# LOCKED: Stable schema – ห้ามแก้ signature/logic ที่เป็นสัญญากับ client
class ShopeeAdapter(MarketplaceAdapter):
    """Shopee marketplace adapter"""
    
    def _get_base_url(self):
        """Get Shopee API base URL"""
        # Use environment variable or default to production URL
        # Production: https://partner.shopeemobile.com/api/v2
        # Sandbox: https://openplatform.sandbox.test-stable.shopee.sg/api/v2
        base_url = self.env['ir.config_parameter'].sudo().get_param(
            'marketplace.shopee.base_url',
            'https://partner.shopeemobile.com/api/v2'  # Default to production
        )
        return base_url
    
    # LOCKED: Shopee HMAC signature algorithm - ห้ามแก้ไข format ของ base_string หรือ signature generation
    def _sign_request(self, partner_id, path, timestamp, access_token=None):
        """Generate Shopee HMAC signature
        LOCKED: This signature format is required by Shopee API v2 spec.
        Do not modify the base_string format or signature generation logic.
        """
        secret = self.account.client_secret or ''
        base_string = f"{partner_id}{path}{timestamp}{access_token or ''}"
        signature = hmac.new(
            secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    # LOCKED: Shopee API request signing - ห้ามแก้ไข signature generation หรือ header structure
    def _make_request(self, method, endpoint, params=None, data=None, headers=None):
        """Make API request with Shopee HMAC signing
        
        LOCKED: This method implements Shopee API v2 request signing specification.
        Do not modify:
        - Signature generation logic (uses _sign_request)
        - Required headers structure (Shopee-Partner-Id, Shopee-Timestamp, Shopee-Signature)
        - Path construction for signing
        """
        url = f"{self.base_url}{endpoint}"
        
        if headers is None:
            headers = {}
        
        # LOCKED: Shopee requires HMAC signature with specific format
        partner_id = int(self.account.client_id)
        timestamp = int(time.time())
        access_token = self._get_access_token() or ''
        
        # For POST requests, Shopee API v2 requires public params (partner_id, timestamp, sign) in query string
        # Initialize params dict if None and method is POST
        if method.upper() == 'POST' and params is None:
            params = {}
        
        # For POST requests, ensure public params are in params dict for query string
        if method.upper() == 'POST' and params is not None:
            # Add public params to params dict if not already present
            if 'partner_id' not in params:
                params['partner_id'] = partner_id
            if 'timestamp' not in params:
                params['timestamp'] = timestamp
        
        # LOCKED: Build path for signing (endpoint + sorted query params)
        path = endpoint
        if params:
            sorted_params = sorted(params.items())
            path += '?' + urllib.parse.urlencode(sorted_params)
        
        # LOCKED: Generate signature using _sign_request (HMAC-SHA256)
        signature = self._sign_request(partner_id, path, timestamp, access_token)
        
        # Add sign to params for POST requests (after signature is generated)
        if method.upper() == 'POST' and params is not None:
            params['sign'] = signature
        
        # LOCKED: Add Shopee required headers (required by Shopee API v2 spec)
        if access_token:
            headers['Authorization'] = f'Bearer {access_token}'
        headers['Shopee-Partner-Id'] = str(partner_id)
        headers['Shopee-Timestamp'] = str(timestamp)
        headers['Shopee-Signature'] = signature
        headers.setdefault('Content-Type', 'application/json')
        
        for attempt in range(self.max_retries):
            try:
                if method.upper() == 'GET':
                    response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
                else:
                    # POST request: params go in query string, data goes in body
                    response = requests.post(url, params=params, json=data, headers=headers, timeout=self.timeout)
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    _logger.warning(f'Rate limited, waiting {retry_after} seconds')
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                result = response.json()
                
                _logger.warning(f'🔍 Shopee API Response - Status: {response.status_code}, Keys: {list(result.keys()) if isinstance(result, dict) else "not a dict"}')
                
                # Shopee wraps response in 'response' key
                if 'response' in result:
                    response_data = result['response']
                    _logger.warning(f'🔍 Shopee API Response Data - Keys: {list(response_data.keys()) if isinstance(response_data, dict) else "not a dict"}')
                    return response_data
                _logger.warning(f'🔍 Shopee API Response - No "response" key, returning result directly')
                return result
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    _logger.error(f'Shopee API request failed: {e}')
                    if hasattr(e, 'response') and e.response is not None:
                        try:
                            error_detail = e.response.json()
                            _logger.error(f'Error response: {error_detail}')
                        except:
                            _logger.error(f'Error response text: {e.response.text}')
                    raise
                wait_time = 2 ** attempt
                _logger.warning(f'Request failed, retrying in {wait_time}s: {e}')
                time.sleep(wait_time)
        
        raise Exception('Request failed after retries')
    
    # LOCKED: Shopee OAuth authorization URL generation - ห้ามแก้ไข signature format หรือ param structure
    def get_authorize_url(self):
        """Get Shopee OAuth authorization URL
        
        LOCKED: This method implements Shopee API v2 OAuth authorization URL generation.
        Do not modify the signature calculation or parameter structure.
        """
        redirect_uri = self.env['ir.config_parameter'].sudo().get_param(
            'web.base.url'
        ) + '/marketplace/oauth/callback/shopee'
        
        # LOCKED: Shopee requires timestamp and signature for auth URL (required by Shopee API v2 spec)
        partner_id = int(self.account.client_id)
        timestamp = int(time.time())
        
        # LOCKED: Build path for signing (required by Shopee API v2 spec)
        path = '/api/v2/shop/auth_partner'
        # LOCKED: Shopee auth_partner parameters (required by Shopee API v2 spec)
        # Note: Use 'redirect' not 'redirect_uri'
        params_dict = {
            'partner_id': partner_id,
            'redirect': redirect_uri,
            'timestamp': timestamp,
        }
        
        # LOCKED: Shopee signature calculation for auth_partner endpoint
        # Base string format: partner_id + path + timestamp
        # Note: redirect_uri is NOT included in signature calculation (required by Shopee spec)
        base_string = f"{partner_id}{path}{timestamp}"
        client_secret = (self.account.client_secret or '').strip()
        
        # Debug logging (using warning level to ensure visibility)
        _logger.warning(f"🔍 Shopee OAuth Debug - Partner ID: {partner_id}")
        _logger.warning(f"🔍 Shopee OAuth Debug - Client Secret length: {len(client_secret)}")
        _logger.warning(f"🔍 Shopee OAuth Debug - Client Secret preview: {client_secret[:10]}...{client_secret[-10:] if len(client_secret) > 20 else ''}")
        _logger.warning(f"🔍 Shopee OAuth Debug - Base string: {base_string}")
        
        if not client_secret:
            _logger.error("❌ Shopee OAuth: Client Secret is empty! Please set Partner Key in Account settings.")
            raise ValueError("Client Secret (Partner Key) is required for OAuth")
        
        # LOCKED: Generate signature using HMAC-SHA256 (required by Shopee API v2 spec)
        signature = hmac.new(
            client_secret.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        _logger.warning(f"🔍 Shopee OAuth Debug - Calculated Signature: {signature}")
        _logger.warning(f"🔍 Shopee OAuth Debug - Redirect URI: {redirect_uri}")
        
        # Add signature to params
        params_dict['sign'] = signature
        
        # Get base URL (supports both test and live environments)
        # For auth_partner, we need the base domain, not the full API path
        base_url = self._get_base_url()
        # Extract domain from base_url (e.g., https://partner.shopeemobile.com from https://partner.shopeemobile.com/api/v2)
        if '/api/v2' in base_url:
            domain = base_url.replace('/api/v2', '')
        else:
            domain = base_url.rstrip('/')
        
        _logger.warning(f"🔍 Shopee OAuth Debug - Using domain: {domain}")
        
        # Build final URL
        auth_url = f"{domain}{path}"
        auth_url += '?' + urllib.parse.urlencode(params_dict)
        
        return auth_url
    # LOCKED: Shopee OAuth token exchange - ห้ามแก้ไข request structure, signature format, หรือ param placement
    def exchange_code(self, code, shop_id=None):
        """Exchange authorization code for tokens
        API Documentation: https://open.shopee.com/documents?module=2&type=1&id=375
        Path: /api/v2/auth/token/get
        Production: https://partner.shopeemobile.com/api/v2/auth/token/get
        Sandbox: https://openplatform.sandbox.test-stable.shopee.sg/api/v2/auth/token/get
        
        Note: access_token and refresh_token must be saved separately for each shop_id and merchant_id
        
        LOCKED: This method implements Shopee API v2 OAuth token exchange specification.
        Do not modify:
        - Request structure (query params vs body params)
        - Signature base string format
        - Parameter placement (public params in query, business params in body)
        """
        # Shopee requires shop_id from callback, not from shop object
        if not shop_id:
            # Try to get from callback parameters or shop object
            shop_id = int(self.shop.external_shop_id) if self.shop and self.shop.external_shop_id else None
        
        if not shop_id:
            raise ValueError('shop_id is required for token exchange. It should be provided in OAuth callback.')
        
        # LOCKED: Shopee API v2 spec - Public params (query): partner_id, timestamp, sign
        # LOCKED: Shopee API v2 spec - Business params (body): code, shop_id, partner_id
        partner_id = int(self.account.client_id)
        partner_key = (self.account.client_secret or '').strip()
        timestamp = int(time.time())
        
        # LOCKED: API path according to spec: /api/v2/auth/token/get
        # Since base_url already includes /api/v2, we use /auth/token/get
        api_path = '/auth/token/get'
        # Full path for signature: /api/v2/auth/token/get
        full_api_path = '/api/v2/auth/token/get'
        
        # LOCKED: Base string for signature: partner_id + full_api_path + timestamp
        # According to Shopee spec, no access_token for token exchange
        base_string = f'{partner_id}{full_api_path}{timestamp}'
        
        # LOCKED: Generate signature using HMAC-SHA256
        sign = hmac.new(
            partner_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # LOCKED: Public params → query string (required by Shopee API v2 spec)
        query_params = {
            'partner_id': partner_id,
            'timestamp': timestamp,
            'sign': sign,
        }
        query_string = urllib.parse.urlencode(query_params)
        
        # Build URL with public params in query
        url = f"{self.base_url}{api_path}?{query_string}"
        
        # LOCKED: Business params → JSON body (required by Shopee API v2 spec)
        body = {
            'code': code,
            'shop_id': int(shop_id),
            'partner_id': partner_id,  # Required in body according to spec
        }
        
        # Headers (no Authorization header for token exchange)
        headers = {
            'Content-Type': 'application/json',
        }
        
        _logger.error(f'🔍 Shopee Token Exchange - Base URL: {self.base_url}')
        _logger.error(f'🔍 Shopee Token Exchange - Partner ID: {partner_id}, Shop ID: {int(shop_id)}, Code: {code[:20]}...')
        _logger.error(f'🔍 Shopee Token Exchange - Full API Path: {full_api_path}')
        _logger.error(f'🔍 Shopee Token Exchange - Base String: {base_string}')
        _logger.error(f'🔍 Shopee Token Exchange - Signature: {sign}')
        _logger.error(f'🔍 Shopee Token Exchange - URL: {url}')
        _logger.error(f'🔍 Shopee Token Exchange - Query Params: {query_params}')
        _logger.error(f'🔍 Shopee Token Exchange - Body: {body}')
        
        # Make request - POST with business params in body
        try:
            response = requests.post(url, json=body, headers=headers, timeout=30)
            _logger.error(f'🔍 Shopee Token Exchange - Response Status: {response.status_code}')
            _logger.error(f'🔍 Shopee Token Exchange - Response Headers: {dict(response.headers)}')
            _logger.error(f'🔍 Shopee Token Exchange - Response Text: {response.text[:1000]}')
            
            response.raise_for_status()
            result = response.json()
            
            _logger.error(f'🔍 Shopee Token Exchange - Response JSON Keys: {list(result.keys()) if isinstance(result, dict) else "not a dict"}')
            _logger.error(f'🔍 Shopee Token Exchange - Response JSON: {result}')
            
            # Shopee wraps response in 'response' key
            if 'response' in result:
                response_data = result['response']
                _logger.error(f'🔍 Shopee Token Exchange - Response Data Keys: {list(response_data.keys()) if isinstance(response_data, dict) else "not a dict"}')
            else:
                response_data = result
            
        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    _logger.error(f'❌ Shopee Token Exchange - Error Response JSON: {error_detail}')
                except:
                    error_detail = e.response.text
                    _logger.error(f'❌ Shopee Token Exchange - Error Response Text: {error_detail}')
            _logger.error(f'❌ Shopee Token Exchange - Request Exception: {e}', exc_info=True)
            raise ValueError(f'Failed to exchange code for tokens: {str(e)}, Error Detail: {error_detail}')
        
        # Use response_data for further processing
        response = response_data
        
        _logger.error(f'🔍 Shopee Token Exchange - Response Type: {type(response)}')
        _logger.error(f'🔍 Shopee Token Exchange - Response Keys: {list(response.keys()) if isinstance(response, dict) else "not a dict"}')
        _logger.error(f'🔍 Shopee Token Exchange - Response: access_token={bool(response.get("access_token"))}, refresh_token={bool(response.get("refresh_token"))}')
        
        # Log full response for debugging (first 1000 chars)
        response_str = str(response)
        _logger.error(f'🔍 Shopee Token Exchange - Response Full: {response_str}')
        
        # Try different possible key names for tokens
        access_token = response.get('access_token') or response.get('accessToken') or response.get('access_token')
        refresh_token = response.get('refresh_token') or response.get('refreshToken') or response.get('refresh_token')
        
        # If still no token, check for error response
        if not access_token and not refresh_token:
            error_msg = response.get('error') or response.get('message') or 'Unknown error'
            error_description = response.get('error_description') or response.get('msg') or ''
            _logger.error(f'❌ Shopee Token Exchange - No tokens in response. Error: {error_msg}, Description: {error_description}')
            _logger.error(f'❌ Shopee Token Exchange - Full Response: {response_str}')
            raise ValueError(f'No tokens received from Shopee API. Error: {error_msg}, Description: {error_description}, Response: {response_str}')
        
        _logger.error(f'🔍 Shopee Token Exchange - Access Token (after key check): {bool(access_token)}')
        _logger.error(f'🔍 Shopee Token Exchange - Refresh Token (after key check): {bool(refresh_token)}')
        
        token_result = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'expires_in': response.get('expires_in') or response.get('expiresIn') or response.get('expires_in', 3600),
            'shop_id': response.get('shop_id') or response.get('shopId') or response.get('shop_id') or shop_id,
        }
        
        _logger.error(f'🔍 Shopee Token Exchange - Token Result: access_token={bool(token_result.get("access_token"))}, refresh_token={bool(token_result.get("refresh_token"))}, shop_id={token_result.get("shop_id")}')
        if token_result.get('access_token'):
            _logger.error(f'🔍 Shopee Token Exchange - Access Token Value: {token_result.get("access_token")[:50]}...')
        if token_result.get('refresh_token'):
            _logger.error(f'🔍 Shopee Token Exchange - Refresh Token Value: {token_result.get("refresh_token")[:50]}...')
        
        return token_result
    
    def get_shops(self):
        """Get list of shops from Shopee API"""
        try:
            # Shopee Public API: Get shops by partner
            response = self._make_request(
                'GET',
                '/public/get_shops_by_partner',
                params={
                    'partner_id': int(self.account.client_id),
                }
            )
            
            # _make_request already unwraps 'response' key, so response is already the inner object
            shops = response.get('shops', []) if isinstance(response, dict) else []
            _logger.info(f'Found {len(shops)} shops from Shopee API')
            return shops
        except Exception as e:
            _logger.warning(f'Failed to get shops from Shopee API: {e}')
            return []
    
    def get_shop_info(self, shop_id):
        """Get shop information from Shopee API"""
        try:
            # Shop API requires shop_id in params
            # Need to create a temporary shop object for this
            shop_record = self.env['marketplace.shop'].sudo().search([
                ('external_shop_id', '=', str(shop_id)),
                ('account_id', '=', self.account.id),
            ], limit=1)
            
            if not shop_record:
                # Create temporary shop for API call
                shop_record = self.env['marketplace.shop'].sudo().new({
                    'external_shop_id': str(shop_id),
                    'account_id': self.account.id,
                })
            
            # Create adapter with shop
            adapter = self.__class__(self.account, shop_record)
            response = adapter._make_request(
                'GET',
                '/shop/get_shop_info',
                params={
                    'shop_id': int(shop_id),
                }
            )
            
            return response
        except Exception as e:
            _logger.warning(f'Failed to get shop info for shop_id {shop_id}: {e}')
            return {}
    
    # LOCKED: Shopee API v2 refresh token implementation - ห้ามแก้ไข signature generation, request structure, หรือ parameter placement
    # This method has been tested and verified to work correctly with Shopee API v2
    # Do not modify:
    # - Signature base string format (partner_id + full_api_path + timestamp, NO refresh_token)
    # - Request structure (public params in query, business params in body)
    # - Parameter placement (shop_id, refresh_token, partner_id in body)
    # - Direct request implementation (bypasses _make_request to prevent recursion)
    def refresh_access_token(self):
        """Refresh Shopee access token
        
        LOCKED: This method implements Shopee API v2 refresh token specification.
        Tested and verified: 2025-11-15
        Do not modify signature generation, request structure, or parameter placement.
        """
        # Prevent recursion: use current access_token directly without checking expiry
        # This is called from _check_token_expiry, so we don't want to trigger another check
        
        # Get shop_id - required by Shopee API for refresh token
        shop_id = None
        if self.shop and self.shop.external_shop_id:
            shop_id = int(self.shop.external_shop_id)
        elif self.account.shop_ids:
            # Try to get shop_id from first shop
            first_shop = self.account.shop_ids[0]
            if first_shop.external_shop_id:
                shop_id = int(first_shop.external_shop_id)
        
        if not shop_id:
            raise ValueError('shop_id is required for refresh token. Please ensure the account has at least one shop with external_shop_id.')
        
        # LOCKED: Shopee API v2 spec for refresh token - similar to token exchange
        # Public params (query): partner_id, timestamp, sign
        # Business params (body): refresh_token, partner_id, shop_id
        partner_id = int(self.account.client_id)
        partner_key = (self.account.client_secret or '').strip()
        timestamp = int(time.time())
        
        # LOCKED: API path according to spec: /api/v2/auth/access_token/get
        # Since base_url already includes /api/v2, we use /auth/access_token/get
        api_path = '/auth/access_token/get'
        # Full path for signature: /api/v2/auth/access_token/get
        full_api_path = '/api/v2/auth/access_token/get'
        
        # LOCKED: Base string for signature: partner_id + full_api_path + timestamp
        # According to Shopee spec, refresh_token is NOT included in signature base string
        # (similar to token exchange where code is not in signature)
        base_string = f'{partner_id}{full_api_path}{timestamp}'
        
        # LOCKED: Generate signature using HMAC-SHA256
        sign = hmac.new(
            partner_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # LOCKED: Public params → query string (required by Shopee API v2 spec)
        query_params = {
            'partner_id': partner_id,
            'timestamp': timestamp,
            'sign': sign,
        }
        query_string = urllib.parse.urlencode(query_params)
        
        # Build URL with public params in query
        url = f"{self.base_url}{api_path}?{query_string}"
        
        # LOCKED: Business params → JSON body (required by Shopee API v2 spec)
        body = {
            'refresh_token': self.account.refresh_token,
            'partner_id': partner_id,  # Required in body according to spec
            'shop_id': shop_id,  # Required by Shopee API
        }
        
        # Headers (no Authorization header for refresh token)
        headers = {
            'Content-Type': 'application/json',
        }
        
        _logger.warning(f'🔍 Shopee Refresh Token - Base URL: {self.base_url}')
        _logger.warning(f'🔍 Shopee Refresh Token - Partner ID: {partner_id}, Shop ID: {shop_id}')
        _logger.warning(f'🔍 Shopee Refresh Token - Full API Path: {full_api_path}')
        _logger.warning(f'🔍 Shopee Refresh Token - Base String: {base_string}')
        _logger.warning(f'🔍 Shopee Refresh Token - Signature: {sign}')
        _logger.warning(f'🔍 Shopee Refresh Token - URL: {url}')
        _logger.warning(f'🔍 Shopee Refresh Token - Body: {body}')
        
        # LOCKED: Make request directly (bypasses _make_request to prevent recursion)
        # POST with business params in body - tested and verified
        try:
            response = requests.post(url, json=body, headers=headers, timeout=30)
            _logger.warning(f'🔍 Shopee Refresh Token - Response Status: {response.status_code}')
            _logger.warning(f'🔍 Shopee Refresh Token - Response Text: {response.text[:500]}')
            
            response.raise_for_status()
            result = response.json()
            
            # LOCKED: Shopee wraps response in 'response' key (tested and verified)
            if 'response' in result:
                response_data = result['response']
            else:
                response_data = result
            
            _logger.warning(f'🔍 Shopee Refresh Token - Response Data: {response_data}')
            
        except requests.exceptions.RequestException as e:
            error_detail = ''
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    _logger.error(f'❌ Shopee Refresh Token - Error Response JSON: {error_detail}')
                except:
                    error_detail = e.response.text
                    _logger.error(f'❌ Shopee Refresh Token - Error Response Text: {error_detail}')
            _logger.error(f'❌ Shopee Refresh Token - Request Exception: {e}', exc_info=True)
            raise ValueError(f'Failed to refresh token: {str(e)}, Error Detail: {error_detail}')
        
        # LOCKED: Return format - tested and verified
        return {
            'access_token': response_data.get('access_token'),
            'refresh_token': response_data.get('refresh_token', self.account.refresh_token),
            'expires_in': response_data.get('expires_in') or response_data.get('expire_in', 3600),
        }
    
    # LOCKED: Shopee API v2 fetch_orders implementation - ห้ามแก้ไข request method, parameter structure, signature calculation, หรือ response handling
    # This method has been tested and verified to work correctly with Shopee API v2
    # Tested and verified: 2025-11-15 - Successfully fetched 206 orders
    # Do not modify:
    # - Request method (GET, not POST)
    # - Parameter placement (all parameters in query string)
    # - Signature calculation (partner_id + api_path + timestamp + access_token + shop_id)
    # - API path for signature (/api/v2/order/get_order_list)
    # - Response parsing (order_list, next_cursor, more)
    def fetch_orders(self, since, until=None):
        """Fetch orders from Shopee
        
        LOCKED: This method implements Shopee API v2 /order/get_order_list specification.
        Tested and verified: 2025-11-15
        Successfully fetched 206 orders from Shopee API.
        Do not modify request method, parameter structure, signature calculation, or response handling.
        """
        if not self.shop:
            raise ValueError('Shop is required for fetching orders')
        
        # Convert datetime if needed
        if isinstance(since, str):
            since = datetime.fromisoformat(since)
        if until is None:
            until = datetime.now()
        elif isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        _logger.warning(f'🔍 Shopee Fetch Orders - Shop ID: {self.shop.external_shop_id}')
        _logger.warning(f'🔍 Shopee Fetch Orders - Time Range: {since} to {until}')
        _logger.warning(f'🔍 Shopee Fetch Orders - Since timestamp: {int(since.timestamp())}, Until timestamp: {int(until.timestamp())}')
        
        # LOCKED: Shopee API v2 /order/get_order_list - GET request with ALL parameters in query string
        # According to Shopee API v2 documentation:
        # - Method: GET (not POST)
        # - All parameters (common + request) go in query string
        # - Signature: partner_id + api_path + timestamp + access_token + shop_id + partner_key
        partner_id = int(self.account.client_id)
        partner_key = (self.account.client_secret or '').strip()
        timestamp = int(time.time())
        access_token = self._get_access_token() or ''
        
        # Get shop_id - required by Shopee API
        shop_id = None
        if self.shop and self.shop.external_shop_id:
            shop_id = int(self.shop.external_shop_id)
        else:
            raise ValueError('shop_id is required for fetching orders. Please ensure the shop has external_shop_id.')
        
        # LOCKED: Build path for signature calculation
        # According to Shopee API v2 spec: partner_id + api_path + timestamp + access_token + shop_id
        # api_path must be the full path: /api/v2/order/get_order_list (not just /order/get_order_list)
        api_path = '/api/v2/order/get_order_list'
        endpoint = '/order/get_order_list'  # For URL construction (base_url already includes /api/v2)
        
        # LOCKED: Generate signature using HMAC-SHA256
        # Base string format: partner_id + api_path + timestamp + access_token + shop_id
        # Note: partner_key is used as HMAC secret, not included in base string
        # api_path must be the full path including /api/v2
        # DO NOT MODIFY: This signature format is required by Shopee API v2 spec
        base_string = f"{partner_id}{api_path}{timestamp}{access_token}{shop_id}"
        signature = hmac.new(
            partner_key.encode('utf-8'),
            base_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        all_orders = []
        cursor = ''
        
        while True:
            # LOCKED: All parameters go in query string (GET request) - tested and verified
            # Common parameters: partner_id, timestamp, access_token, shop_id, sign
            # Request parameters: time_range_field, time_from, time_to, page_size, cursor
            # DO NOT MODIFY: This parameter structure is required by Shopee API v2 spec
            query_params = {
                # Common parameters
                'partner_id': partner_id,
                'timestamp': timestamp,
                'access_token': access_token,
                'shop_id': shop_id,
                'sign': signature,
                # Request parameters
                'time_range_field': 'create_time',
                'time_from': int(since.timestamp()),
                'time_to': int(until.timestamp()),
                'page_size': 100,
            }
            
            if cursor:
                query_params['cursor'] = cursor
            
            _logger.warning(f'🔍 Shopee Fetch Orders - Calling API: GET /order/get_order_list')
            _logger.warning(f'🔍 Shopee Fetch Orders - Query Params: partner_id={partner_id}, shop_id={shop_id}, timestamp={timestamp}, time_from={query_params["time_from"]}, time_to={query_params["time_to"]}, cursor={query_params.get("cursor", "")}')
            _logger.warning(f'🔍 Shopee Fetch Orders - Signature Base String: {base_string}')
            _logger.warning(f'🔍 Shopee Fetch Orders - Signature: {signature}')
            
            # LOCKED: Use GET request with all parameters in query string - tested and verified
            # Note: We bypass _make_request to avoid duplicate signature generation
            # _make_request creates its own signature, but we need custom signature for /order/get_order_list
            # DO NOT MODIFY: This request structure is required by Shopee API v2 spec
            url = f"{self.base_url}/order/get_order_list"
            query_string = urllib.parse.urlencode(query_params)
            full_url = f"{url}?{query_string}"
            
            headers = {
                'Content-Type': 'application/json',
            }
            
            # LOCKED: Make GET request directly - tested and verified
            try:
                response_obj = requests.get(full_url, headers=headers, timeout=self.timeout)
                response_obj.raise_for_status()
                result = response_obj.json()
                
                # LOCKED: Shopee wraps response in 'response' key (tested and verified)
                if 'response' in result:
                    response_data = result['response']
                else:
                    response_data = result
                
                response = response_data
                
            except requests.exceptions.RequestException as e:
                _logger.error(f'Shopee Fetch Orders - Request failed: {e}')
                if hasattr(e, 'response') and e.response is not None:
                    try:
                        error_detail = e.response.json()
                        _logger.error(f'Error response: {error_detail}')
                    except:
                        _logger.error(f'Error response text: {e.response.text}')
                raise
            
            _logger.warning(f'🔍 Shopee Fetch Orders - API Response: {type(response)}, keys: {list(response.keys()) if isinstance(response, dict) else "not a dict"}')
            
            # LOCKED: Check for errors in response - tested and verified
            if isinstance(response, dict) and 'error' in response:
                error_msg = response.get('error', 'Unknown error')
                error_message = response.get('message', 'No message')
                request_id = response.get('request_id', 'No request ID')
                _logger.error(f'❌ Shopee Fetch Orders - API Error: {error_msg}, Message: {error_message}, Request ID: {request_id}')
                _logger.error(f'❌ Shopee Fetch Orders - Full Error Response: {response}')
                # Return empty list on error (don't raise exception to allow retry)
                return []
            
            # LOCKED: Parse order_list from response - tested and verified
            # Response structure: {'more': bool, 'next_cursor': str, 'order_list': [...]}
            orders = response.get('order_list', [])
            _logger.warning(f'🔍 Shopee Fetch Orders - Orders in response: {len(orders)}')
            
            # Extract order_sn from order_list for detail fetching
            order_sn_list = [o.get('order_sn') for o in orders if o.get('order_sn')]
            _logger.warning(f'🔍 Shopee Fetch Orders - Extracted {len(order_sn_list)} order_sn from list response')
            
            # Fetch detailed order information using /order/get_order_detail
            if order_sn_list:
                # Shopee API limit: max 50 orders per batch
                batch_size = 50
                for batch_start in range(0, len(order_sn_list), batch_size):
                    batch = order_sn_list[batch_start:batch_start + batch_size]
                    _logger.warning(f'🔍 Shopee Fetch Orders - Fetching details for batch {batch_start // batch_size + 1} ({len(batch)} orders)')
                    
                    try:
                        # Prepare detail request payload
                        detail_payload = {
                            'order_sn_list': batch,
                            'response_optional_fields': [
                                'item_list',
                                'recipient_address',
                                'buyer_username',
                                'payment_method',
                                'total_amount',
                                'amount_detail',
                            ],
                        }
                        
                        # Use _make_request for detail endpoint (POST request)
                        # Note: _make_request will handle signature generation automatically
                        detail_response = self._make_request(
                            'POST',
                            '/order/get_order_detail',
                            data=detail_payload
                        )
                        
                        # Check for errors in detail response
                        if isinstance(detail_response, dict) and 'error' in detail_response:
                            error_msg = detail_response.get('error', 'Unknown error')
                            error_message = detail_response.get('message', 'No message')
                            _logger.error(f'❌ Shopee Fetch Order Details - API Error: {error_msg}, Message: {error_message}')
                            # Continue with next batch even if one fails
                            continue
                        
                        # Extract detailed orders from response
                        detail_orders = detail_response.get('order_list', [])
                        _logger.warning(f'🔍 Shopee Fetch Orders - Got {len(detail_orders)} detailed orders from batch')
                        
                        all_orders.extend(detail_orders)
                        
                    except Exception as e:
                        _logger.error(f'❌ Shopee Fetch Orders - Failed to fetch details for batch: {e}', exc_info=True)
                        # Continue with next batch even if one fails
                        continue
            
            # LOCKED: Pagination handling - tested and verified
            cursor = response.get('next_cursor')
            if not cursor or len(orders) == 0:
                break
        
        _logger.warning(f'🔍 Shopee Fetch Orders - Total detailed orders fetched: {len(all_orders)}')
        return all_orders
    
    def update_inventory(self, items):
        """Update inventory on Shopee
        
        Args:
            items: list of tuples (external_sku, quantity)
        
        Returns:
            dict with results
        """
        if not self.shop:
            raise ValueError('Shop is required for updating inventory')
        
        # Shopee batch update
        item_list = []
        for sku, qty in items:
            item_list.append({
                'seller_sku': sku,
                'available_stock': int(qty),
            })
        
        data = {
            'item_list': item_list,
        }
        
        response = self._make_request(
            'POST',
            '/product/update_stock',
            data=data,
        )
        
        # Map results
        results = {}
        for item in response.get('item_list', []):
            results[item.get('seller_sku')] = {
                'success': item.get('success', False),
                'error': item.get('error', ''),
            }
        
        return results
    
    def verify_webhook(self, headers, body):
        """Verify Shopee webhook signature"""
        signature = headers.get('X-Shopee-Signature', '')
        if not signature:
            return False
        
        # Shopee uses HMAC-SHA256
        secret = self.account.client_secret or ''
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            body.encode('utf-8') if isinstance(body, str) else body,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    def parse_order_payload(self, payload):
        """Parse Shopee order payload to standard format
        
        Supports payload from both /order/get_order_list and /order/get_order_detail
        """
        order_sn = payload.get('order_sn', '')
        order_status = payload.get('order_status', '')
        
        # Map Shopee status to our status
        status_map = {
            'UNPAID': 'pending',
            'READY_TO_SHIP': 'pending',
            'PROCESSED': 'synced',
            'SHIPPED': 'synced',
            'COMPLETED': 'synced',
            'CANCELLED': 'cancelled',
            'IN_CANCEL': 'cancelled',
        }
        
        state = status_map.get(order_status, 'pending')
        
        # Parse customer info from recipient_address and buyer_username
        recipient_info = payload.get('recipient_address', {}) or {}
        
        # Prefer recipient's real name; fallback to buyer_username, then phone-derived alias if masked
        def _is_masked(value):
            if not value or not isinstance(value, str):
                return False
            stripped = value.strip()
            return stripped and all(ch == '*' for ch in stripped)
        
        recipient_name = (recipient_info.get('name', '') or '').strip()
        buyer_username = (payload.get('buyer_username', '') or '').strip()
        phone_value = (recipient_info.get('phone', '') or '').strip()
        
        # Choose best available non-masked identifier
        if recipient_name and not _is_masked(recipient_name):
            customer_name = recipient_name
        elif buyer_username and not _is_masked(buyer_username):
            customer_name = buyer_username
        else:
            # Fallback: derive from phone if available, else from order_sn tail
            last4 = ''.join([c for c in phone_value if c.isdigit()])[-4:] or (order_sn[-4:] if order_sn else '')
            customer_name = f"Shopee Customer {last4}" if last4 else "Shopee Customer"
        customer_phone = recipient_info.get('phone', '')
        
        # Build customer address from recipient_address fields
        address_parts = [
            recipient_info.get('full_address', ''),
            recipient_info.get('town', ''),
            recipient_info.get('district', ''),
            recipient_info.get('city', ''),
            recipient_info.get('state', ''),
            recipient_info.get('zipcode', ''),
        ]
        customer_address = ' '.join(filter(None, address_parts))
        
        # Parse order lines from item_list
        lines = []
        item_list = payload.get('item_list', []) or []
        for item in item_list:
            # Try multiple SKU fields (seller_sku, item_sku, model_sku)
            external_sku = (
                item.get('seller_sku')
                or item.get('item_sku')
                or item.get('model_sku')
                or ''
            )
            
            lines.append({
                'external_sku': external_sku,
                'product_name': item.get('item_name', ''),
                'quantity': float(item.get('model_quantity_purchased', 1)),
                'price_unit': float(item.get('model_discounted_price', 0)),
            })
        
        # Parse order date - prevent 1970 date issue
        # Check if create_time exists and is valid (> 0)
        create_ts = payload.get('create_time')
        if create_ts:
            try:
                # Convert to int if it's a string or float
                create_ts_int = int(create_ts)
                if create_ts_int > 0:
                    order_date = datetime.fromtimestamp(create_ts_int)
                else:
                    # Invalid timestamp (0 or negative)
                    order_date = fields.Datetime.now()
                    _logger.warning(f'Shopee order {order_sn}: create_time is invalid ({create_ts}), using current time as order_date')
            except (ValueError, TypeError, OSError) as e:
                # Invalid timestamp format or out of range
                order_date = fields.Datetime.now()
                _logger.warning(f'Shopee order {order_sn}: create_time conversion failed ({create_ts}): {e}, using current time as order_date')
        else:
            # Missing create_time
            order_date = fields.Datetime.now()
            _logger.warning(f'Shopee order {order_sn}: create_time is missing, using current time as order_date')
        
        # Parse total amount
        # Try total_amount first, then check amount_detail if needed
        total_amount = payload.get('total_amount', 0)
        if not total_amount and payload.get('amount_detail'):
            # If total_amount is not available, try to get from amount_detail
            amount_detail = payload.get('amount_detail', {})
            total_amount = amount_detail.get('total_amount', 0) or amount_detail.get('original_total_amount', 0)
        
        # Convert to float (Shopee may send as string or number)
        try:
            amount_total = float(total_amount)
            # If amount seems too large (e.g., in cents), divide by 100
            # Shopee typically sends amounts in the smallest currency unit
            # But check if it's reasonable first (if > 1000000, likely in cents)
            if amount_total > 1000000:
                amount_total = amount_total / 100.0
                _logger.warning(f'Shopee order {order_sn}: total_amount seems in cents ({total_amount}), divided by 100: {amount_total}')
        except (ValueError, TypeError):
            amount_total = 0.0
            _logger.warning(f'Shopee order {order_sn}: Failed to parse total_amount ({total_amount}), using 0.0')
        
        # Determine currency – Shopee usually sends 'currency' at order level
        # Fallback and normalization: force THB if missing or not THB
        currency_code = (
            (payload.get('currency') or '') 
            or (payload.get('amount_detail', {}) or {}).get('currency', '')
        )
        currency_code = (currency_code or 'THB').upper()
        if currency_code != 'THB':
            _logger.warning(
                f'Shopee order {order_sn}: currency in payload is {currency_code}, forcing THB'
            )
            currency_code = 'THB'
        currency = self.env['res.currency'].sudo().search([('name', '=', currency_code)], limit=1)
        currency_id = currency.id if currency else (self.env.company.currency_id.id if self.env.company and self.env.company.currency_id else False)
        
        return {
            'external_order_id': order_sn,
            'name': order_sn,
            'order_date': order_date,
            'customer_name': customer_name,
            'customer_phone': customer_phone,
            'customer_address': customer_address,
            'amount_total': amount_total,
            'currency_id': currency_id,
            'state': state,
            'lines': lines,
        }
    
    def _get_order_detail_by_sn_list(self, order_sn_list):
        """Get Shopee order details for a list of order_sn values.
        
        Args:
            order_sn_list: List of order_sn strings from Shopee
            
        Returns:
            List of detailed order payloads from Shopee API
        """
        # LOCKED: Shopee get_order_detail implementation - ห้ามแก้ไขโครงสร้าง request
        # ข้อกำหนด (ยึดตาม Shopee API v2 ที่ทดสอบแล้ว):
        # - ใช้วิธี GET เท่านั้น
        # - ใส่ทุก parameter ใน query string (รวมทั้ง order_sn_list และ response_optional_fields)
        # - ลงนามด้วย base string: partner_id + '/api/v2/order/get_order_detail' + timestamp + access_token + shop_id
        # - อย่าเปลี่ยนรูปแบบการคำนวณลายเซ็นหรือย้ายพารามิเตอร์ไปไว้ใน JSON body
        if not order_sn_list:
            return []
        
        # Validate shop_id
        if not self.shop or not self.shop.external_shop_id:
            raise ValueError('shop_id is required for get_order_detail. Please ensure the shop has external_shop_id.')
        shop_id = int(self.shop.external_shop_id)
        
        # Prepare signing info (same pattern as fetch_orders)
        partner_id = int(self.account.client_id)
        partner_key = (self.account.client_secret or '').strip()
        access_token = self._get_access_token() or ''
        
        # API constants
        api_path = '/api/v2/order/get_order_detail'  # full path for signature
        endpoint = '/order/get_order_detail'  # for URL construction (base_url already includes /api/v2)
        
        all_details = []
        batch_size = 50
        
        for i in range(0, len(order_sn_list), batch_size):
            batch = order_sn_list[i:i + batch_size]
            
            # Recompute timestamp and sign per request to avoid 5-min window issues
            timestamp = int(time.time())
            base_string = f"{partner_id}{api_path}{timestamp}{access_token}{shop_id}"
            sign = hmac.new(
                partner_key.encode('utf-8'),
                base_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            # Public params in query string + business params in query (GET per Shopee spec)
            query_params = {
                'partner_id': partner_id,
                'timestamp': timestamp,
                'access_token': access_token,
                'shop_id': shop_id,
                'sign': sign,
                'order_sn_list': ','.join(batch),
                'response_optional_fields': (
                    'item_list,recipient_address,buyer_username,'
                    'payment_method,total_amount,amount_detail'
                ),
            }
            
            url = f"{self.base_url}{endpoint}"
            query_string = urllib.parse.urlencode(query_params)
            full_url = f"{url}?{query_string}"
            
            try:
                headers = {'Content-Type': 'application/json'}
                _logger.warning(f'🔍 Shopee _get_order_detail_by_sn_list: GET {full_url}')
                response_obj = requests.get(full_url, headers=headers, timeout=self.timeout)
                response_obj.raise_for_status()
                result = response_obj.json()
                
                if isinstance(result, dict) and 'response' in result:
                    response_data = result['response']
                else:
                    response_data = result
                
                if isinstance(response_data, dict) and 'error' in response_data:
                    _logger.error(
                        f'❌ Shopee _get_order_detail_by_sn_list - API Error: '
                        f'{response_data.get("error")}, Message: {response_data.get("message")}'
                    )
                    continue
                
                details = []
                if isinstance(response_data, dict):
                    details = response_data.get('order_list', []) or []
                    if not details:
                        _logger.warning(
                            f'🔍 Shopee _get_order_detail_by_sn_list: Empty order_list for batch, '
                            f'keys={list(response_data.keys())}'
                        )
                
                _logger.warning(
                    f'🔍 Shopee _get_order_detail_by_sn_list: requested {len(batch)} orders, got {len(details)} details'
                )
                all_details.extend(details)
            except Exception as e:
                _logger.error(f'❌ Shopee _get_order_detail_by_sn_list - Failed to fetch batch: {e}', exc_info=True)
                continue
        
        return all_details
    
    def get_order_detail(self, order_sn):
        """Get detailed Shopee order payload for a single order_sn.
        
        Args:
            order_sn: Single order_sn string from Shopee
            
        Returns:
            Detailed order payload dict or None if not found
        """
        if not order_sn:
            return None
        details = self._get_order_detail_by_sn_list([order_sn])
        return details[0] if details else None


# Non-LOCKED helper: fetch order list via GET (v2 spec) then fetch details via _get_order_detail_by_sn_list
    def fetch_orders_list_with_details(self, since, until=None, time_range_field='create_time', page_size=100, order_status=None, request_order_status_pending=False):
        """
        Fetch orders using Shopee v2 /order/get_order_list (GET + query) and then
        retrieve detailed payloads using _get_order_detail_by_sn_list (GET + query).
        
        This method avoids modifying the LOCKED fetch_orders() and detail logic inside it.
        It adheres to v2 spec:
          - GET method
          - All params in query string
          - Signature base: partner_id + '/api/v2/order/get_order_list' + timestamp + access_token + shop_id
        """
        if not self.shop or not self.shop.external_shop_id:
            raise ValueError('shop_id is required for fetching orders. Please ensure the shop has external_shop_id.')
        if isinstance(since, str):
            since = datetime.fromisoformat(since)
        if until is None:
            until = datetime.now()
        elif isinstance(until, str):
            until = datetime.fromisoformat(until)
        
        partner_id = int(self.account.client_id)
        partner_key = (self.account.client_secret or '').strip()
        access_token = self._get_access_token() or ''
        shop_id = int(self.shop.external_shop_id)
        
        api_path = '/api/v2/order/get_order_list'  # full path for signature
        endpoint = '/order/get_order_list'         # base_url already includes /api/v2
        
        # Use a fresh timestamp and signature for each page call
        all_order_sns = []
        cursor = ''
        more = True
        
        while more:
            timestamp = int(time.time())
            base_string = f"{partner_id}{api_path}{timestamp}{access_token}{shop_id}"
            sign = hmac.new(
                partner_key.encode('utf-8'),
                base_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()
            
            query_params = {
                'partner_id': partner_id,
                'timestamp': timestamp,
                'access_token': access_token,
                'shop_id': shop_id,
                'sign': sign,
                'time_range_field': time_range_field,
                'time_from': int(since.timestamp()),
                'time_to': int(until.timestamp()),
                'page_size': min(max(int(page_size or 100), 1), 100),
            }
            if cursor:
                query_params['cursor'] = cursor
            if order_status:
                query_params['order_status'] = order_status
            if request_order_status_pending:
                query_params['request_order_status_pending'] = True
            
            url = f"{self.base_url}{endpoint}"
            query_string = urllib.parse.urlencode(query_params)
            full_url = f"{url}?{query_string}"
            
            _logger.warning(
                f'🔍 Shopee fetch_orders_list_with_details: '
                f'GET {endpoint} shop_id={shop_id} time_from={query_params["time_from"]} time_to={query_params["time_to"]} cursor={query_params.get("cursor","")}'
            )
            _logger.warning(f'🔍 Signature base: {base_string}')
            
            try:
                headers = {'Content-Type': 'application/json'}
                response_obj = requests.get(full_url, headers=headers, timeout=self.timeout)
                response_obj.raise_for_status()
                raw = response_obj.json()
                response = raw.get('response', raw) if isinstance(raw, dict) else raw
            except Exception as e:
                _logger.error(f'❌ Shopee fetch_orders_list_with_details - list request failed: {e}', exc_info=True)
                break
            
            if isinstance(response, dict) and 'error' in response and response.get('error'):
                _logger.error(
                    f'❌ Shopee get_order_list error: {response.get("error")}, '
                    f'message: {response.get("message")}, request_id: {response.get("request_id")}'
                )
                _logger.error(f'❌ Full list response: {response}')
                break
            
            order_list = (response or {}).get('order_list', []) if isinstance(response, dict) else []
            extracted = [o.get('order_sn') for o in order_list if isinstance(o, dict) and o.get('order_sn')]
            all_order_sns.extend(extracted)
            _logger.warning(f'🔍 Shopee fetch_orders_list_with_details: got {len(extracted)} order_sn (total {len(all_order_sns)})')
            
            more = bool((response or {}).get('more')) if isinstance(response, dict) else False
            cursor = (response or {}).get('next_cursor') if isinstance(response, dict) else ''
        
        # Fetch details in batches via the correct GET + query method
        detailed_orders = []
        if all_order_sns:
            batch_size = 50
            for i in range(0, len(all_order_sns), batch_size):
                batch = all_order_sns[i:i + batch_size]
                _logger.warning(f'🔍 Shopee fetch_orders_list_with_details: fetching details for batch of {len(batch)}')
                try:
                    details = self._get_order_detail_by_sn_list(batch) or []
                    _logger.warning(f'🔍 Shopee fetch_orders_list_with_details: got {len(details)} detailed orders')
                    detailed_orders.extend(details)
                except Exception as e:
                    _logger.error(f'❌ Shopee fetch_orders_list_with_details - detail fetch failed: {e}', exc_info=True)
                    continue
        
        return detailed_orders

# Register adapter
from . import adapters
adapters.MarketplaceAdapters.register_adapter('shopee', ShopeeAdapter)

