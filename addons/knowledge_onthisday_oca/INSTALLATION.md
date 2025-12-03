# Installation Guide: Knowledge Base OCA

## Overview

This module provides a simple Knowledge Base system for Odoo 19 Community Edition, based on OCA (Odoo Community Association) patterns.

**Module Name**: `knowledge_onthisday_oca`  
**Version**: 19.0.1.0.0  
**License**: LGPL-3  
**Compatibility**: Odoo 19 Community Edition (no Enterprise dependencies)

## Prerequisites

- Odoo 19 Community Edition installed and running
- Docker Compose setup (or direct Odoo installation)
- Database: `odoo19` (default, configurable)

## Environment Setup

### Current Configuration

Based on your environment analysis:

- **Addons Path** (Container): `/mnt/extra-addons`
- **Addons Path** (Host): `./addons/`
- **Config File**: `./config/odoo.conf`
- **Module Location**: `./addons/knowledge_onthisday_oca/`

The module is already placed in the correct location and will be automatically loaded by Odoo.

## Installation Steps

### Step 1: Verify Module Location

The module should be located at:
```
/Users/nattaphonsupa/odoo19/addons/knowledge_onthisday_oca/
```

Verify the structure:
```bash
cd /Users/nattaphonsupa/odoo19
ls -la addons/knowledge_onthisday_oca/
```

You should see:
- `__init__.py`
- `__manifest__.py`
- `models/`
- `views/`
- `security/`
- `data/`

### Step 2: Restart Odoo (if needed)

If Odoo is already running, restart it to load the new module:

```bash
cd /Users/nattaphonsupa/odoo19
docker compose restart odoo
```

Or if starting for the first time:

```bash
docker compose up -d
```

### Step 3: Update Apps List

1. Open Odoo: http://localhost:8069
2. Login with your credentials
3. Go to **Settings** (click the gear icon)
4. Click **"Update Apps List"** button
5. Wait for the update to complete (this may take a minute)

**Important**: This step is required for Odoo to recognize the new module.

### Step 4: Install the Module

1. Go to **Apps** menu
2. Remove the "Apps" filter (click "Clear Filters" or search for "Knowledge")
3. Search for: **"Knowledge Base OCA"** or **"knowledge_onthisday_oca"**
4. Click the **"Install"** button
5. Wait for installation to complete

### Step 5: Verify Installation

After installation, verify:

1. **Check Module State**:
   - Go to **Settings > Apps**
   - Search for "Knowledge Base OCA"
   - Status should be: **"Installed"** ✅

2. **Check Menu**:
   - Look for **"Knowledge"** menu in the main menu bar
   - Should have submenus:
     - **All Articles**
     - **My Articles**

3. **Test Functionality**:
   - Go to **Knowledge > All Articles**
   - Click **"Create"**
   - Fill in:
     - Title: "Test Article"
     - Category: "SOP / Workflow"
     - Content: "This is a test article"
   - Click **"Save"**
   - Article should be created successfully ✅

## Troubleshooting

### Problem: Module not found in Apps

**Solution**:
1. Verify module is in correct location: `./addons/knowledge_onthisday_oca/`
2. Check `__manifest__.py` exists and is valid
3. Restart Odoo: `docker compose restart odoo`
4. Update Apps List again
5. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)

### Problem: Installation fails with "Field does not exist" error

**Solution**:
1. Verify all fields in views exist in `models/knowledge_article.py`
2. Check `__manifest__.py` data files are listed correctly
3. Check logs: `docker compose logs odoo --tail 100`

### Problem: Menu not showing after installation

**Solution**:
1. Clear browser cache (Ctrl+Shift+R / Cmd+Shift+R)
2. Logout and login again
3. Check user has "Internal User" group: **Settings > Users & Companies > Users**
4. Verify menu exists: **Settings > Technical > User Interface > Menu Items**
   - Search for "Knowledge"

### Problem: "ModuleNotFoundError" or import errors

**Solution**:
1. Verify `__init__.py` files exist in module root and `models/` folder
2. Check Python syntax: `python3 -m py_compile addons/knowledge_onthisday_oca/models/*.py`
3. Restart Odoo

## Manual Installation (Command Line)

If you prefer command line installation:

```bash
# Option 1: Using odoo shell
docker compose exec odoo odoo shell -d odoo19 --no-http << 'EOF'
env['ir.module.module'].update_list()
module = env['ir.module.module'].search([('name', '=', 'knowledge_onthisday_oca')], limit=1)
if module:
    if module.state == 'uninstalled':
        module.button_immediate_install()
        print(f"✅ Module installed: {module.name}")
    else:
        print(f"Module state: {module.state}")
else:
    print("❌ Module not found")
EOF

# Option 2: Using upgrade command (requires Odoo to be stopped first)
docker compose stop odoo
docker compose exec -T odoo odoo -c /etc/odoo/odoo.conf -d odoo19 -i knowledge_onthisday_oca --stop-after-init
docker compose start odoo
```

## Upgrade Module

To upgrade the module after making changes:

1. **Via Web Interface**:
   - Go to **Settings > Apps**
   - Search for "Knowledge Base OCA"
   - Click **"Upgrade"**

2. **Via Command Line**:
   ```bash
   docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d odoo19 -u knowledge_onthisday_oca --stop-after-init
   ```

## Module Structure

```
knowledge_onthisday_oca/
├── __init__.py                      # Module initialization
├── __manifest__.py                  # Module metadata
├── models/
│   ├── __init__.py                  # Models initialization
│   └── knowledge_article.py         # Knowledge Article model
├── views/
│   └── knowledge_article_views.xml  # List, Form, Kanban, Search views
├── security/
│   └── ir.model.access.csv          # Access rights
└── data/
    └── knowledge_menus.xml          # Menu definitions
```

## Features

### Models

- **knowledge.article**: Main model for knowledge articles
  - Hierarchical structure (parent/child)
  - Category-based organization
  - User-based responsibility
  - Mail thread integration

### Views

- **List View**: Shows name, category, responsible, write_date
- **Form View**: Full article editing with Content and Children pages
- **Kanban View**: Grouped by category
- **Search View**: Search by name, category, responsible, parent with filters and group by

### Menus

- **Knowledge > All Articles**: View all articles
- **Knowledge > My Articles**: View articles where you are responsible

### Security

- **Internal Users** (base.group_user): Read, Write, Create (no delete)
- **System Admins** (base.group_system): Full access

## Development

### Making Changes

1. Make your code changes
2. Restart Odoo: `docker compose restart odoo`
3. Upgrade module: **Settings > Apps > Upgrade**
4. Clear browser cache

### Adding New Fields

1. Add field to `models/knowledge_article.py`
2. Add field to views in `views/knowledge_article_views.xml`
3. Upgrade module

### Testing

After installation, test:
1. ✅ Create article
2. ✅ Edit article
3. ✅ Create child article
4. ✅ Search and filter
5. ✅ Group by category/responsible
6. ✅ Access "My Articles" menu

## Support

If you encounter issues:

1. Check logs: `docker compose logs odoo --tail 200`
2. Verify module structure matches this guide
3. Check Odoo version compatibility (requires Odoo 19)
4. Verify dependencies (`base`, `mail`) are installed

## License

LGPL-3 - See LICENSE file for details.

