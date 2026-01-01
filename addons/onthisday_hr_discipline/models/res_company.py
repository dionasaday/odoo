# -*- coding: utf-8 -*-
from odoo import api, fields, models, _

class ResCompany(models.Model):
    _inherit = "res.company"

    # --- Discipline configuration ---
    discipline_start_date = fields.Date(
        string="Discipline Start Date",
        help="Start date for discipline policy calculations."
    )
    discipline_threshold_late = fields.Integer(
        string="Late Threshold (per period)",
        default=5,
        help="Number of lateness occurrences within the period that triggers a summary/warning."
    )
    discipline_email_enabled = fields.Boolean(
        string="Send Monthly Discipline Email",
        default=True
    )

    # --- Lateness knobs (อ้างใน company_lateness_views.xml) ---
    hr_lateness_grace = fields.Integer(
        string="Grace Minutes (Late)",
        default=5,
        help="Minutes allowed before counting as late."
    )
    lateness_alert_min_minutes = fields.Integer(
        string="Alert when late over (min)",
        default=10,
        help="Only count lateness >= this number of minutes. (Legacy field, kept for compatibility)"
    )
    lateness_alert_every_n = fields.Integer(
        string="Alert every N occurrences",
        default=5,
        help="Legacy field: Bundling logic disabled in Policy 002/2025. Kept for backward compatibility."
    )
    
    # --- Token-based Lateness Policy 002/2025 ---
    lateness_tier1_max_minutes = fields.Integer(
        string="Tier 1 Max Minutes",
        default=10,
        help="Maximum minutes for Tier 1 lateness (deducts 1 token). Beyond this is Tier 2 (2 tokens)."
    )
    tokens_tier1 = fields.Integer(
        string="Tokens for Tier 1 (≤10 min)",
        default=1,
        help="Number of tokens deducted for lateness ≤ tier1_max_minutes (with notification)."
    )
    tokens_tier2 = fields.Integer(
        string="Tokens for Tier 2 (>10 min)",
        default=2,
        help="Number of tokens deducted for lateness > tier1_max_minutes (with notification)."
    )
    tokens_no_notice = fields.Integer(
        string="Tokens for No Notice",
        default=3,
        help="Number of tokens deducted when employee is late without notifying manager beforehand."
    )
    token_period_type = fields.Selection(
        [
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
        ],
        string="Token Period Type",
        default="monthly",
        help="Period for token reset and management review threshold."
    )
    token_period_start_day = fields.Integer(
        string="Weekly Start Day (0=Monday)",
        default=0,
        help="Day of week for weekly period start (0=Monday, 6=Sunday). Only used if period_type is 'weekly'."
    )
    token_reset_day_of_month = fields.Integer(
        string="Monthly Reset Day",
        default=1,
        help="Day of month for monthly period reset (1-31). Only used if period_type is 'monthly'."
    )
    lateness_repeat_threshold = fields.Integer(
        string="Management Review Threshold",
        default=3,
        help="Number of lateness occurrences within period that triggers management review flag (no auto punishment)."
    )
    tokens_starting_per_period = fields.Integer(
        string="Starting Tokens per Period",
        default=0,
        help="Number of tokens employees receive at the start of each period. Set to 0 to disable automatic allocation."
    )
