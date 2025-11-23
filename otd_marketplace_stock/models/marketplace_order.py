# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
try:
    from odoo.osv import expression
except ImportError:
    # Odoo 19+ uses odoo.fields.Domain instead
    from odoo.fields import Domain as expression
import logging
import json

_logger = logging.getLogger(__name__)


class MarketplaceOrder(models.Model):
    _name = 'marketplace.order'
    _description = 'Marketplace Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Order Number', required=True, index=True)
    external_order_id = fields.Char(
        string='External Order ID', required=True, index=True,
        help='Order ID from marketplace platform'
    )
    shop_id = fields.Many2one(
        'marketplace.shop', string='Shop', required=True,
        ondelete='restrict', tracking=True
    )
    account_id = fields.Many2one(
        related='shop_id.account_id', string='Account',
        readonly=True, store=True
    )
    channel = fields.Selection(
        related='shop_id.channel', string='Channel', readonly=True, store=True
    )
    company_id = fields.Many2one(
        related='shop_id.company_id', string='Company', readonly=True
    )
    
    # Order status
    state = fields.Selection([
        ('pending', 'Pending'),
        ('synced', 'Synced'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ], string='Status', default='pending', tracking=True)
    
    # Odoo sale order reference
    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order', ondelete='set null',
        tracking=True
    )
    sale_order_name = fields.Char(
        related='sale_order_id.name', string='SO Number', readonly=True
    )
    
    # Order details
    order_date = fields.Datetime(string='Order Date', required=True)
    customer_name = fields.Char(string='Customer Name')
    customer_email = fields.Char(string='Customer Email')
    customer_phone = fields.Char(string='Customer Phone')
    customer_address = fields.Text(string='Customer Address')
    
    # Amounts
    amount_total = fields.Monetary(
        string='Total Amount', currency_field='currency_id'
    )
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # Cancellation/Return
    cancellation_reason = fields.Text(string='Cancellation Reason')
    return_reason = fields.Text(string='Return Reason')
    cancellation_date = fields.Datetime(string='Cancellation Date')
    return_date = fields.Datetime(string='Return Date')
    
    # Raw data
    raw_payload = fields.Text(
        string='Raw Payload', readonly=True,
        help='Original JSON payload from marketplace'
    )
    
    # Order lines
    order_line_ids = fields.One2many(
        'marketplace.order.line', 'order_id', string='Order Lines'
    )
    
    # Sync tracking
    sync_error = fields.Text(string='Sync Error', readonly=True)
    last_sync_at = fields.Datetime(string='Last Sync At', readonly=True)

    @api.model
    def create_from_payload(self, shop, payload, channel):
        """Create marketplace order from API payload"""
        try:
            # Extract order data based on channel
            adapter = shop.account_id._get_adapter(shop)
            order_data = adapter.parse_order_payload(payload)
            
            # Check if order already exists
            existing = self.search([
                ('external_order_id', '=', order_data['external_order_id']),
                ('shop_id', '=', shop.id),
            ], limit=1)
            
            if existing:
                # Update existing order
                existing.write({
                    'raw_payload': json.dumps(payload, ensure_ascii=False),
                    'state': order_data.get('state', existing.state),
                })
                existing._sync_to_sale_order()
                return existing
            
            # Create new order
            order = self.create({
                'name': order_data.get('name', order_data['external_order_id']),
                'external_order_id': order_data['external_order_id'],
                'shop_id': shop.id,
                'order_date': order_data.get('order_date', fields.Datetime.now()),
                'customer_name': order_data.get('customer_name', ''),
                'customer_email': order_data.get('customer_email', ''),
                'customer_phone': order_data.get('customer_phone', ''),
                'customer_address': order_data.get('customer_address', ''),
                'amount_total': order_data.get('amount_total', 0.0),
                'currency_id': order_data.get('currency_id', self.env.company.currency_id.id),
                'state': order_data.get('state', 'pending'),
                'raw_payload': json.dumps(payload, ensure_ascii=False),
            })
            
            # Create order lines
            for line_data in order_data.get('lines', []):
                self.env['marketplace.order.line'].create({
                    'order_id': order.id,
                    'external_sku': line_data.get('external_sku'),
                    'product_name': line_data.get('product_name', ''),
                    'quantity': line_data.get('quantity', 1),
                    'price_unit': line_data.get('price_unit', 0.0),
                    'raw_data': json.dumps(line_data, ensure_ascii=False),
                })
            
            # Sync to sale order
            _logger.warning(f'🔍 create_from_payload: Syncing order {order.name} to sale order')
            order._sync_to_sale_order()
            _logger.warning(f'✅ create_from_payload: Successfully synced order {order.name} to sale order')
            
            return order
            
        except Exception as e:
            _logger.error(f'Failed to create order from payload: {e}', exc_info=True)
            raise

    @api.model
    def create_from_payloads_bulk(self, shop, payloads, channel, batch_size=50):
        """Create marketplace orders from multiple payloads (optimized with bulk operations)
        
        Args:
            shop: marketplace.shop record
            payloads: list of order payloads from marketplace API
            channel: marketplace channel (e.g., 'woocommerce', 'shopee')
            batch_size: number of orders to process per batch (for commit)
        
        Returns:
            dict with 'created', 'updated', 'errors' counts
        """
        if not payloads:
            return {'created': 0, 'updated': 0, 'errors': 0}
        
        adapter = shop.account_id._get_adapter(shop)
        
        # Step 1: Parse all payloads (must be done individually)
        order_data_list = []
        for payload in payloads:
            try:
                order_data = adapter.parse_order_payload(payload)
                order_data['_payload'] = payload  # Store original payload
                order_data_list.append(order_data)
            except Exception as e:
                _logger.error(f'Failed to parse order payload: {e}', exc_info=True)
                continue
        
        if not order_data_list:
            return {'created': 0, 'updated': 0, 'errors': len(payloads)}
        
        # Step 2: Bulk check for existing orders (1 query instead of N queries)
        external_order_ids = [od['external_order_id'] for od in order_data_list]
        existing_orders = self.search([
            ('external_order_id', 'in', external_order_ids),
            ('shop_id', '=', shop.id),
        ])
        
        # Create mapping: external_order_id -> existing order
        existing_map = {order.external_order_id: order for order in existing_orders}
        
        # Step 3: Separate new and existing orders
        new_orders_data = []
        update_orders = []
        
        for order_data in order_data_list:
            external_id = order_data['external_order_id']
            if external_id in existing_map:
                update_orders.append((existing_map[external_id], order_data))
            else:
                new_orders_data.append(order_data)
        
        # Step 4: Update existing orders
        updated_count = 0
        for existing_order, order_data in update_orders:
            try:
                existing_order.write({
                    'raw_payload': json.dumps(order_data['_payload'], ensure_ascii=False),
                    'state': order_data.get('state', existing_order.state),
                })
                updated_count += 1
            except Exception as e:
                _logger.error(f'Failed to update order {existing_order.name}: {e}', exc_info=True)
        
        # Step 5: Bulk create new orders (batch by batch)
        created_count = 0
        error_count = 0
        currency_id = self.env.company.currency_id.id
        all_new_orders = []  # Store all newly created orders for sync
        
        for batch_start in range(0, len(new_orders_data), batch_size):
            batch_data = new_orders_data[batch_start:batch_start + batch_size]
            
            # Prepare order vals for bulk create
            order_vals_list = []
            order_lines_map = {}  # order_index -> list of line_data
            
            for idx, order_data in enumerate(batch_data):
                order_vals_list.append({
                    'name': order_data.get('name', order_data['external_order_id']),
                    'external_order_id': order_data['external_order_id'],
                    'shop_id': shop.id,
                    'order_date': order_data.get('order_date', fields.Datetime.now()),
                    'customer_name': order_data.get('customer_name', ''),
                    'customer_email': order_data.get('customer_email', ''),
                    'customer_phone': order_data.get('customer_phone', ''),
                    'customer_address': order_data.get('customer_address', ''),
                    'amount_total': order_data.get('amount_total', 0.0),
                    'currency_id': order_data.get('currency_id', currency_id),
                    'state': order_data.get('state', 'pending'),
                    'raw_payload': json.dumps(order_data['_payload'], ensure_ascii=False),
                })
                order_lines_map[idx] = order_data.get('lines', [])
            
            try:
                # Bulk create orders
                new_orders = self.create(order_vals_list)
                all_new_orders.extend(new_orders)
                
                # Bulk create order lines
                line_vals_list = []
                for order_idx, order in enumerate(new_orders):
                    lines_data = order_lines_map[order_idx]
                    for line_data in lines_data:
                        line_vals_list.append({
                            'order_id': order.id,
                            'external_sku': line_data.get('external_sku'),
                            'product_name': line_data.get('product_name', ''),
                            'quantity': line_data.get('quantity', 1),
                            'price_unit': line_data.get('price_unit', 0.0),
                            'raw_data': json.dumps(line_data, ensure_ascii=False),
                        })
                
                if line_vals_list:
                    self.env['marketplace.order.line'].create(line_vals_list)
                
                created_count += len(new_orders)
                
                # Commit batch
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(f'Failed to create batch of orders: {e}', exc_info=True)
                error_count += len(batch_data)
                # Continue with next batch
        
        # Step 6: Bulk sync to sale orders (optimized)
        # Sync existing orders that were updated
        if update_orders:
            orders_to_sync = self.browse([order.id for order, _ in update_orders])
            try:
                self._sync_orders_to_sale_orders_bulk(orders_to_sync)
            except Exception as e:
                _logger.error(f'Failed to bulk sync updated orders: {e}', exc_info=True)
                # Fallback to individual sync
                for existing_order, _ in update_orders:
                    try:
                        existing_order._sync_to_sale_order()
                    except Exception as sync_error:
                        _logger.error(f'Failed to sync updated order {existing_order.name}: {sync_error}', exc_info=True)
        
        # Sync newly created orders using bulk operations
        if all_new_orders:
            _logger.warning(f'🔍 create_from_payloads_bulk: Syncing {len(all_new_orders)} new orders to sale orders')
            try:
                # Convert list to recordset before calling bulk sync
                new_orders_recordset = self.browse([order.id for order in all_new_orders])
                self._sync_orders_to_sale_orders_bulk(new_orders_recordset)
                _logger.warning(f'✅ create_from_payloads_bulk: Successfully synced {len(all_new_orders)} orders to sale orders')
            except Exception as e:
                _logger.error(f'Failed to bulk sync new orders: {e}', exc_info=True)
                # Fallback to individual sync in batches
                sync_batch_size = 10
                for sync_batch_start in range(0, len(all_new_orders), sync_batch_size):
                    sync_batch = all_new_orders[sync_batch_start:sync_batch_start + sync_batch_size]
                    for order in sync_batch:
                        try:
                            order._sync_to_sale_order()
                        except Exception as sync_error:
                            _logger.error(f'Failed to sync new order {order.name}: {sync_error}', exc_info=True)
                    # Commit after each sync batch
                    self.env.cr.commit()
        
        return {
            'created': created_count,
            'updated': updated_count,
            'errors': error_count,
        }

    def _sync_to_sale_order(self):
        """Sync marketplace order to Odoo sale order"""
        for order in self:
            if order.state in ('cancelled', 'returned'):
                _logger.warning(f'🔍 _sync_to_sale_order: Skipping order {order.name} (state: {order.state})')
                continue
            
            _logger.warning(f'🔍 _sync_to_sale_order: Processing order {order.name} (sale_order_id: {order.sale_order_id.id if order.sale_order_id else None})')
            try:
                if order.sale_order_id:
                    # Update existing
                    _logger.warning(f'🔍 _sync_to_sale_order: Updating existing sale order {order.sale_order_id.name}')
                    order._update_sale_order()
                else:
                    # Create new
                    _logger.warning(f'🔍 _sync_to_sale_order: Creating new sale order for {order.name}')
                    sale_order = order._create_sale_order()
                    _logger.warning(f'✅ _sync_to_sale_order: Successfully created sale order {sale_order.name} for marketplace order {order.name}')
                
                order.write({
                    'state': 'synced',
                    'last_sync_at': fields.Datetime.now(),
                    'sync_error': False,
                })
                
            except Exception as e:
                _logger.error(f'❌ Failed to sync order {order.name}: {e}', exc_info=True)
                order.write({
                    'state': 'failed',
                    'sync_error': str(e),
                })
    
    def _sync_orders_to_sale_orders_bulk(self, orders):
        """Bulk sync marketplace orders to sale orders (optimized)
        
        Args:
            orders: list of marketplace.order records
        """
        if not orders:
            _logger.warning('🔍 _sync_orders_to_sale_orders_bulk: No orders provided')
            return
        
        _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: Processing {len(orders)} orders')
        
        # Filter out cancelled/returned orders
        orders_to_sync = orders.filtered(lambda o: o.state not in ('cancelled', 'returned'))
        if not orders_to_sync:
            _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: No orders to sync after filtering (all cancelled/returned)')
            return
        
        _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: {len(orders_to_sync)} orders to sync after filtering')
        
        # Step 1: Bulk lookup/create partners (optimized)
        partner_map = self._bulk_get_or_create_partners(orders_to_sync)
        
        # Step 2: Bulk lookup/create products for all order lines
        self._bulk_prepare_products_for_orders(orders_to_sync)
        
        # Step 3: Separate orders to create and update
        orders_to_create = orders_to_sync.filtered(lambda o: not o.sale_order_id)
        orders_to_update = orders_to_sync.filtered(lambda o: o.sale_order_id)
        relinked_orders = self.env['marketplace.order']
        
        _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: {len(orders_to_create)} orders to create, {len(orders_to_update)} orders to update')
        
        # Step 4: Bulk update existing sale orders
        if orders_to_update:
            for order in orders_to_update:
                try:
                    partner = partner_map.get(order.id)
                    if partner and order.sale_order_id.partner_id != partner:
                        order.sale_order_id.partner_id = partner.id
                except Exception as e:
                    _logger.error(f'Failed to update sale order for {order.name}: {e}', exc_info=True)
        
        # Step 5: Bulk create new sale orders
        if orders_to_create:
            fallback_currency_id = self.env.company.currency_id.id
            
            # Prepare sale order vals
            sale_order_vals_list = []
            order_line_map = {}  # order_id -> list of line_vals
            order_name_map = {}  # order_id -> expected_order_name (for correction after create)
            orders_ready_to_create = []
            
            for order in orders_to_create:
                partner = partner_map.get(order.id)
                if not partner:
                    _logger.warning(f'No partner found for order {order.name}, skipping')
                    continue
                
                # Guard against duplicate sale orders (e.g., when sync retried)
                existing_sale_order = self.env['sale.order'].search([
                    ('origin', '=', f'{order.channel}: {order.name}'),
                    ('state', '!=', 'cancel'),
                ], limit=1)
                if existing_sale_order:
                    order.sale_order_id = existing_sale_order.id
                    if order.external_order_id and existing_sale_order.name != order.external_order_id:
                        existing_sale_order.name = order.external_order_id
                    if existing_sale_order.marketplace_order_id != order:
                        existing_sale_order.marketplace_order_id = order.id
                    if partner and existing_sale_order.partner_id != partner:
                        existing_sale_order.partner_id = partner.id
                    relinked_orders |= order
                    continue
                
                company_id = order.company_id.id or self.env.company.id
                currency_id = (
                    order.currency_id.id
                    if order.currency_id
                    else (
                        order.company_id.currency_id.id
                        if order.company_id and order.company_id.currency_id
                        else fallback_currency_id
                    )
                )
                
                # Use external_order_id as name for marketplace orders to match Lazada/Shopee order numbers
                order_name = order.external_order_id or order.name or '/'
                # Use default_user_id from context (set by cron) if available, otherwise fallback to team_id.user_id
                default_user_id = self.env.context.get('default_user_id')
                user_id = default_user_id if default_user_id else (order.shop_id.team_id.user_id.id if order.shop_id.team_id else False)
                sale_order_vals_list.append({
                    'name': order_name,
                    'partner_id': partner.id,
                    'date_order': order.order_date,
                    'user_id': user_id,
                    'team_id': order.shop_id.team_id.id if order.shop_id.team_id else False,
                    'pricelist_id': order.account_id.order_default_pricelist_id.id if order.account_id.order_default_pricelist_id else False,
                    'origin': f'{order.channel}: {order.name}',
                    'company_id': company_id,
                    'currency_id': currency_id,
                    'marketplace_channel': order.shop_id.channel if order.shop_id and order.shop_id.channel else False,
                    'marketplace_shop': order.shop_id.id if order.shop_id else False,
                })
                # Store order_name mapping for later correction if sequence overrides
                order_name_map[order.id] = order_name
                
                # Prepare order lines
                line_vals_list = []
                _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: Order {order.name} has {len(order.order_line_ids)} marketplace lines before creating sale order')
                for line in order.order_line_ids:
                    # Get product from binding or ensure it exists
                    target_company_id = company_id or self.env.company.id
                    product = line._ensure_product_for_company(target_company_id)
                    if not product:
                        _logger.warning(f'No product found for SKU {line.external_sku} in order {order.name}, skipping line')
                        continue
                    
                    line_vals_list.append({
                        'product_id': product.id,
                        'name': line.product_name,
                        'product_uom_qty': line.quantity,
                        'price_unit': line.price_unit,
                        'sequence': len(line_vals_list) + 1,  # Set sequence to ensure order lines are displayed
                    })
                
                if line_vals_list:
                    order_line_map[order.id] = line_vals_list
                
                orders_ready_to_create.append(order)
            
            # Bulk create sale orders
            if sale_order_vals_list:
                _logger.warning(f'🔍 _sync_orders_to_sale_orders_bulk: Creating {len(sale_order_vals_list)} sale orders')
                try:
                    sale_orders = self.env['sale.order'].create(sale_order_vals_list)
                    _logger.warning(f'✅ _sync_orders_to_sale_orders_bulk: Successfully created {len(sale_orders)} sale orders')
                    
                    # Ensure name is set correctly (in case sequence overrides it)
                    for sale_order, order in zip(sale_orders, orders_ready_to_create):
                        expected_name = order_name_map.get(order.id)
                        if expected_name and expected_name != '/' and sale_order.name != expected_name:
                            sale_order.write({'name': expected_name})
                    
                    # Bulk create sale order lines
                    all_line_vals = []
                    for sale_order, order in zip(sale_orders, orders_ready_to_create):
                        if order.id in order_line_map:
                            line_vals = order_line_map[order.id]
                            for line_val in line_vals:
                                line_val['order_id'] = sale_order.id
                                all_line_vals.append(line_val)
                            
                            # Link marketplace order to sale order (bidirectional)
                            order.sale_order_id = sale_order.id
                            sale_order.marketplace_order_id = order.id
                    
                    if all_line_vals:
                        self.env['sale.order.line'].create(all_line_vals)
                    
                    # Log sale order lines after creation
                    for sale_order in sale_orders:
                        _logger.warning(f'✅ _sync_orders_to_sale_orders_bulk: Sale order {sale_order.name} created with {len(sale_order.order_line)} lines')
                    
                    # Auto confirm if enabled
                    account = orders_to_create[0].account_id if orders_to_create else None
                    if account and account.order_auto_confirm:
                        for sale_order in sale_orders:
                            try:
                                sale_order.action_confirm()
                            except Exception as e:
                                _logger.error(f'Failed to confirm sale order {sale_order.name}: {e}', exc_info=True)
                    
                    # Commit after bulk create
                    self.env.cr.commit()
                    
                except Exception as e:
                    _logger.error(f'Failed to bulk create sale orders: {e}', exc_info=True)
                    raise
        
        # Sync orders that were linked to existing sale orders
        if relinked_orders:
            for order in relinked_orders:
                try:
                    order._sync_to_sale_order()
                except Exception as e:
                    _logger.error(f'Failed to sync relinked order {order.name}: {e}', exc_info=True)
        
        # Step 6: Update sync status for all orders
        now = fields.Datetime.now()
        orders_to_sync.write({
            'state': 'synced',
            'last_sync_at': now,
            'sync_error': False,
        })
        self.env.cr.commit()
    
    def _bulk_get_or_create_partners(self, orders):
        """Bulk get or create partners for orders (optimized)
        
        Args:
            orders: list of marketplace.order records
        
        Returns:
            dict: {order_id: partner_record}
        """
        # LOCKED: Partner resolution rules for Shopee orders (Do NOT modify)
        # - Always cleanse masked placeholders (e.g., "****") before any matching
        # - Matching priority MUST be: name > email > phone
        # - Enforce company consistency:
        #   * If existing partner has different company_id, create a new partner for this company
        #   * If existing partner has company_id = False, update it to match order's company_id
        # - Keep addresses and names as provided by the latest payload parsing logic
        # Any change to these invariants can re-introduce duplicated/incorrect customer names in sale orders.
        partner_map = {}
        if not orders:
            return partner_map
        
        # Helper to detect masked placeholders like "****"
        def _is_masked(value):
            if not value or not isinstance(value, str):
                return False
            stripped = value.strip()
            return bool(stripped) and all(ch == '*' for ch in stripped)
        
        # Collect all customer identifiers (cleansed)
        customer_data = []
        for order in orders:
            name_val = (order.customer_name or '').strip()
            email_val = (order.customer_email or '').strip()
            phone_val = (order.customer_phone or '').strip()
            if _is_masked(name_val):
                name_val = ''
            if _is_masked(email_val):
                email_val = ''
            if _is_masked(phone_val):
                phone_val = ''
            customer_data.append({
                'order_id': order.id,
                'email': email_val or '',
                'phone': phone_val or '',
                'name': name_val or 'Marketplace Customer',
                'address': (order.customer_address or '').strip() or '',
                'company_id': order.company_id.id,
            })
        
        # Build a company filter domain used across lookups
        company_ids = list(set(cd['company_id'] for cd in customer_data if cd['company_id']))
        company_domain = [('company_id', 'in', [False] + company_ids)] if company_ids else []
        
        # Bulk lookup existing partners by NAME (preferred)
        names = [cd['name'] for cd in customer_data if cd['name']]
        existing_partners_by_name = {}
        if names:
            partners = self.env['res.partner'].search(
                [('name', 'in', list(set(names)))] + company_domain
            )
            existing_partners_by_name = {p.name: p for p in partners}
        
        # Bulk lookup existing partners by EMAIL (fallback 2)
        emails = [cd['email'] for cd in customer_data if cd['email']]
        existing_partners_by_email = {}
        if emails:
            partners = self.env['res.partner'].search(
                [('email', 'in', list(set(emails)))] + company_domain
            )
            existing_partners_by_email = {p.email: p for p in partners if p.email}
        
        # Bulk lookup existing partners by PHONE (fallback 3)
        phones = [cd['phone'] for cd in customer_data if cd['phone']]
        existing_partners_by_phone = {}
        if phones:
            partners = self.env['res.partner'].search(
                [('phone', 'in', list(set(phones)))] + company_domain
            )
            existing_partners_by_phone = {p.phone: p for p in partners if p.phone}
        
        # Map customers to partners (existing or new)
        partners_to_create = []
        customer_to_partner_map = {}
        
        for cd in customer_data:
            partner = None
            
            # Prefer name -> email -> phone
            if cd['name'] and cd['name'] in existing_partners_by_name:
                partner = existing_partners_by_name[cd['name']]
            elif cd['email'] and cd['email'] in existing_partners_by_email:
                partner = existing_partners_by_email[cd['email']]
            elif cd['phone'] and cd['phone'] in existing_partners_by_phone:
                partner = existing_partners_by_phone[cd['phone']]
            
            # Check company consistency: if partner found but company_id doesn't match, create new partner
            if partner:
                order_company_id = cd['company_id']
                partner_company_id = partner.company_id.id if partner.company_id else False
                
                # If partner has a specific company_id that doesn't match order's company_id, create new partner
                # If partner has company_id=False (shared), update it to match order's company_id
                if partner_company_id and order_company_id and partner_company_id != order_company_id:
                    # Partner belongs to different company, create new partner for this order
                    partner = None
                elif not partner_company_id and order_company_id:
                    # Partner is shared (company_id=False), update to match order's company_id
                    try:
                        partner.write({'company_id': order_company_id})
                    except Exception as e:
                        _logger.warning(f'Failed to update partner {partner.id} company_id: {e}, creating new partner')
                        partner = None
            
            if partner:
                partner_map[cd['order_id']] = partner
            else:
                # Prepare partner for creation
                partner_vals = {
                    'name': cd['name'] or 'Marketplace Customer',
                    'email': cd['email'] or False,
                    'phone': cd['phone'] or False,
                    'street': cd['address'] or False,
                    'company_id': cd['company_id'],
                    'is_company': False,
                }
                partners_to_create.append((cd['order_id'], partner_vals))
        
        # Bulk create new partners
        if partners_to_create:
            try:
                # Prepare partner vals list for bulk create
                partner_vals_list = [pv for _, pv in partners_to_create]
                created_partners = self.env['res.partner'].create(partner_vals_list)
                
                # Map order_id to partner
                for (order_id, _), partner in zip(partners_to_create, created_partners):
                    partner_map[order_id] = partner
                
                # Commit after bulk create
                self.env.cr.commit()
                
            except Exception as e:
                _logger.error(f'Failed to bulk create partners: {e}', exc_info=True)
                # Fallback to individual create
                for order_id, partner_vals in partners_to_create:
                    try:
                        partner = self.env['res.partner'].create(partner_vals)
                        partner_map[order_id] = partner
                    except Exception as create_error:
                        _logger.error(f'Failed to create partner for order {order_id}: {create_error}', exc_info=True)
        
        return partner_map
    def _create_sale_order(self):
        """Create sale order from marketplace order"""
        self.ensure_one()
        
        # Find or create partner
        partner = self._get_or_create_partner()
        
        # Prepare order values
        # Use external_order_id as name for marketplace orders to match Lazada/Shopee order numbers
        order_name = self.external_order_id or self.name or '/'
        # Use default_user_id from context (set by cron) if available, otherwise fallback to team_id.user_id
        default_user_id = self.env.context.get('default_user_id')
        user_id = default_user_id if default_user_id else (self.shop_id.team_id.user_id.id if self.shop_id.team_id else False)
        order_vals = {
            'name': order_name,
            'partner_id': partner.id,
            'date_order': self.order_date,
            'user_id': user_id,
            'team_id': self.shop_id.team_id.id if self.shop_id.team_id else False,
            'pricelist_id': self.account_id.order_default_pricelist_id.id if self.account_id.order_default_pricelist_id else False,
            'origin': f'{self.channel}: {self.name}',
            'company_id': self.company_id.id,
            'marketplace_channel': self.shop_id.channel if self.shop_id and self.shop_id.channel else False,
            'marketplace_shop': self.shop_id.id if self.shop_id else False,
        }
        
        # Log marketplace order lines before creating sale order
        _logger.warning(f'🔍 _create_sale_order: order {self.name} has {len(self.order_line_ids)} marketplace lines before create')
        
        # Create sale order with explicit name to prevent sequence override
        sale_order = self.env['sale.order'].with_context(default_name=order_name).create(order_vals)
        
        # Ensure name is set correctly (in case sequence overrides it)
        if order_name != '/' and sale_order.name != order_name:
            sale_order.write({'name': order_name})
        
        # Create order lines
        for line in self.order_line_ids:
            line._create_sale_order_line(sale_order)
        
        # Log sale order lines after creation
        _logger.warning(f'✅ _create_sale_order: sale order {sale_order.name} created with {len(sale_order.order_line)} lines')
        
        # Link to marketplace order (bidirectional)
        self.sale_order_id = sale_order.id
        sale_order.marketplace_order_id = self.id
        
        # Auto confirm if enabled
        if self.account_id.order_auto_confirm:
            sale_order.action_confirm()
        
        return sale_order

    def _update_sale_order(self):
        """Update existing sale order"""
        self.ensure_one()
        if not self.sale_order_id:
            return
        
        # Update partner if needed
        partner = self._get_or_create_partner()
        if self.sale_order_id.partner_id != partner:
            self.sale_order_id.partner_id = partner.id

    def _get_or_create_partner(self):
        """Get or create customer partner"""
        self.ensure_one()
        
        def _is_masked(value):
            if not value or not isinstance(value, str):
                return False
            stripped = value.strip()
            return bool(stripped) and all(ch == '*' for ch in stripped)
        
        # Normalize incoming values and ignore masked placeholders (e.g. "****")
        name_value = (self.customer_name or '').strip()
        email_value = (self.customer_email or '').strip()
        phone_value = (self.customer_phone or '').strip()
        
        if _is_masked(name_value):
            name_value = ''
        if _is_masked(email_value):
            email_value = ''
        if _is_masked(phone_value):
            phone_value = ''
        
        # Prefer matching by recipient real name; then fallback to email, then phone
        # Add company constraint for consistency
        order_company_id = self.company_id.id if self.company_id else False
        company_domain = [('company_id', 'in', [False, order_company_id])] if order_company_id else []
        
        Partner = self.env['res.partner']
        partner = None
        
        if name_value:
            domain = [('name', '=', name_value)] + company_domain
            partner = Partner.search(domain, limit=1)
        
        if not partner and email_value:
            domain = [('email', '=', email_value)] + company_domain
            partner = Partner.search(domain, limit=1)
        
        if not partner and phone_value:
            domain = [('phone', '=', phone_value)] + company_domain
            partner = Partner.search(domain, limit=1)
        
        # If partner found but company mismatch, create a dedicated partner for this company
        if partner:
            partner_company_id = partner.company_id.id if partner.company_id else False
            if partner_company_id and order_company_id and partner_company_id != order_company_id:
                partner = None
            elif not partner_company_id and order_company_id:
                try:
                    partner.write({'company_id': order_company_id})
                except Exception as e:
                    _logger.warning(f'Failed to update partner {partner.id} company_id: {e}, creating new partner')
                    partner = None
        
        if not partner:
            partner = Partner.create({
                'name': name_value or 'Marketplace Customer',
                'email': email_value or False,
                'phone': phone_value or False,
                'street': (self.customer_address or '').strip() or False,
                'company_id': order_company_id,
                'is_company': False,
            })
        
        return partner
    
    def _bulk_prepare_products_for_orders(self, orders):
        """Bulk prepare products for all order lines (optimized)
        
        Args:
            orders: list of marketplace.order records
        
        This method ensures all products and bindings exist before syncing to sale orders.
        """
        # Get all order lines (ensure each SKU binding matches the order's company)
        all_lines = orders.mapped('order_line_ids').filtered(lambda l: l.external_sku)
        if not all_lines:
            return
        
        # Group lines by SKU and shop
        sku_shop_map = {}  # (sku, shop_id) -> list of lines
        for line in all_lines:
            key = (line.external_sku, line.order_id.shop_id.id)
            if key not in sku_shop_map:
                sku_shop_map[key] = []
            sku_shop_map[key].append(line)
        
        # Bulk lookup existing products by SKU
        all_skus = list(set(line.external_sku for line in all_lines))
        company_ids = list({
            line.order_id.company_id.id
            for line in all_lines
            if line.order_id.company_id
        })
        existing_products = {}
        if all_skus:
            domain = [('default_code', 'in', all_skus)]
            if company_ids:
                domain.append(('company_id', 'in', company_ids + [False]))
            products = self.env['product.product'].search(domain)
            for product in products:
                if not product.default_code:
                    continue
                company_key = product.company_id.id or 0
                existing_products.setdefault(product.default_code, {})[company_key] = product
        
        # Bulk lookup existing bindings
        all_shop_ids = list(set(line.order_id.shop_id.id for line in all_lines))
        existing_bindings = {}
        if all_shop_ids and all_skus:
            bindings = self.env['marketplace.product.binding'].search([
                ('external_sku', 'in', all_skus),
                ('shop_id', 'in', all_shop_ids),
                ('active', '=', True),
            ])
            existing_bindings = {(b.external_sku, b.shop_id.id): b for b in bindings}
        
        # Process each SKU-shop combination
        products_to_create = []
        bindings_to_create = []
        
        bindings_to_update = []
        
        for (sku, shop_id), lines in sku_shop_map.items():
            target_company_id = lines[0].order_id.company_id.id if lines[0].order_id.company_id else False
            product = None
            binding = existing_bindings.get((sku, shop_id))
            
            if binding and binding.product_id:
                binding_company_id = binding.product_id.company_id.id if binding.product_id.company_id else False
                if not target_company_id or binding_company_id in (False, target_company_id):
                    product = binding.product_id
                else:
                    product = None
            
            if not product:
                product_map = existing_products.get(sku, {})
                if target_company_id:
                    product = product_map.get(target_company_id)
                if not product:
                    product = product_map.get(0)
            
            if not product:
                # Product doesn't exist yet for this company; queue creation
                line = lines[0]
                product_company_id = target_company_id or self.env.company.id
                products_to_create.append({
                    'sku': sku,
                    'name': line.product_name or f'Product {sku}',
                    'price': line.price_unit or 0.0,
                    'company_id': product_company_id,
                    'shop_id': shop_id,
                    'lines': lines,
                    'binding': binding,
                })
                continue
            
            if binding:
                if binding.product_id != product:
                    bindings_to_update.append({
                        'binding': binding,
                        'product': product,
                        'lines': lines,
                    })
                else:
                    for line in lines:
                        line.product_binding_id = binding.id
                continue
            
            # No binding exists; create one after loop
            bindings_to_create.append({
                'product_id': product.id,
                'shop_id': shop_id,
                'external_sku': sku,
                'lines': lines,
            })
        
        # Bulk create products
        if products_to_create:
            # Get default UOM and category
            uom_id = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
            if not uom_id:
                uom_id = self.env['uom.uom'].search([('name', '=', 'Units')], limit=1)
            if not uom_id:
                uom_id = self.env['uom.uom'].search([], limit=1)
            
            categ = self.env.ref('product.product_category_all', raise_if_not_found=False)
            if not categ:
                categ = self.env['product.category'].search([], limit=1)
            
            # Create product templates
            template_vals_list = []
            product_data_map = {}  # template_idx -> product_data
            
            for idx, product_data in enumerate(products_to_create):
                template_vals_list.append({
                    'name': product_data['name'],
                    'default_code': product_data['sku'],
                    'type': 'product',
                    'is_storable': True,
                    'tracking': 'none',
                    'categ_id': categ.id if categ else False,
                    'uom_id': uom_id.id if uom_id else False,
                    'company_id': product_data['company_id'] or False,
                    'sale_ok': True,
                    'purchase_ok': True,
                    'list_price': product_data['price'],
                })
                product_data_map[idx] = product_data
            
            try:
                templates = self.env['product.template'].sudo().create(template_vals_list)
                
                # Create bindings for newly created products
                for template, (idx, product_data) in zip(templates, product_data_map.items()):
                    product = template.product_variant_id
                    company_key = product.company_id.id or 0
                    existing_products.setdefault(product_data['sku'], {})[company_key] = product
                    binding = product_data.get('binding')
                    if binding:
                        bindings_to_update.append({
                            'binding': binding,
                            'product': product,
                            'lines': product_data['lines'],
                        })
                    else:
                        bindings_to_create.append({
                            'product_id': product.id,
                            'shop_id': product_data['shop_id'],
                            'external_sku': product_data['sku'],
                            'lines': product_data['lines'],
                        })
                
                self.env.cr.commit()
            except Exception as e:
                _logger.error(f'Failed to bulk create products: {e}', exc_info=True)
                # Fallback to individual create
                for product_data in products_to_create:
                    binding = product_data.get('binding')
                    product = False
                    for line in product_data['lines']:
                        try:
                            product = line._create_product_from_order_line(
                                company_id=line.order_id.company_id.id if line.order_id.company_id else False
                            )
                            if product:
                                company_key = product.company_id.id or 0
                                existing_products.setdefault(product_data['sku'], {})[company_key] = product
                                break
                        except Exception as create_error:
                            _logger.error(f'Failed to create product for SKU {product_data["sku"]}: {create_error}', exc_info=True)
                    if product and binding:
                        try:
                            binding.sudo().write({'product_id': product.id})
                        except Exception as update_error:
                            _logger.error(
                                f'Failed to update binding {binding.id} for SKU {product_data["sku"]}: {update_error}',
                                exc_info=True,
                            )
                        else:
                            for line in product_data['lines']:
                                line.product_binding_id = binding.id
        
        # Bulk create bindings
        if bindings_to_create:
            binding_vals_list = []
            binding_lines_map = {}  # binding_idx -> list of lines
            
            for idx, binding_data in enumerate(bindings_to_create):
                binding_vals_list.append({
                    'product_id': binding_data['product_id'],
                    'shop_id': binding_data['shop_id'],
                    'external_sku': binding_data['external_sku'],
                    'active': True,
                })
                binding_lines_map[idx] = binding_data['lines']
            
            try:
                bindings = self.env['marketplace.product.binding'].sudo().create(binding_vals_list)
                
                # Update lines with binding IDs
                for binding, (idx, binding_data) in zip(bindings, binding_lines_map.items()):
                    for line in binding_data['lines']:
                        line.product_binding_id = binding.id
                
                self.env.cr.commit()
            except Exception as e:
                _logger.error(f'Failed to bulk create bindings: {e}', exc_info=True)
                # Fallback to individual create
                for binding_data in bindings_to_create:
                    for line in binding_data['lines']:
                        try:
                            binding = self.env['marketplace.product.binding'].sudo().search([
                                ('external_sku', '=', binding_data['external_sku']),
                                ('shop_id', '=', binding_data['shop_id']),
                            ], limit=1)
                            if not binding:
                                binding = self.env['marketplace.product.binding'].sudo().create({
                                    'product_id': binding_data['product_id'],
                                    'shop_id': binding_data['shop_id'],
                                    'external_sku': binding_data['external_sku'],
                                    'active': True,
                                })
                            line.product_binding_id = binding.id
                            break
                        except Exception as create_error:
                            _logger.error(f'Failed to create binding for SKU {binding_data["external_sku"]}: {create_error}', exc_info=True)

        if bindings_to_update:
            for item in bindings_to_update:
                binding = item['binding'].sudo()
                product = item['product']
                try:
                    if binding.product_id != product:
                        binding.write({'product_id': product.id})
                except Exception as e:
                    _logger.error(
                        f'Failed to update binding {binding.id} for SKU {binding.external_sku}: {e}',
                        exc_info=True,
                    )
                    continue
                
                for line in item['lines']:
                    line.product_binding_id = binding.id

    def action_view_sale_order(self):
        """View linked sale order"""
        self.ensure_one()
        if not self.sale_order_id:
            raise UserError('No sale order linked')
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_retry_sync(self):
        """Retry syncing to sale order"""
        self._sync_to_sale_order()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Sync Retried',
                'message': f'Order {self.name} sync retried',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_bulk_sync_to_sale_orders(self):
        """Bulk sync marketplace orders to sale orders for orders without sale_order_id"""
        orders_to_sync = self.filtered(lambda o: not o.sale_order_id and o.state not in ('cancelled', 'returned'))
        
        if not orders_to_sync:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'No orders to sync. All selected orders already have sale orders or are cancelled/returned.',
                    'type': 'info',
                },
            }
        
        _logger.warning(f'🔍 action_bulk_sync_to_sale_orders: Syncing {len(orders_to_sync)} orders to sale orders')
        
        try:
            # Use bulk sync for better performance
            if len(orders_to_sync) >= 3:
                self._sync_orders_to_sale_orders_bulk(orders_to_sync)
            else:
                # Use individual sync for small number of orders
                for order in orders_to_sync:
                    order._sync_to_sale_order()
            
            _logger.warning(f'✅ action_bulk_sync_to_sale_orders: Successfully synced {len(orders_to_sync)} orders to sale orders')
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Successfully synced {len(orders_to_sync)} orders to sale orders',
                    'type': 'success',
                },
            }
        except Exception as e:
            _logger.error(f'❌ action_bulk_sync_to_sale_orders: Failed to sync orders: {e}', exc_info=True)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': f'Failed to sync orders: {str(e)}',
                    'type': 'danger',
                },
            }
    
    def action_fix_order_dates_from_payload(self):
        """Fix order_date for orders with 1970 date by reading create_time from raw_payload"""
        from datetime import datetime
        
        # Filter orders with 1970 date (Jan 1, 1970)
        # Check if order_date is before 1971-01-01
        orders_to_fix = self.filtered(lambda o: o.order_date and o.order_date.year == 1970)
        
        if not orders_to_fix:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'No orders with 1970 date found to fix.',
                    'type': 'info',
                },
            }
        
        fixed_count = 0
        failed_count = 0
        
        _logger.warning(f'🔍 action_fix_order_dates_from_payload: Fixing {len(orders_to_fix)} orders with 1970 date')
        
        for order in orders_to_fix:
            try:
                if not order.raw_payload:
                    _logger.warning(f'Order {order.name}: No raw_payload, skipping')
                    failed_count += 1
                    continue
                
                # Parse raw_payload JSON
                try:
                    payload = json.loads(order.raw_payload)
                except (json.JSONDecodeError, TypeError) as e:
                    _logger.warning(f'Order {order.name}: Failed to parse raw_payload: {e}')
                    failed_count += 1
                    continue
                
                # Get create_time from payload
                create_ts = payload.get('create_time')
                
                if create_ts and create_ts > 0:
                    # Use actual create_time from Shopee
                    new_order_date = datetime.fromtimestamp(create_ts)
                    order.write({'order_date': new_order_date})
                    fixed_count += 1
                    _logger.warning(f'✅ Order {order.name}: Fixed order_date from 1970 to {new_order_date}')
                else:
                    # If create_time is missing or 0, use current time as fallback
                    new_order_date = fields.Datetime.now()
                    order.write({'order_date': new_order_date})
                    fixed_count += 1
                    _logger.warning(f'⚠️ Order {order.name}: create_time missing/invalid, set to current time: {new_order_date}')
                
                # Also update sale order date if exists
                if order.sale_order_id:
                    order.sale_order_id.write({'date_order': new_order_date})
                    _logger.warning(f'✅ Updated sale order {order.sale_order_id.name} date_order to {new_order_date}')
                    
            except Exception as e:
                _logger.error(f'❌ Failed to fix order {order.name}: {e}', exc_info=True)
                failed_count += 1
        
        _logger.warning(f'✅ action_fix_order_dates_from_payload: Fixed {fixed_count} orders, {failed_count} failed')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success' if failed_count == 0 else 'Partial Success',
                'message': f'Fixed {fixed_count} orders, {failed_count} failed',
                'type': 'success' if failed_count == 0 else 'warning',
            },
        }
    
    def action_repair_incomplete_orders(self):
        """
        Repair incomplete marketplace orders imported from Shopee:
        - refetch detailed order payloads from Shopee
        - update marketplace.order fields and lines
        - rebuild related sale.order and sale.order.line
        """
        # Filter for Shopee orders that need repair
        orders = self.filtered(
            lambda o: o.channel == 'shopee'
            and (not o.order_line_ids or not o.amount_total or o.order_date.year <= 1971)
        )
        
        if not orders:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'No Shopee orders selected for repair.',
                    'type': 'info',
                },
            }
        
        _logger.warning(f'🔍 action_repair_incomplete_orders: repairing {len(orders)} Shopee orders')
        
        # Group orders by shop to reuse adapters
        orders_by_shop = {}
        for order in orders:
            orders_by_shop.setdefault(order.shop_id, self.env['marketplace.order'])
            orders_by_shop[order.shop_id] |= order
        
        repaired_count = 0
        failed_count = 0
        
        for shop, shop_orders in orders_by_shop.items():
            try:
                adapter = shop.account_id._get_adapter(shop)
                # Fetch details in batch
                sn_list = [o.external_order_id for o in shop_orders if o.external_order_id]
                if not sn_list:
                    _logger.warning(f'No external_order_id found for shop {shop.name}, skipping')
                    continue
                
                details = adapter._get_order_detail_by_sn_list(sn_list)
                details_by_sn = {d.get('order_sn'): d for d in details if d.get('order_sn')}
                
                for order in shop_orders:
                    payload = details_by_sn.get(order.external_order_id)
                    if not payload:
                        _logger.warning(f'❌ No detail payload for order {order.external_order_id}, skipping')
                        failed_count += 1
                        continue
                    
                    try:
                        order._repair_from_payload(adapter, payload)
                        repaired_count += 1
                    except Exception as e:
                        _logger.error(
                            f'❌ Failed to repair marketplace order {order.name}: {e}',
                            exc_info=True,
                        )
                        failed_count += 1
            except Exception as e:
                _logger.error(f'❌ Failed to process shop {shop.name}: {e}', exc_info=True)
                failed_count += len(shop_orders)
        
        _logger.warning(f'✅ action_repair_incomplete_orders: Repaired {repaired_count} orders, {failed_count} failed')
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success' if failed_count == 0 else 'Partial Success',
                'message': f'Repaired {repaired_count} orders, {failed_count} failed. Check logs for details.',
                'type': 'success' if failed_count == 0 else 'warning',
            },
        }
    
    def _repair_from_payload(self, adapter, payload):
        """
        Update this marketplace.order and linked sale.order from a fresh Shopee payload.
        
        Args:
            adapter: ShopeeAdapter instance
            payload: Raw order payload from Shopee API
        """
        self.ensure_one()
        
        order_data = adapter.parse_order_payload(payload)
        
        # Update main order fields
        vals = {
            'name': order_data.get('name', self.external_order_id),
            'order_date': order_data.get('order_date') or self.order_date,
            'customer_name': order_data.get('customer_name', self.customer_name),
            'customer_email': order_data.get('customer_email', self.customer_email),
            'customer_phone': order_data.get('customer_phone', self.customer_phone),
            'customer_address': order_data.get('customer_address', self.customer_address),
            'amount_total': order_data.get('amount_total', self.amount_total),
            'state': order_data.get('state', self.state),
            'raw_payload': json.dumps(payload, ensure_ascii=False),
        }
        self.write(vals)
        
        # Rebuild marketplace order lines
        self.order_line_ids.unlink()
        
        line_vals_list = []
        for line_data in order_data.get('lines', []) or []:
            line_vals_list.append({
                'order_id': self.id,
                'external_sku': line_data.get('external_sku'),
                'product_name': line_data.get('product_name', ''),
                'quantity': line_data.get('quantity', 1),
                'price_unit': line_data.get('price_unit', 0.0),
                'raw_data': json.dumps(line_data, ensure_ascii=False),
            })
        
        if line_vals_list:
            self.env['marketplace.order.line'].create(line_vals_list)
        
        _logger.warning(
            f'🔍 _repair_from_payload: order {self.name} now has '
            f'{len(self.order_line_ids)} marketplace lines'
        )
        
        # Rebuild sale order
        if self.sale_order_id:
            self._rebuild_sale_order_from_marketplace()
        else:
            self._sync_to_sale_order()
    
    def _rebuild_sale_order_from_marketplace(self):
        """
        Rebuild existing sale.order lines to match marketplace.order lines.
        """
        self.ensure_one()
        
        sale_order = self.sale_order_id
        if not sale_order:
            return
        
        _logger.warning(
            f'🔍 _rebuild_sale_order_from_marketplace: rebuilding sale order '
            f'{sale_order.name} from marketplace order {self.name}'
        )
        
        # Remove existing lines
        sale_order.order_line.unlink()
        
        # Recreate lines from marketplace.order.line
        for line in self.order_line_ids:
            line._create_sale_order_line(sale_order)
        
        # Update partner if needed
        partner = self._get_or_create_partner()
        if sale_order.partner_id != partner:
            sale_order.partner_id = partner.id
        
        # Update date_order if needed
        if sale_order.date_order != self.order_date:
            sale_order.date_order = self.order_date
        
        _logger.warning(
            f'✅ _rebuild_sale_order_from_marketplace: sale order {sale_order.name} now has '
            f'{len(sale_order.order_line)} lines'
        )


