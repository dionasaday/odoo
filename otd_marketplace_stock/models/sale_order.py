# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    """Extend sale.order to add marketplace order reference"""
    _inherit = 'sale.order'

    marketplace_order_id = fields.Many2one(
        'marketplace.order', string='Marketplace Order',
        ondelete='set null', readonly=True,
        help='Linked marketplace order'
    )
    marketplace_channel = fields.Selection(
        selection=[
            ('woocommerce', 'WooCommerce'),
            ('shopee', 'Shopee'),
            ('lazada', 'Lazada'),
            ('tiktok', 'TikTok Shop'),
            ('zortout', 'Zortout'),
        ],
        related='marketplace_order_id.channel', string='Marketplace Channel',
        readonly=True, store=True
    )
    marketplace_shop = fields.Many2one(
        related='marketplace_order_id.shop_id', string='Marketplace Shop',
        readonly=True, store=True
    )
    marketplace_channel_icon = fields.Html(
        string='Channel', compute='_compute_marketplace_channel_icon',
        store=False, sanitize=False
    )
    marketplace_channel_display = fields.Char(
        string='Channel', compute='_compute_marketplace_channel_display',
        store=False,
        help='Channel display name for list view (text only, no HTML)'
    )
    marketplace_order_number = fields.Char(
        string='Order Number', compute='_compute_marketplace_order_number',
        store=False,
        help='Marketplace order number (e.g., WooCommerce, Shopee, Lazada) or Odoo order number'
    )
    
    def _compute_marketplace_channel_icon(self):
        """Compute marketplace channel icon HTML with actual logos and shop name"""
        # Use CDN URLs for channel logos with fallback icons
        # WooCommerce logo: purple circle with "Woo" text
        channel_logos = {
            'woocommerce': {
                # WooCommerce logo: purple circle (#96588A) with "Woo" text in white
                # Using data URI for reliable display
                'url': 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjQiIGhlaWdodD0iMjQiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMTIiIGN5PSIxMiIgcj0iMTIiIGZpbGw9IiM5NjU4OEEiLz4KPHRleHQgeD0iMTIiIHk9IjE2IiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTAiIGZvbnQtd2VpZ2h0PSJib2xkIiBmaWxsPSJ3aGl0ZSIgdGV4dC1hbmNob3I9Im1pZGRsZSI+V29vPC90ZXh0Pgo8L3N2Zz4=',
                'alt': 'WooCommerce',
                'fallback_icon': 'fa-shopping-cart',
                'fallback_color': '#96588a',
                'style': 'height: 20px; width: 20px; vertical-align: middle; object-fit: contain; margin-right: 6px;'
            },
            'shopee': {
                'url': 'https://cf.shopee.co.th/file/4e515e0e1e8aa6daf9cac6f08c4cc94f',
                'alt': 'Shopee',
                'fallback_icon': 'fa-shopping-bag',
                'fallback_color': '#ee4d2d',
                'style': 'height: 20px; width: auto; vertical-align: middle; max-width: 80px; margin-right: 6px;'
            },
            'lazada': {
                'url': 'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PGRlZnM+PGxpbmVhckdyYWRpZW50IGlkPSJnIiB4MT0iMCUiIHkxPSIwJSIgeDI9IjEwMCUiIHkyPSIxMDAlIj48c3RvcCBvZmZzZXQ9IjAlIiBzdG9wLWNvbG9yPSIjZmY1ZjZkIi8+PHN0b3Agb2Zmc2V0PSIxMDAlIiBzdG9wLWNvbG9yPSIjODQ1ZWY3Ii8+PC9saW5lYXJHcmFkaWVudD48L2RlZnM+PHBhdGggZD0iTTEyIDJsNiA0djhsLTYgNC02LTRWNnoiIGZpbGw9InVybCgjZykiLz48cGF0aCBkPSJNOC41IDcuNWwzLjUgMmwzLjUtMnY0Ljc1TDEyIDE0bC0zLjUtMS43NXoiIGZpbGw9IiNmZmQ0M2IiLz48L3N2Zz4=',
                'alt': 'Lazada',
                'fallback_icon': 'fa-shopping-basket',
                'fallback_color': '#0f146d',
                'style': 'height: 20px; width: auto; vertical-align: middle; max-width: 80px; margin-right: 6px;'
            },
            'tiktok': {
                'url': 'https://sf16-website-login.neutral.ttwstatic.com/obj/tiktok_web_login_static/tiktok/webapp/main/webapp-desktop/8152caf0c8e8bc67ae0d.png',
                'alt': 'TikTok Shop',
                'fallback_icon': 'fa-video-camera',
                'fallback_color': '#000000',
                'style': 'height: 20px; width: auto; vertical-align: middle; max-width: 80px; margin-right: 6px;'
            },
            'zortout': {
                'url': 'https://www.zortout.com/wp-content/uploads/2021/06/zortout-logo.png',
                'alt': 'Zortout',
                'fallback_icon': 'fa-database',
                'fallback_color': '#007bff',
                'style': 'height: 20px; width: auto; vertical-align: middle; max-width: 80px; margin-right: 6px;'
            },
        }
        
        # Channel display names
        channel_names = {
            'woocommerce': 'WooCommerce',
            'shopee': 'Shopee',
            'lazada': 'Lazada',
            'tiktok': 'TikTok Shop',
            'zortout': 'Zortout',
        }
        
        for order in self:
            # Initialize with safe default value
            order.marketplace_channel_icon = '&nbsp;'
            try:
                # Priority: marketplace_channel (auto-mapped) > manual_marketplace_channel_id (manual selection)
                # Marketplace orders: channel is automatically mapped via marketplace_order_id.channel
                # Manual orders: can select channel via manual_marketplace_channel_id
                if order.marketplace_channel and order.marketplace_channel in channel_logos:
                    # Marketplace order: auto-map channel from marketplace_order_id
                    logo = channel_logos.get(order.marketplace_channel)
                    if not logo:
                        order.marketplace_channel_icon = ''
                        continue
                    
                    channel_display = channel_names.get(order.marketplace_channel, order.marketplace_channel)
                    
                    # Get shop name for display (safely access marketplace_shop)
                    shop_name = ''
                    if order.marketplace_shop and hasattr(order.marketplace_shop, 'name'):
                        try:
                            shop_name = order.marketplace_shop.name or ''
                        except Exception:
                            shop_name = ''
                    
                    if shop_name:
                        # Remove channel prefix if exists (e.g., "Lazada – " or "WooCommerce - " -> "")
                        # This makes the display cleaner: "Lazada – ON THIS DAY" -> "ON THIS DAY"
                        # Support both em dash (–) and hyphen (-)
                        if shop_name.startswith(f"{channel_display} – "):
                            shop_name = shop_name.replace(f"{channel_display} – ", "", 1)
                        elif shop_name.startswith(f"{channel_display} - "):
                            shop_name = shop_name.replace(f"{channel_display} - ", "", 1)
                        elif shop_name.startswith(f"{channel_display}–"):
                            shop_name = shop_name.replace(f"{channel_display}–", "", 1)
                        elif shop_name.startswith(f"{channel_display}-"):
                            shop_name = shop_name.replace(f"{channel_display}-", "", 1)
                    
                    # Display only shop name (without channel name prefix)
                    # Format: "ShopName" or just channel name if no shop
                    if shop_name and shop_name.strip():
                        display_text = shop_name.strip()
                    else:
                        display_text = channel_display
                    
                    # Ensure all logo properties exist
                    logo_url = logo.get('url', '')
                    logo_alt = logo.get('alt', channel_display)
                    logo_style = logo.get('style', '')
                    fallback_icon = logo.get('fallback_icon', 'fa-shopping-cart')
                    fallback_color = logo.get('fallback_color', '#333')
                    
                    order.marketplace_channel_icon = (
                        f'<span style="display: inline-flex; align-items: center; vertical-align: middle; gap: 6px;">'
                        f'<img src="{logo_url}" alt="{logo_alt}" title="{display_text}" '
                        f'style="{logo_style}" '
                        f'onerror="this.style.display=\'none\'; this.nextElementSibling.style.display=\'inline\';">'
                        f'<i class="fa {fallback_icon}" '
                        f'style="display:none; color: {fallback_color}; font-size: 16px; margin-right: 6px;" '
                        f'title="{display_text}"></i>'
                        f'<span style="font-size: 13px; color: #333;">{display_text}</span>'
                        f'</span>'
                    )
                elif order.manual_marketplace_channel_id:
                    # Manual order: show manually selected channel
                    try:
                        channel_display = order.manual_marketplace_channel_id.name or 'Channel'
                    except Exception:
                        channel_display = 'Channel'
                    
                    order.marketplace_channel_icon = (
                        f'<span style="display: inline-flex; align-items: center; vertical-align: middle; gap: 6px;">'
                        f'<span style="font-size: 13px; color: #333;">{channel_display}</span>'
                        f'</span>'
                    )
                else:
                    # No channel: neither marketplace nor manual
                    # Use non-breaking space to avoid JavaScript errors with empty HTML
                    order.marketplace_channel_icon = '&nbsp;'
            except Exception as e:
                # Fallback: set empty but safe value
                _logger.warning(f'Error computing marketplace_channel_icon for order {order.id}: {e}', exc_info=True)
                order.marketplace_channel_icon = '&nbsp;'

    @api.depends('marketplace_order_id', 'marketplace_channel', 'marketplace_shop', 'manual_marketplace_channel_id')
    def _compute_marketplace_channel_display(self):
        """Compute channel display name (text only, for list view)"""
        for order in self:
            # Initialize with empty string to avoid None
            order.marketplace_channel_display = ''
            
            try:
                # Priority: marketplace_channel > manual_marketplace_channel_id
                if order.marketplace_channel:
                    channel_value = str(order.marketplace_channel).strip() if order.marketplace_channel else ''
                    if not channel_value:
                        continue
                    
                    channel_display = channel_value.title()
                    
                    # Try to get shop name safely
                    shop_name = ''
                    if order.marketplace_shop:
                        try:
                            # Ensure marketplace_shop is a valid recordset
                            if hasattr(order.marketplace_shop, 'name') and order.marketplace_shop.exists():
                                shop_name = str(order.marketplace_shop.name or '').strip()
                        except (AttributeError, Exception):
                            shop_name = ''
                    
                    # Remove channel prefix if exists
                    if shop_name:
                        # Support various formats: "Lazada – ", "Lazada - ", "Lazada–", "Lazada-"
                        prefixes = [
                            f"{channel_display} – ",
                            f"{channel_display} - ",
                            f"{channel_display}–",
                            f"{channel_display}-",
                        ]
                        for prefix in prefixes:
                            if shop_name.startswith(prefix):
                                shop_name = shop_name[len(prefix):].strip()
                                break
                        
                        if shop_name:
                            order.marketplace_channel_display = shop_name
                        else:
                            order.marketplace_channel_display = channel_display
                    else:
                        order.marketplace_channel_display = channel_display
                        
                elif order.manual_marketplace_channel_id:
                    try:
                        if order.manual_marketplace_channel_id.exists():
                            manual_name = order.manual_marketplace_channel_id.name
                            order.marketplace_channel_display = str(manual_name).strip() if manual_name else ''
                        else:
                            order.marketplace_channel_display = ''
                    except (AttributeError, Exception):
                        order.marketplace_channel_display = ''
                else:
                    # No channel: set empty string (not None)
                    order.marketplace_channel_display = ''
                    
            except Exception as e:
                # Fallback: ensure we always have a string value
                _logger.warning(f'Error computing marketplace_channel_display for order {order.id}: {e}', exc_info=True)
                order.marketplace_channel_display = ''
            
            # Final safety check: ensure it's always a string
            if order.marketplace_channel_display is None:
                order.marketplace_channel_display = ''

    @api.depends('marketplace_order_id', 'name')
    def _compute_marketplace_order_number(self):
        """Compute order number: show marketplace order number if available, otherwise show Odoo order number"""
        for order in self:
            try:
                # Initialize with order name to avoid None
                order.marketplace_order_number = str(order.name or '')
                
                if order.marketplace_order_id:
                    try:
                        if order.marketplace_order_id.exists():
                            mo = order.marketplace_order_id
                            # Try external_order_id first, then name
                            if hasattr(mo, 'external_order_id') and mo.external_order_id:
                                order.marketplace_order_number = str(mo.external_order_id).strip()
                            elif hasattr(mo, 'name') and mo.name:
                                order.marketplace_order_number = str(mo.name).strip()
                    except (AttributeError, Exception):
                        # Fallback to order name
                        order.marketplace_order_number = str(order.name or '')
            except Exception as e:
                _logger.warning(f'Error computing marketplace_order_number for order {order.id}: {e}', exc_info=True)
                # Ensure we always have a string value
                order.marketplace_order_number = str(order.name or '')

