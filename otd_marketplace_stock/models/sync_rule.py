# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MarketplaceSyncRule(models.Model):
    _name = 'marketplace.sync.rule'
    _description = 'Marketplace Sync Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'priority desc, name'

    name = fields.Char(string='Rule Name', required=True)
    active = fields.Boolean(string='Active', default=True)
    priority = fields.Integer(
        string='Priority', default=10,
        help='Higher priority rules are applied first'
    )
    
    # Rule scope
    rule_scope = fields.Selection([
        ('global', 'Global'),
        ('account', 'Account'),
        ('shop', 'Shop'),
        ('product', 'Product'),
    ], string='Scope', required=True, default='global')
    
    account_id = fields.Many2one(
        'marketplace.account', string='Account',
        ondelete='cascade'
    )
    shop_id = fields.Many2one(
        'marketplace.shop', string='Shop',
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product', string='Product',
        ondelete='cascade'
    )
    
    # Stock sync rules
    buffer_qty = fields.Integer(
        string='Buffer Quantity',
        help='Quantity to subtract from available stock (empty = use account default)'
    )
    min_qty = fields.Integer(
        string='Minimum Quantity',
        help='Minimum quantity to show online (empty = use account default)'
    )
    rounding = fields.Integer(
        string='Rounding',
        help='Round quantity to nearest value (e.g., 10 = round to 10s)'
    )
    exclude_push = fields.Boolean(
        string='Exclude from Push',
        help='Exclude products matching this rule from stock push'
    )
    
    # Conditions
    condition_product_category_ids = fields.Many2many(
        'product.category', string='Product Categories',
        help='Apply rule only to products in these categories'
    )
    condition_product_tag_ids = fields.Many2many(
        'product.tag', string='Product Tags',
        help='Apply rule only to products with these tags'
    )
    condition_min_stock = fields.Float(
        string='Minimum Stock Condition',
        help='Apply rule only if stock is above this value'
    )

    @api.constrains('rule_scope', 'account_id', 'shop_id', 'product_id')
    def _check_scope(self):
        for rule in self:
            if rule.rule_scope == 'account' and not rule.account_id:
                raise ValidationError('Account is required for account scope')
            if rule.rule_scope == 'shop' and not rule.shop_id:
                raise ValidationError('Shop is required for shop scope')
            if rule.rule_scope == 'product' and not rule.product_id:
                raise ValidationError('Product is required for product scope')

    @api.model
    def get_rule_for_binding(self, binding):
        """Get applicable rule for a product binding"""
        rules = self.search([
            ('active', '=', True),
        ], order='priority desc')
        
        product = binding.product_id
        
        for rule in rules:
            # Check scope match
            if rule.rule_scope == 'product' and rule.product_id != product:
                continue
            if rule.rule_scope == 'shop' and rule.shop_id != binding.shop_id:
                continue
            if rule.rule_scope == 'account' and rule.account_id != binding.account_id:
                continue
            
            # Check conditions
            if rule.condition_product_category_ids:
                if product.categ_id not in rule.condition_product_category_ids:
                    continue
            
            if rule.condition_product_tag_ids:
                if not (product.product_tag_ids & rule.condition_product_tag_ids):
                    continue
            
            # Return first matching rule
            return rule
        
        return self.browse()