class MarketplaceOrderLine(models.Model):
    _name = 'marketplace.order.line'
    _description = 'Marketplace Order Line'
    _order = 'order_id, id'

    order_id = fields.Many2one(
        'marketplace.order', string='Order', required=True,
        ondelete='cascade', index=True
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line', string='Sale Order Line',
        ondelete='set null'
    )
    
    # Product mapping
    product_binding_id = fields.Many2one(
        'marketplace.product.binding', string='Product Binding',
        compute='_compute_product_binding', store=True
    )
    product_id = fields.Many2one(
        'product.product', string='Product',
        related='product_binding_id.product_id', readonly=True
    )
    
    # Line details
    external_sku = fields.Char(string='External SKU', required=True)
    product_name = fields.Char(string='Product Name', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    price_unit = fields.Float(string='Unit Price', required=True)
    
    raw_data = fields.Text(string='Raw Data', readonly=True)

    @api.depends('external_sku', 'order_id.shop_id')
    def _compute_product_binding(self):
        for line in self:
            if line.external_sku and line.order_id.shop_id:
                binding = self.env['marketplace.product.binding'].search([
                    ('external_sku', '=', line.external_sku),
                    ('shop_id', '=', line.order_id.shop_id.id),
                    ('active', '=', True),
                ], limit=1)
                line.product_binding_id = binding.id
            else:
                line.product_binding_id = False

    def _create_sale_order_line(self, sale_order):
        """Create sale order line"""
        self.ensure_one()
        
        target_company_id = sale_order.company_id.id if sale_order.company_id else False
        product = self._ensure_product_for_company(target_company_id)
        if not product:
            raise UserError(
                f'Failed to prepare product for SKU: {self.external_sku}. '
                f'Please create the product manually and set up product binding.'
            )
        
        # Get next sequence number for this order
        max_sequence = max(
            sale_order.order_line.mapped('sequence') or [0]
        )
        
        line_vals = {
            'order_id': sale_order.id,
            'product_id': product.id,
            'name': self.product_name,
            'product_uom_qty': self.quantity,
            'price_unit': self.price_unit,
            'sequence': max_sequence + 1,  # Set sequence to ensure order lines are displayed
        }
        
        line = self.env['sale.order.line'].create(line_vals)
        self.sale_order_line_id = line.id
        return line
    
    def _ensure_product_for_company(self, company_id=False):
        """Ensure the order line has a product binding for the given company."""
        binding = self.product_binding_id
        product = binding.product_id if binding else False

        if product and company_id and product.company_id and product.company_id.id not in (False, company_id):
            product = False

        if not product:
            product = self._find_existing_product_for_company(company_id)
            if product:
                self._bind_product_to_line(product)

        if not product:
            product = self._create_product_from_order_line(company_id=company_id)

        return product

    def _create_product_from_order_line(self, company_id=False):
        """Create product and binding automatically from order line"""
        self.ensure_one()
        
        if not self.external_sku:
            _logger.warning(f'Cannot create product: No SKU for order line {self.id}')
            return False
        
        # Try to reuse existing product for this company (or global)
        product = self._find_existing_product_for_company(company_id)
        
        if product:
            _logger.info(f'Product exists for SKU {self.external_sku}, binding or reusing for company {company_id}')
            self._bind_product_to_line(product)
            return product
        else:
            # Create product template and product
            _logger.warning(f'Creating product for SKU: {self.external_sku}, Name: {self.product_name}')
            
            # Get company from shop
            product_company_id = company_id or (
                self.order_id.shop_id.company_id.id if self.order_id.shop_id.company_id else self.env.company.id
            )
            
            # Get default UOM
            uom_id = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
            if not uom_id:
                uom_id = self.env['uom.uom'].search([('name', '=', 'Units')], limit=1)
            if not uom_id:
                uom_id = self.env['uom.uom'].search([], limit=1)
            
            # Get product category
            categ = self.env.ref('product.product_category_all', raise_if_not_found=False)
            if not categ:
                # Try to get any category
                categ = self.env['product.category'].search([], limit=1)
            
            # Create product template
            template_vals = {
                'name': self.product_name or f'Product {self.external_sku}',
                'default_code': self.external_sku,
                'type': 'product',
                'is_storable': True,
                'categ_id': categ.id if categ else False,
                'uom_id': uom_id.id if uom_id else False,
                'company_id': product_company_id,
                'sale_ok': True,
                'purchase_ok': True,
                'list_price': self.price_unit or 0.0,
            }
            company = self.env['res.company'].browse(product_company_id) if product_company_id else self.env.company
            if company:
                sale_tax = company.account_sale_tax_id
                purchase_tax = company.account_purchase_tax_id
                if sale_tax:
                    template_vals['taxes_id'] = [(6, 0, sale_tax.ids)]
                if purchase_tax:
                    template_vals['supplier_taxes_id'] = [(6, 0, purchase_tax.ids)]
            
            try:
                template = self.env['product.template'].sudo().create(template_vals)
                product = template.product_variant_id
                _logger.warning(f'✅ Created product: {product.name} (SKU: {self.external_sku})')
            except Exception as e:
                _logger.error(f'Failed to create product for SKU {self.external_sku}: {e}', exc_info=True)
                return False
        
        # Create product binding if it doesn't exist
        if product and self.order_id.shop_id:
            self._bind_product_to_line(product)
            return product
        
        return False

    def _find_existing_product_for_company(self, company_id=False):
        """Find an existing product by SKU that matches the target company or is shared."""
        domain = [('default_code', '=', self.external_sku)]
        if company_id:
            domain = expression.AND([domain, [('company_id', 'in', [company_id, False])]])
        
        products = self.env['product.product'].sudo().search(domain)
        if not products:
            return False
        
        if company_id:
            for product in products:
                if product.company_id and product.company_id.id == company_id:
                    return product
            for product in products:
                if not product.company_id:
                    return product
            return False
        
        return products[:1]

    def _bind_product_to_line(self, product):
        """Ensure the marketplace binding points to the provided product."""
        if not product or not self.order_id.shop_id:
            return
        
        binding = self.product_binding_id
        if binding:
            if binding.product_id != product:
                try:
                    binding.sudo().write({'product_id': product.id})
                except Exception as e:
                    _logger.error(
                        f'Failed to update binding {binding.id} for SKU {self.external_sku}: {e}',
                        exc_info=True,
                    )
            return
        
        try:
            binding = self.env['marketplace.product.binding'].sudo().create({
                'product_id': product.id,
                'shop_id': self.order_id.shop_id.id,
                'external_sku': self.external_sku,
                'active': True,
            })
            _logger.warning(f'✅ Created product binding: {self.external_sku} -> {product.name}')
            self.invalidate_recordset(['product_binding_id'])
            self._compute_product_binding()
        except Exception as e:
            _logger.error(f'Failed to create binding for SKU {self.external_sku}: {e}', exc_info=True)
            

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    marketplace_external_order_id = fields.Char(
        string='External Order ID',
        related='marketplace_order_id.external_order_id',
        store=False,
        readonly=True,
        help='Marketplace external order number'
    )
    manual_marketplace_channel_id = fields.Many2one(
        'marketplace.channel',
        string='Channel',
        help='Manual channel selection for orders created directly in Odoo (only for manually created orders)'
    )

    @api.onchange('marketplace_order_id')
    def _onchange_marketplace_order_id(self):
        """Auto-map channel from marketplace order and clear manual channel selection"""
        for order in self:
            if order.marketplace_order_id:
                # Marketplace order: channel is automatically mapped via related field
                # Clear manual channel selection to avoid confusion
                order.manual_marketplace_channel_id = False
            # If marketplace_order_id is cleared, manual_marketplace_channel_id can be set manually

    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        """Allow searching sale orders by external marketplace order number."""
        args = list(args or [])

        if name and operator in ('ilike', 'like', '=ilike', '=like', '='):
            search_domain = ['|', ('name', operator, name), ('marketplace_order_id.external_order_id', operator, name)]
            domain = expression.AND([search_domain, args])
            record_ids = self._search(domain, limit=limit, access_rights_uid=name_get_uid)
            return self.browse(record_ids).name_get()
            
        return super()._name_search(
            name=name, args=args, operator=operator, limit=limit, name_get_uid=name_get_uid
        )

    def _compute_display_name(self):
        super()._compute_display_name()
        for order in self:
            if order.marketplace_order_id and order.marketplace_order_id.external_order_id:
                order.display_name = order.marketplace_order_id.external_order_id

