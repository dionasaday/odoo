# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api
import json
import logging

_logger = logging.getLogger(__name__)


class SpreadsheetDashboard(models.Model):
    """Inherit spreadsheet.dashboard to handle empty/invalid spreadsheet_data
    
    This patch handles cases where spreadsheet_data is empty or invalid,
    preventing JSONDecodeError when loading dashboards.
    """
    _inherit = 'spreadsheet.dashboard'

    def _get_serialized_readonly_dashboard(self):
        """Override to handle empty or invalid spreadsheet_data"""
        try:
            # Call parent method first
            return super()._get_serialized_readonly_dashboard()
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # If spreadsheet_data is empty or invalid, return empty dashboard
            _logger.warning(
                "Dashboard %s (id=%s) has invalid spreadsheet_data: %s. Returning empty dashboard.",
                self.name, self.id, str(e)
            )
            
            # Return structure matching parent method format
            # Parent method returns: {'snapshot': {...}, 'revisions': [], 'default_currency': ..., 'translation_namespace': ...}
            dashboard_name = self.name or "Dashboard"
            user_locale = self.env['res.lang']._get_user_spreadsheet_locale()
            default_currency = self.env['res.currency'].get_company_currency_for_spreadsheet()
            
            # Try to get sales orders data if this is a Sales dashboard
            sales_data = {}
            if 'sales' in dashboard_name.lower() or 'sale' in dashboard_name.lower():
                try:
                    # Get current company from context
                    current_company = self.env.company
                    _logger.info(f"Fetching sales data for company: {current_company.name} (id={current_company.id})")
                    
                    # Filter sales orders by current company
                    sales_orders = self.env['sale.order'].search([
                        ('company_id', '=', current_company.id)
                    ])
                    total_orders = len(sales_orders)
                    total_amount = sum(sales_orders.mapped('amount_total'))
                    sales_data = {
                        'total_orders': total_orders,
                        'total_amount': total_amount,
                        'currency_symbol': default_currency.get('symbol', '฿') if isinstance(default_currency, dict) else '฿',
                        'company_name': current_company.name
                    }
                    _logger.info(f"Sales data for {current_company.name}: {total_orders} orders, {total_amount} total")
                except Exception as e:
                    _logger.warning(f"Could not fetch sales data for dashboard (company={self.env.company.name}): {e}")
                    sales_data = {}
            
            # Create snapshot structure (the actual spreadsheet data)
            # Always show dashboard content, even if no sales data
            current_company = self.env.company
            cells = {}
            
            if sales_data:
                # Show actual sales data with company info
                cells = {
                    "A1": {
                        "content": f"{dashboard_name} Dashboard - {sales_data.get('company_name', current_company.name)}",
                        "style": {}
                    },
                    "A2": {
                        "content": "Total Sales Orders:",
                        "style": {}
                    },
                    "B2": {
                        "content": str(sales_data.get('total_orders', 0)),
                        "style": {}
                    },
                    "A3": {
                        "content": "Total Amount:",
                        "style": {}
                    },
                    "B3": {
                        "content": f"{sales_data.get('currency_symbol', '฿')} {sales_data.get('total_amount', 0):,.2f}",
                        "style": {}
                    },
                    "A4": {
                        "content": f"Company: {sales_data.get('company_name', current_company.name)}",
                        "style": {}
                    },
                    "A5": {
                        "content": "Note: This is a placeholder dashboard. Please configure it with proper spreadsheet data.",
                        "style": {}
                    }
                }
            else:
                # Show generic placeholder with company info
                cells = {
                    "A1": {
                        "content": f"{dashboard_name} Dashboard - {current_company.name}",
                        "style": {}
                    },
                    "A2": {
                        "content": f"Company: {current_company.name}",
                        "style": {}
                    },
                    "A3": {
                        "content": "Dashboard is empty or has invalid data.",
                        "style": {}
                    },
                    "A4": {
                        "content": "Please configure this dashboard with data.",
                        "style": {}
                    }
                }
                _logger.warning(f"Dashboard '{dashboard_name}' for company '{current_company.name}' has no sales data")
            
            snapshot = {
                "version": "1.0",
                "sheets": [{
                    "id": "sheet1",
                    "name": "Sheet1",
                    "cells": cells,
                    "cols": {
                        "0": {"size": 300},
                        "1": {"size": 100},
                        "2": {"size": 100}
                    },
                    "rows": {
                        "0": {"size": 30},
                        "1": {"size": 25},
                        "2": {"size": 25},
                        "3": {"size": 25},
                        "4": {"size": 25},
                        "5": {"size": 25}
                    },
                    "figures": [],
                    "conditionalFormats": [],
                    "charts": [],
                    "images": [],
                    "zones": {},
                    "viewports": [{"left": 0, "top": 0, "right": 20, "bottom": 20}],
                    "filters": {},
                    "collaborative": {
                        "sessionId": "",
                        "clientId": ""
                    }
                }],
                "revisionId": "0",
                "collaborative": {
                    "sessionId": "",
                    "clientId": ""
                },
                "settings": {
                    "locale": user_locale
                }
            }
            
            # Return in the same format as parent method
            result = json.dumps({
                'snapshot': snapshot,
                'revisions': [],
                'default_currency': default_currency,
                'translation_namespace': self._get_dashboard_translation_namespace(),
            }, ensure_ascii=False)
            
            _logger.info(f"Returning dashboard with sales data (length: {len(result)}) for dashboard {self.name} (id={self.id})")
            return result
        except Exception as e:
            # For any other error, log and return empty dashboard
            _logger.error(
                "Error loading dashboard %s (id=%s): %s. Returning empty dashboard.",
                self.name, self.id, str(e)
            )
            
            # Return structure matching parent method format
            dashboard_name = self.name or "Dashboard"
            user_locale = self.env['res.lang']._get_user_spreadsheet_locale()
            default_currency = self.env['res.currency'].get_company_currency_for_spreadsheet()
            
            # Try to get sales orders data if this is a Sales dashboard
            sales_data = {}
            if 'sales' in dashboard_name.lower() or 'sale' in dashboard_name.lower():
                try:
                    # Get current company from context
                    current_company = self.env.company
                    _logger.info(f"Fetching sales data for company: {current_company.name} (id={current_company.id})")
                    
                    # Filter sales orders by current company
                    sales_orders = self.env['sale.order'].search([
                        ('company_id', '=', current_company.id)
                    ])
                    total_orders = len(sales_orders)
                    total_amount = sum(sales_orders.mapped('amount_total'))
                    sales_data = {
                        'total_orders': total_orders,
                        'total_amount': total_amount,
                        'currency_symbol': default_currency.get('symbol', '฿') if isinstance(default_currency, dict) else '฿',
                        'company_name': current_company.name
                    }
                    _logger.info(f"Sales data for {current_company.name}: {total_orders} orders, {total_amount} total")
                except Exception as e:
                    _logger.warning(f"Could not fetch sales data for dashboard (company={self.env.company.name}): {e}")
                    sales_data = {}
            
            # Create snapshot structure (the actual spreadsheet data)
            # Always show dashboard content, even if no sales data
            current_company = self.env.company
            cells = {}
            
            if sales_data:
                # Show actual sales data with company info
                cells = {
                    "A1": {
                        "content": f"{dashboard_name} Dashboard - {sales_data.get('company_name', current_company.name)}",
                        "style": {}
                    },
                    "A2": {
                        "content": "Total Sales Orders:",
                        "style": {}
                    },
                    "B2": {
                        "content": str(sales_data.get('total_orders', 0)),
                        "style": {}
                    },
                    "A3": {
                        "content": "Total Amount:",
                        "style": {}
                    },
                    "B3": {
                        "content": f"{sales_data.get('currency_symbol', '฿')} {sales_data.get('total_amount', 0):,.2f}",
                        "style": {}
                    },
                    "A4": {
                        "content": f"Company: {sales_data.get('company_name', current_company.name)}",
                        "style": {}
                    },
                    "A5": {
                        "content": "Note: This is a placeholder dashboard. Please configure it with proper spreadsheet data.",
                        "style": {}
                    }
                }
            else:
                # Show generic placeholder with company info
                cells = {
                    "A1": {
                        "content": f"{dashboard_name} Dashboard - {current_company.name}",
                        "style": {}
                    },
                    "A2": {
                        "content": f"Company: {current_company.name}",
                        "style": {}
                    },
                    "A3": {
                        "content": "Dashboard is empty or has invalid data.",
                        "style": {}
                    },
                    "A4": {
                        "content": "Please configure this dashboard with data.",
                        "style": {}
                    }
                }
                _logger.warning(f"Dashboard '{dashboard_name}' for company '{current_company.name}' has no sales data")
            
            snapshot = {
                "version": "1.0",
                "sheets": [{
                    "id": "sheet1",
                    "name": "Sheet1",
                    "cells": cells,
                    "cols": {
                        "0": {"size": 300},
                        "1": {"size": 100},
                        "2": {"size": 100}
                    },
                    "rows": {
                        "0": {"size": 30},
                        "1": {"size": 25},
                        "2": {"size": 25},
                        "3": {"size": 25},
                        "4": {"size": 25},
                        "5": {"size": 25}
                    },
                    "figures": [],
                    "conditionalFormats": [],
                    "charts": [],
                    "images": [],
                    "zones": {},
                    "viewports": [{"left": 0, "top": 0, "right": 20, "bottom": 20}],
                    "filters": {},
                    "collaborative": {
                        "sessionId": "",
                        "clientId": ""
                    }
                }],
                "revisionId": "0",
                "collaborative": {
                    "sessionId": "",
                    "clientId": ""
                },
                "settings": {
                    "locale": user_locale
                }
            }
            
            # Return in the same format as parent method
            result = json.dumps({
                'snapshot': snapshot,
                'revisions': [],
                'default_currency': default_currency,
                'translation_namespace': self._get_dashboard_translation_namespace(),
            }, ensure_ascii=False)
            
            _logger.info(f"Returning dashboard with sales data (length: {len(result)}) for dashboard {self.name} (id={self.id})")
            return result

