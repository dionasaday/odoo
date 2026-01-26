# -*- coding: utf-8 -*-
from . import models


def post_init_hook(env):
    """Create access rights after module installation"""
    env['ir.model.access']._create_employee_payslip_access()
