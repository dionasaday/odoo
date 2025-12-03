# Environment Analysis

## โครงสร้าง Environment

### 1. Addons Path
- **Host Path**: `./addons/` (relative to project root `/Users/nattaphonsupa/odoo19`)
- **Container Path**: `/mnt/extra-addons` (mapped from `./addons`)
- **Recommended Location for New Module**: `./addons/knowledge_onthisday_oca/`

### 2. Odoo Configuration
- **Config File**: `./config/odoo.conf`
- **Addons Path in Config**: `/mnt/extra-addons,/mnt/enterprise-addons,/usr/lib/python3/dist-packages/odoo/addons`
- ✅ โมดูลใหม่จะถูกโหลดอัตโนมัติจาก `/mnt/extra-addons`

### 3. Docker Setup
- **Compose File**: `docker-compose.yml`
- **Container Name**: `odoo19-odoo-1`
- **Database**: PostgreSQL in `odoo19-db-1`
- **Database Name**: `odoo19` (default, configurable)

### 4. Commands to Manage Odoo

#### Start/Restart Odoo
```bash
# Start (if stopped)
docker compose up -d

# Restart
docker compose restart odoo

# View logs
docker compose logs odoo --tail 100 -f
```

#### Update Apps List (inside Odoo)
1. Open: http://localhost:8069
2. Go to: **Settings > Apps**
3. Click: **"Update Apps List"**

#### Install/Upgrade Module via Command Line
```bash
# Upgrade specific module
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d odoo19 -u knowledge_onthisday_oca --stop-after-init

# Or use odoo shell
docker compose exec odoo odoo shell -d odoo19 --no-http
```

### 5. Module Installation Workflow

1. **Place Module**: Put module in `./addons/knowledge_onthisday_oca/`
2. **Restart Odoo**: `docker compose restart odoo`
3. **Update Apps List**: Via web interface (Settings > Apps > Update Apps List)
4. **Install Module**: Via web interface (Apps > Find "Knowledge Base OCA" > Install)

### 6. Recommended Structure for New Module

```
knowledge_onthisday_oca/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── knowledge_article.py
├── views/
│   └── knowledge_article_views.xml
├── security/
│   └── ir.model.access.csv
├── data/
│   └── knowledge_menus.xml
└── static/
    └── description/
        └── icon.png (optional)
```

## Next Steps

1. ✅ Environment analyzed
2. ⏳ Create module structure
3. ⏳ Implement models following OCA patterns
4. ⏳ Create views (list, form, kanban, search)
5. ⏳ Set up security
6. ⏳ Create menus and actions
7. ⏳ Test installation
8. ⏳ Create INSTALLATION.md

