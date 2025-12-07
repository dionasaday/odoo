# -*- coding: utf-8 -*-

{
    'name': 'Knowledge Base OCA',
    'version': '19.0.1.0.2',
    'category': 'Knowledge',
    'summary': 'Internal Knowledge Base based on OCA patterns',
    'description': """
Knowledge Base OCA
==================
A simple internal Knowledge Base application for organizations,
based on OCA (Odoo Community Association) patterns.

This module is 100% compatible with Odoo 19 Community Edition
and requires no Enterprise dependencies.

Features:
---------
* Hierarchical article structure (parent/child articles)
* Category-based organization
* Rich HTML content editor
* User-based responsibility tracking
* Full mail thread integration for collaboration
* Activity tracking

Categories:
-----------
* SOP / Workflow
* Product Knowledge
* System / Tools Manual
* Policy / HR
* Other
    """,
    'author': 'On This Day',
    'website': 'https://www.example.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'website',
    ],
    'data': [
        'security/knowledge_groups.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',
        'data/knowledge_article_category_data.xml',
        'views/knowledge_article_category_views.xml',
        'views/knowledge_article_tag_views.xml',
        'views/knowledge_article_views.xml',
        'views/knowledge_article_comment_views.xml',
        'views/knowledge_public_templates.xml',
        'data/knowledge_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Utility files
            'knowledge_onthisday_oca/static/src/js/utils/logger.js',
            # Comment system files
            'knowledge_onthisday_oca/static/src/js/comment/text_selection.js',
            'knowledge_onthisday_oca/static/src/js/comment/comment_manager.js',
            'knowledge_onthisday_oca/static/src/js/comment/comment_overlay.js',
            'knowledge_onthisday_oca/static/src/js/comment/lazy_comment_overlay_wrapper.js',
            'knowledge_onthisday_oca/static/src/js/knowledge_document_controller.js',
            'knowledge_onthisday_oca/static/src/xml/comment_overlay.xml',
            'knowledge_onthisday_oca/static/src/xml/knowledge_document_view.xml',
            'knowledge_onthisday_oca/static/src/scss/comment_overlay.scss',
            'knowledge_onthisday_oca/static/src/scss/knowledge_document.scss',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
