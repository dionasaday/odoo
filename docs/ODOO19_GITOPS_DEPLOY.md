# Odoo 19 GitOps Deployment (Local -> Git -> Production)

This setup replaces direct production editing with a Git-based flow:

1. Develop on local machine (Mac)
2. Push to GitHub
3. GitHub Actions deploys to production over SSH
4. Server pulls code, upgrades changed modules, clears assets, and restarts Odoo

## 1) Branching Strategy

- `main`: production-ready only
- `staging`: optional pre-production validation
- `feature/*`: development branches

Recommended workflow:

1. Create feature branch from `main`
2. Open Pull Request
3. CI checks pass
4. Merge PR into `main`
5. Auto deploy to production (or manual dispatch)

## 2) Required GitHub Secrets

Set these in repository settings:

- `PROD_HOST`: production server host/IP
- `PROD_USER`: SSH user for deploy
- `PROD_SSH_KEY`: private SSH key (PEM/OpenSSH)
- `PROD_PORT`: SSH port (usually `22`)

## 3) Production Server Prerequisites

Ensure production server has:

- Git repository at `/opt/odoo/custom_addons`
- Deploy scripts available under `scripts/deploy/`
- `odoo-bin` at `/opt/odoo/odoo-bin`
- Odoo config at `/etc/odoo.conf`
- PostgreSQL CLI (`psql`)
- `systemctl` access for `odoo.service`

## 4) Auto Deploy Behavior

Workflow file:

- `.github/workflows/deploy-production.yml`

Triggers:

- Push to `main`
- Manual `workflow_dispatch`

Main deploy script:

- `scripts/deploy/deploy_odoo19.sh`

What the deploy script does:

1. Fetch + checkout target ref
2. Pull latest with `--ff-only`
3. Detect changed modules from git diff
4. Run module upgrade (`-u module1,module2`)
5. Clear `/web/assets/%` cache rows
6. Restart `odoo.service`
7. Append release log to `.deploy/releases.log`

## 5) Manual Deploy (Server-Side)

```bash
cd /opt/odoo/custom_addons
chmod +x scripts/deploy/*.sh
scripts/deploy/deploy_odoo19.sh --ref main
```

Deploy specific modules:

```bash
scripts/deploy/deploy_odoo19.sh --ref main --modules onthisday_hr_discipline,knowledge_onthisday_oca
```

Dry run:

```bash
scripts/deploy/deploy_odoo19.sh --ref main --dry-run true
```

## 6) Rollback

Rollback script:

- `scripts/deploy/rollback_odoo19.sh`

Example:

```bash
cd /opt/odoo/custom_addons
scripts/deploy/rollback_odoo19.sh --to <tag-or-commit> --modules onthisday_hr_discipline
```

## 7) Operational Recommendations

- Tag each production release:
  - `git tag prod-YYYYMMDD-HHMM`
  - `git push origin --tags`
- Keep DB backup before major release
- Use manual deploy (`workflow_dispatch`) for high-risk schema changes
- Use staging branch and staging DB for integration tests

## 8) Suggested Next Hardening Steps

1. Add automatic pre-deploy DB backup script
2. Add health check endpoint verification after restart
3. Add Slack/LINE notify on deploy success/failure
4. Add protected environment approval in GitHub Actions
