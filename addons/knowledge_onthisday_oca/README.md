# Knowledge Base OCA

A simple Knowledge Base module for Odoo 19 Community Edition, based on OCA (Odoo Community Association) patterns.

## Features

- **Hierarchical Articles**: Parent-child article relationships
- **Categories**: Organize articles by type (SOP, Product, System, Policy, Other)
- **Rich Content**: HTML editor for article content
- **Responsibility Tracking**: Assign articles to users
- **Mail Integration**: Full mail thread and activity support
- **Multiple Views**: List, Form, Kanban, and Search views

## Installation

See [INSTALLATION.md](INSTALLATION.md) for detailed installation instructions.

Quick start:
1. Place module in `./addons/knowledge_onthisday_oca/`
2. Restart Odoo: `docker compose restart odoo`
3. Update Apps List in Odoo web interface
4. Install "Knowledge Base OCA" from Apps menu

## Module Structure

```
knowledge_onthisday_oca/
├── __init__.py                      # Module initialization
├── __manifest__.py                  # Module metadata
├── models/
│   ├── __init__.py                  # Models initialization
│   └── knowledge_article.py         # Knowledge Article model
├── views/
│   └── knowledge_article_views.xml  # Views (list, form, kanban, search)
├── security/
│   └── ir.model.access.csv          # Access rights
└── data/
    └── knowledge_menus.xml          # Menu definitions
```

## Usage

### Creating Articles

1. Go to **Knowledge > All Articles**
2. Click **"Create"**
3. Fill in:
   - **Title**: Article title
   - **Category**: Select from dropdown
   - **Parent Article**: Optional, link to parent article
   - **Responsible**: User responsible for article
   - **Content**: Rich HTML content
4. Click **"Save"**

### Hierarchical Structure

- Create parent articles first
- Then create child articles and link via "Parent Article" field
- View child articles in the "Children" tab of parent article

### Categories

- **SOP / Workflow**: Standard operating procedures
- **Product Knowledge**: Product information
- **System / Tools Manual**: System documentation
- **Policy / HR**: Policies and HR information
- **Other**: Miscellaneous articles

## Security

- **Internal Users** (`base.group_user`): Read, Write, Create (no delete)
- **System Admins** (`base.group_system`): Full access

## License

LGPL-3

## Author

On This Day

