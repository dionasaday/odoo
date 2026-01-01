from . import models
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """No-op. Manual maintenance tasks moved to scripts/manual_post_init_tasks.py."""
    _logger.info("post_init_hook is a no-op; run scripts/manual_post_init_tasks.py if needed.")
