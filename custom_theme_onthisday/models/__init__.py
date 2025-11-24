# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import res_company
from . import res_config_settings

# Try to import spreadsheet_dashboard_patch if spreadsheet_dashboard module exists
try:
    from . import spreadsheet_dashboard_patch
except ImportError:
    # spreadsheet_dashboard module may not be installed, skip
    pass

