# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Helpdesk Management",
    "summary": """
        Helpdesk""",
    "version": "19.0.1.17.0",
    "license": "AGPL-3",
    "category": "After-Sales",
    "author": "AdaptiveCity, "
    "Tecnativa, "
    "ForgeFlow, "
    "C2i Change 2 Improve, "
    "Domatix, "
    "Factor Libre, "
    "SDi Soluciones, "
    "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/helpdesk",
    "depends": ["mail", "portal", "product"],
    "data": [
        "data/helpdesk_data.xml",
        "data/helpdesk_followup_cron.xml",
        "data/helpdesk_followup_kpi_cron.xml",
        "security/helpdesk_security.xml",
        "security/ir.model.access.csv",
        "views/res_partner_views.xml",
        "views/res_config_settings_views.xml",
        "views/helpdesk_ticket_templates.xml",
        "views/helpdesk_ticket_menu.xml",
        "views/helpdesk_ticket_team_views.xml",
        "views/helpdesk_ticket_stage_views.xml",
        "views/helpdesk_ticket_category_views.xml",
        "views/helpdesk_ticket_channel_views.xml",
        "views/helpdesk_ticket_tag_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_ticket_product_context_views.xml",
        "views/helpdesk_dashboard_views.xml",
        "views/helpdesk_lineoa_channel_views.xml",
        "views/helpdesk_followup_policy_views.xml",
        "views/helpdesk_followup_event_views.xml",
        "views/helpdesk_followup_kpi_daily_views.xml",
        "views/helpdesk_followup_kpi_summary_views.xml",
        "views/helpdesk_followup_kpi_search.xml",
        "views/helpdesk_followup_kpi_menu.xml",
        "views/line_webhook_event_views.xml",
        "wizards/helpdesk_ticket_duplicate_wizard_views.xml",
    ],
    "demo": ["demo/helpdesk_demo.xml"],
    "assets": {
        "web.assets_frontend": [
            "helpdesk_mgmt/static/src/js/new_ticket.esm.js",
        ],
        "web.assets_backend": [
            "helpdesk_mgmt/static/src/views/**/*.esm.js",
            "helpdesk_mgmt/static/src/views/**/*.xml",
            "helpdesk_mgmt/static/src/js/helpdesk_password_toggle_field.js",
            "helpdesk_mgmt/static/src/xml/helpdesk_password_toggle_field.xml",
            "helpdesk_mgmt/static/src/scss/helpdesk_followup_kpi.scss",
            "helpdesk_mgmt/static/src/scss/helpdesk_ticket_product.scss",
        ],
        "web.assets_unit_tests": [
            "helpdesk_mgmt/static/tests/**/*.test.js",
        ],
    },
    "development_status": "Production/Stable",
    "application": True,
    "installable": True,
}
