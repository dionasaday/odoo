# Odoo Custom Addons

This repository contains custom Odoo addons/modules for On This Day company.

## Modules

### knowledge_onthisday_oca
Knowledge base module with custom document view, tags/labels system, and category-based organization.

**Features:**
- Custom document view with sidebar navigation
- Tags/Labels system with color index support (0-11)
- Category-based article organization
- Integration with company CI colors
- Tag filtering and search functionality
- Parent-child article relationships

**Version:** 19.0.1.0.0

## Git Repository Setup

This repository is initialized and ready for version control.

### Initial Setup
```bash
cd /opt/odoo/custom_addons
git status
git log --oneline
```

### Adding Remote Repository

To connect to a remote repository (GitHub, GitLab, etc.):

```bash
# Add remote repository
git remote add origin <your-repository-url>

# Push to remote
git push -u origin main
```

### Common Git Commands

```bash
# Check status
git status

# View commit history
git log --oneline --graph

# Create a new branch for feature development
git checkout -b feature/your-feature-name

# Commit changes
git add .
git commit -m "Your commit message"

# Push changes
git push origin main
```

## Directory Structure

```
custom_addons/
├── .gitignore
├── README.md
└── knowledge_onthisday_oca/
    ├── __init__.py
    ├── __manifest__.py
    ├── controllers/
    ├── data/
    ├── models/
    ├── security/
    ├── static/
    ├── views/
    └── ...
```

## Notes

- All Python cache files (`__pycache__/`) are ignored
- Log files and temporary files are excluded from version control
- See `.gitignore` for complete list of ignored files

## License

Proprietary - On This Day Company

