# -*- coding: utf-8 -*-

import logging

from . import models
from . import controllers
from . import wizard
from . import wizards


_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Fix action contexts that contain active_id"""
    actions = env['ir.actions.act_window'].with_context(active_test=False).search([
        ('context', 'ilike', 'active_id'),
        '|',
        ('res_model', 'like', 'marketplace.%'),
        ('name', 'ilike', 'Marketplace'),
    ])
    if actions:
        actions.write({'context': False})
        _logger.info("Cleared context for %s marketplace actions containing active_id", len(actions))

