# -*- coding: utf-8 -*-
{
    "name": "OnThisDay HR Discipline",
    "summary": "วินัยและบทลงโทษพนักงาน (ฉบับที่ 002/2025) — Token-based lateness system, เคสความผิด, เลดเจอร์, เกณฑ์บทลงโทษ",
    "version": "19.0.1.0.0",
    "author": "On This Day",
    "license": "LGPL-3",
    "depends": ["base", "hr", "mail", "hr_attendance", "hr_holidays"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "data/hr_employee_action_restrictions.xml",
        "data/sequences.xml",
        "data/remove_om_account_asset_assets.xml",
        "data/offense_data.xml",
        "data/offense_lateness.xml", 
        "data/offense_late_bundle.xml", 
        "data/offense_token_lateness.xml", 
        "data/cron_lateness.xml",
        "data/cron_lateness_monthly_summary.xml",
        "data/cron_sync_discipline_manager.xml",
        # Views with actions (ต้องมาก่อน menu.xml)
        "views/ledger_views.xml",  # action_hr_discipline_ledger
        "views/case_views.xml",  # action_hr_discipline_case
        "views/punishment_wizard_views.xml",
        "views/offense_views.xml",  # action_hr_offense_category, action_hr_offense
        "views/action_views.xml",  # action_hr_discipline_action
        "views/lateness_log_views.xml",  # ต้องมาก่อน lateness_monthly_summary_views.xml เพื่อให้ view IDs พร้อม
        "views/lateness_monthly_summary_views.xml",  # action_hr_lateness_monthly_summary
        "views/email_log_views.xml",  # action_hr_discipline_email_log
        "views/attendance_award_views.xml",  # action_attendance_award (ถ้ามี)
        'views/my_token_balance_views.xml',  # action_my_token_balance
        "views/token_balance_summary_views.xml",  # action_token_balance_summary
        'views/my_summary_views.xml',  # action_my_points_by_catalog
        # Menu (ต้องมาหลัง views ที่มี actions)
        "views/menu.xml",
        "data/update_menu_name.xml",  # Force update menu name AFTER menu.xml
        "data/fix_menu_token_balance.xml",  # Force update menu AFTER menu.xml to remove groups restriction
        # Other views
        "views/lateness_rule_views.xml",
        "views/attendance_views.xml",
             "views/case_user_views.xml", 
             "views/company_lateness_views.xml", 
             'views/res_company_views.xml',
             "views/res_config_settings_patch_view.xml",
             "views/mail_templates_monthly.xml",
             "data/cron_monthly_summary.xml",
             'data/cron.xml',
             "data/mail_templates.xml",
    ],
    "application": True,
    "installable": True,
    "post_init_hook": "post_init_hook",
}
