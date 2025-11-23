# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

# LOCKED: Stable schema – ห้ามแก้ signature/logic ที่เป็นสัญญากับ client
class MarketplaceOAuthCallback(http.Controller):
    
    @http.route('/marketplace/oauth/callback/<string:channel>', 
                type='http', auth='public', methods=['GET'], csrf=False)
    def oauth_callback(self, channel, code=None, state=None, error=None, shop_id=None, **kwargs):
        """Handle OAuth callback from marketplace"""
        try:
            _logger.info(f'OAuth callback received - channel: {channel}, code: {code}, shop_id: {shop_id}, error: {error}')
            
            if error:
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': error,
                    'channel': channel,
                })
            
            if not code:
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': 'No authorization code received',
                    'channel': channel,
                })
            
            # Find account by state or client_id (simplified)
            # In production, use state to identify the account
            account = request.env['marketplace.account'].sudo().search([
                ('channel', '=', channel),
                ('active', '=', True),
            ], limit=1)
            
            if not account:
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': 'Account not found',
                    'channel': channel,
                })
            
            # Exchange code for tokens (pass shop_id if available)
            adapter = account._get_adapter(shop=None)  # No shop needed for token exchange
            
            try:
                token_data = adapter.exchange_code(code, shop_id=shop_id)
            except Exception as e:
                error_msg = f'Failed to exchange authorization code: {str(e)}'
                _logger.error(f'❌ OAuth Callback - Error exchanging code: {e}', exc_info=True)
                # Store error in account message for debugging
                account.message_post(body=f'OAuth Error: {error_msg}<br/>Code: {code[:20]}...<br/>Shop ID: {shop_id}')
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': error_msg,
                    'channel': channel,
                })
            
            # Log token_data for debugging
            _logger.error(f'🔍 OAuth Callback - Token Data: access_token={bool(token_data.get("access_token"))}, refresh_token={bool(token_data.get("refresh_token"))}, shop_id={token_data.get("shop_id")}')
            _logger.error(f'🔍 OAuth Callback - Token Data Full: {str(token_data)[:500]}')
            
            # Store token_data in account message for debugging
            account.message_post(body=f'OAuth Token Data:<br/>Access Token: {bool(token_data.get("access_token"))}<br/>Refresh Token: {bool(token_data.get("refresh_token"))}<br/>Shop ID: {token_data.get("shop_id")}<br/>Full Data: {str(token_data)[:500]}')
            
            # Get shop_id from token_data or callback parameter
            final_shop_id = token_data.get('shop_id') or shop_id
            
            # Update account with tokens
            access_token = token_data.get('access_token')
            refresh_token = token_data.get('refresh_token')
            
            _logger.error(f'🔍 OAuth Callback - Before write: access_token={bool(access_token)}, refresh_token={bool(refresh_token)}')
            _logger.error(f'🔍 OAuth Callback - Access Token Value: {access_token[:50] if access_token else "None"}...')
            _logger.error(f'🔍 OAuth Callback - Refresh Token Value: {refresh_token[:50] if refresh_token else "None"}...')
            
            # Check if tokens are None or empty
            if not access_token and not refresh_token:
                error_msg = f'No tokens received from Shopee API. Token Data: {str(token_data)[:500]}'
                _logger.error(f'❌ OAuth Callback - {error_msg}')
                account.message_post(body=f'OAuth Error: {error_msg}')
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': 'No tokens received from Shopee API. Please check the OAuth callback logs.',
                    'channel': channel,
                })
            
            try:
                account.write({
                    'access_token': access_token,
                    'refresh_token': refresh_token,
                    'access_token_expire_at': fields.Datetime.now() + timedelta(
                        seconds=token_data.get('expires_in', 3600)
                    ),
                })
                
                # Commit to ensure token is saved
                request.env.cr.commit()
                
                # Verify token was saved by reloading from database
                account.invalidate_recordset(['access_token', 'refresh_token'])
                # Reload account from database to get updated values
                account = request.env['marketplace.account'].sudo().browse(account.id)
                
                _logger.error(f'🔍 OAuth Callback - After write: access_token={bool(account.access_token)}, refresh_token={bool(account.refresh_token)}')
                
                if not account.access_token and access_token:
                    error_msg = f'Token was not saved! access_token was {access_token[:50] if access_token else "None"}, but account.access_token is {account.access_token}'
                    _logger.error(f'❌ OAuth Callback - {error_msg}')
                    account.message_post(body=f'OAuth Error: {error_msg}')
                elif account.access_token:
                    _logger.error(f'✅ OAuth Callback - Token saved successfully! access_token length: {len(account.access_token)}')
                    account.message_post(body=f'OAuth Success: Token saved successfully! Access Token Length: {len(account.access_token)}')
                    
            except Exception as e:
                error_msg = f'Failed to save tokens: {str(e)}'
                _logger.error(f'❌ OAuth Callback - Error writing tokens: {e}', exc_info=True)
                account.message_post(body=f'OAuth Error: {error_msg}')
                return request.render('otd_marketplace_stock.oauth_error', {
                    'error': error_msg,
                    'channel': channel,
                })
            
            # Auto-create shops after successful OAuth (Shopee specific requirement)
            shops_created = []
            shops_existing = []
            shop_errors = []
            
            # Always try to process the shop_id returned in the token payload/callback
            shop_ids_to_process = set()
            if final_shop_id:
                shop_ids_to_process.add(str(final_shop_id))
            
            # Fetch all partner shops from Shopee so every connected shop is created automatically
            shop_info_lookup = {}
            partner_shop_adapter = None
            try:
                partner_shop_adapter = account._get_adapter(shop=None)
            except Exception as adapter_error:
                _logger.warning(f'Could not initialize {account.channel} adapter after OAuth: {adapter_error}')
                shop_errors.append(f'Adapter init failed: {adapter_error}')
                partner_shop_adapter = None
            
            if account.channel == 'shopee' and partner_shop_adapter:
                try:
                    partner_shops_raw = partner_shop_adapter.get_shops()
                    partner_shops_list = []
                    
                    if isinstance(partner_shops_raw, list):
                        partner_shops_list = partner_shops_raw
                    elif isinstance(partner_shops_raw, dict):
                        if isinstance(partner_shops_raw.get('shops'), list):
                            partner_shops_list = partner_shops_raw.get('shops')
                        elif isinstance(partner_shops_raw.get('response'), dict):
                            response_block = partner_shops_raw.get('response', {})
                            if isinstance(response_block.get('shops'), list):
                                partner_shops_list = response_block.get('shops')
                    else:
                        _logger.debug(f'Shopee get_shops returned unexpected payload type: {type(partner_shops_raw)}')
                    
                    for shop_payload in partner_shops_list:
                        if not isinstance(shop_payload, dict):
                            continue
                        raw_shop_id = (shop_payload.get('shop_id') or
                                       shop_payload.get('shopId') or
                                       shop_payload.get('shopid'))
                        if not raw_shop_id:
                            continue
                        shop_id_str = str(raw_shop_id)
                        shop_ids_to_process.add(shop_id_str)
                        shop_info_lookup[shop_id_str] = shop_payload
                except Exception as e:
                    _logger.warning(f'Could not fetch Shopee partner shop list: {e}')
                    shop_errors.append(f'Fetch shop list failed: {e}')
            
            elif account.channel == 'lazada' and partner_shop_adapter:
                try:
                    lazada_seller_info = partner_shop_adapter.get_seller_info()
                    if isinstance(lazada_seller_info, dict) and lazada_seller_info:
                        lazada_shop_id = (
                            lazada_seller_info.get('shop_id') or
                            lazada_seller_info.get('seller_id') or
                            lazada_seller_info.get('user_id') or
                            lazada_seller_info.get('site_id') or
                            account.id
                        )
                        shop_id_str = str(lazada_shop_id)
                        shop_ids_to_process.add(shop_id_str)
                        shop_info_lookup[shop_id_str] = lazada_seller_info
                    else:
                        shop_errors.append('Lazada seller info not returned')
                except Exception as e:
                    _logger.warning(f'Could not fetch Lazada seller info: {e}')
                    shop_errors.append(f'Lazada seller info failed: {e}')
            
            # Create or update shop records based on collected shop IDs
            shop_model = request.env['marketplace.shop'].sudo()
            warehouse = request.env['stock.warehouse'].sudo().search([
                ('company_id', '=', account.company_id.id),
            ], limit=1)
            
            def _normalize_shop_info(payload):
                """Extract meaningful info from Shopee API responses"""
                if not isinstance(payload, dict):
                    return {}
                if 'data' in payload and isinstance(payload['data'], dict):
                    return payload['data']
                if 'shop_info' in payload and isinstance(payload['shop_info'], dict):
                    return payload['shop_info']
                return payload
            
            for external_shop_id in sorted(shop_ids_to_process):
                existing_shop = shop_model.search([
                    ('account_id', '=', account.id),
                    ('external_shop_id', '=', external_shop_id),
                ], limit=1)
                
                if existing_shop:
                    shops_existing.append(f'{existing_shop.name} ({external_shop_id})')
                    continue
                
                shop_info = _normalize_shop_info(shop_info_lookup.get(external_shop_id, {}))
                
                # If we do not have details yet, try fetching them now
                if account.channel == 'shopee' and partner_shop_adapter and not shop_info:
                    try:
                        fetched_info = partner_shop_adapter.get_shop_info(external_shop_id)
                        shop_info = _normalize_shop_info(fetched_info)
                    except Exception as e:
                        _logger.warning(f'Could not fetch Shopee shop info for {external_shop_id}: {e}')
                        shop_errors.append(f'Shop {external_shop_id}: fetch info failed ({e})')
                        shop_info = {}
                elif not shop_info:
                    # Fallback for other marketplaces (reuse previous behavior)
                    try:
                        temp_adapter = account._get_adapter(shop=None)
                        fetched_info = temp_adapter.get_shop_info(external_shop_id)
                        shop_info = _normalize_shop_info(fetched_info)
                    except Exception as e:
                        _logger.warning(f'Could not fetch shop info for {external_shop_id}: {e}')
                        shop_errors.append(f'Shop {external_shop_id}: fetch info failed ({e})')
                        shop_info = {}
                
                shop_name = (shop_info.get('shop_name') or
                             shop_info.get('name') or
                             f'{account.channel.title()} Shop {external_shop_id}')
                
                shop_vals = {
                    'name': shop_name,
                    'external_shop_id': external_shop_id,
                    'account_id': account.id,
                    'active': True,
                    'timezone': shop_info.get('timezone') or 'Asia/Bangkok',
                }
                
                if warehouse:
                    shop_vals['warehouse_id'] = warehouse.id
                
                shop = shop_model.create(shop_vals)
                shops_created.append(f'{shop.name} ({external_shop_id})')
                _logger.info(f'✅ Auto-created shop: {shop.name} (Shop ID: {external_shop_id})')
            
            # Log result
            message_lines = ['OAuth authorization successful']
            if final_shop_id:
                message_lines.append(f'Shop ID from callback: {final_shop_id}')
            if shops_created:
                message_lines.append('✅ Shop(s) created automatically: ' + ', '.join(shops_created))
            if shops_existing:
                message_lines.append('ℹ️ Shop(s) already existed: ' + ', '.join(shops_existing))
            if shop_errors:
                message_lines.append('⚠️ Shop sync warnings: ' + '; '.join(shop_errors))
            message = '\n'.join(message_lines)
            
            account.message_post(body=message)
            
            return request.render('otd_marketplace_stock.oauth_success', {
                'account': account,
                'channel': channel,
            })
            
        except Exception as e:
            _logger.error(f'OAuth callback error: {e}', exc_info=True)
            return request.render('otd_marketplace_stock.oauth_error', {
                'error': str(e),
                'channel': channel,
            })

    @http.route('/oauth/lazada/callback', type='http', auth='public', methods=['GET'], csrf=False)
    def oauth_callback_lazada_short(self, code=None, state=None, error=None, shop_id=None, **kwargs):
        """Backward-compatible route for Lazada callback without marketplace prefix"""
        return self.oauth_callback(
            'lazada',
            code=code,
            state=state,
            error=error,
            shop_id=shop_id,
            **kwargs,
        )

