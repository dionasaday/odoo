# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
from odoo import models, fields
from odoo.exceptions import UserError
import requests
import time
import logging
from datetime import datetime, timedelta
import json
import hmac
import hashlib

_logger = logging.getLogger(__name__)


class MarketplaceAdapter(ABC):
    """Abstract base class for marketplace adapters"""
    
    def __init__(self, account, shop=None):
        self.account = account
        self.shop = shop
        self.env = account.env
        self.base_url = self._get_base_url()
        self.timeout = 30
        self.max_retries = 3
    
    @abstractmethod
    def _get_base_url(self):
        """Get base API URL for the marketplace"""
        pass
    
    @abstractmethod
    def get_authorize_url(self):
        """Get OAuth authorization URL"""
        pass
    
    @abstractmethod
    def exchange_code(self, code):
        """Exchange authorization code for tokens"""
        pass
    
    @abstractmethod
    def refresh_access_token(self):
        """Refresh access token"""
        pass
    
    @abstractmethod
    def fetch_orders(self, since, until=None):
        """Fetch orders from marketplace
        
        Args:
            since: datetime or string - start time
            until: datetime or string (optional) - end time
        
        Returns:
            list of order payloads
        """
        pass
    
    @abstractmethod
    def update_inventory(self, items):
        """Update inventory on marketplace
        
        Args:
            items: list of tuples (external_sku, quantity)
        
        Returns:
            dict with results per item
        """
        pass
    
    @abstractmethod
    def verify_webhook(self, headers, body):
        """Verify webhook signature"""
        pass
    
    @abstractmethod
    def parse_order_payload(self, payload):
        """Parse order payload from marketplace to standard format"""
        pass
    
    def _get_access_token(self):
        """Get valid access token (refresh if needed)"""
        self.account._check_token_expiry()
        return self.account.access_token
    
    def _make_request(self, method, endpoint, params=None, data=None, headers=None):
        """Make API request with retry and rate limiting"""
        url = f"{self.base_url}{endpoint}"
        
        if headers is None:
            headers = {}
        
        # Add authorization
        token = self._get_access_token()
        if token:
            headers['Authorization'] = f'Bearer {token}'
        
        headers.setdefault('Content-Type', 'application/json')
        
        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    params=params,
                    json=data,
                    headers=headers,
                    timeout=self.timeout,
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    _logger.warning(f'Rate limited, waiting {retry_after} seconds')
                    time.sleep(retry_after)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = 2 ** attempt
                _logger.warning(f'Request failed, retrying in {wait_time}s: {e}')
                time.sleep(wait_time)
        
        raise Exception('Request failed after retries')


class MarketplaceAdapters(models.Model):
    """Registry for marketplace adapters"""
    _name = 'marketplace.adapters'
    _description = 'Marketplace Adapters Registry'
    
    _adapter_classes = {}
    
    @classmethod
    def register_adapter(cls, channel, adapter_class):
        """Register an adapter class for a channel"""
        cls._adapter_classes[channel] = adapter_class
    
    @classmethod
    def _get_adapter_class(cls, channel):
        """Get adapter class for channel"""
        return cls._adapter_classes.get(channel)


# Adapters will be registered when imported
# This is done in __init__.py to avoid circular imports

