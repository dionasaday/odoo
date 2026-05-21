#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/odoo/custom_addons"
REF="main"
MODULES=""
DB_NAME="odoo19"
ODOO_BIN="/opt/odoo/odoo-bin"
ODOO_CONF="/etc/odoo.conf"
ODOO_SERVICE="odoo.service"
ODOO_USER="odoo"
PSQL_USER="postgres"
DRY_RUN="false"
SKIP_RESTART="false"
SKIP_ASSET_CLEAR="false"

usage() {
  cat <<'USAGE'
Usage:
  deploy_odoo19.sh [options]

Options:
  --ref <branch|tag|commit>     Git ref to deploy (default: main)
  --modules <m1,m2,...>         Modules to upgrade (optional, auto-detect if empty)
  --db <db_name>                Odoo database name (default: odoo19)
  --repo <path>                 Repository directory (default: /opt/odoo/custom_addons)
  --odoo-bin <path>             odoo-bin path (default: /opt/odoo/odoo-bin)
  --odoo-conf <path>            Odoo config path (default: /etc/odoo.conf)
  --service <name>              systemd service name (default: odoo.service)
  --odoo-user <user>            User to run odoo-bin upgrade command (default: odoo)
  --psql-user <user>            User to run psql command (default: postgres)
  --dry-run <true|false>        Print actions without changing system
  --skip-restart <true|false>   Skip service restart
  --skip-asset-clear <true|false> Skip DELETE /web/assets/% step
  -h, --help                    Show this help
USAGE
}

log() {
  printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

run_cmd() {
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY_RUN: $*"
    return 0
  fi
  eval "$*"
}

run_odoo_upgrade() {
  local modules="$1"
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY_RUN: sudo -H -u $ODOO_USER $ODOO_BIN -c $ODOO_CONF -d $DB_NAME -u $modules --stop-after-init"
    return 0
  fi

  if [[ "$(id -u)" -eq 0 && "$ODOO_USER" != "root" ]]; then
    sudo -H -u "$ODOO_USER" "$ODOO_BIN" -c "$ODOO_CONF" -d "$DB_NAME" -u "$modules" --stop-after-init
  else
    "$ODOO_BIN" -c "$ODOO_CONF" -d "$DB_NAME" -u "$modules" --stop-after-init
  fi
}

run_asset_clear() {
  if [[ "$DRY_RUN" == "true" ]]; then
    log "DRY_RUN: sudo -H -u $PSQL_USER psql -d $DB_NAME -c DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"
    return 0
  fi

  if [[ "$(id -u)" -eq 0 && "$PSQL_USER" != "root" ]]; then
    sudo -H -u "$PSQL_USER" psql -d "$DB_NAME" -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"
  else
    psql -d "$DB_NAME" -c "DELETE FROM ir_attachment WHERE url LIKE '/web/assets/%';"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --modules) MODULES="$2"; shift 2 ;;
    --db) DB_NAME="$2"; shift 2 ;;
    --repo) REPO_DIR="$2"; shift 2 ;;
    --odoo-bin) ODOO_BIN="$2"; shift 2 ;;
    --odoo-conf) ODOO_CONF="$2"; shift 2 ;;
    --service) ODOO_SERVICE="$2"; shift 2 ;;
    --odoo-user) ODOO_USER="$2"; shift 2 ;;
    --psql-user) PSQL_USER="$2"; shift 2 ;;
    --dry-run) DRY_RUN="$2"; shift 2 ;;
    --skip-restart) SKIP_RESTART="$2"; shift 2 ;;
    --skip-asset-clear) SKIP_ASSET_CLEAR="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if ! git -C "$REPO_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not a git repository: $REPO_DIR" >&2
  exit 1
fi

if [[ ! -x "$ODOO_BIN" ]]; then
  echo "odoo-bin not found or not executable: $ODOO_BIN" >&2
  exit 1
fi

if [[ ! -f "$ODOO_CONF" ]]; then
  echo "Odoo config not found: $ODOO_CONF" >&2
  exit 1
fi

if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
  echo "Repository has uncommitted changes. Commit or stash first." >&2
  exit 1
fi

OLD_REV="$(git -C "$REPO_DIR" rev-parse HEAD)"
log "Current revision: $OLD_REV"

run_cmd "git -C \"$REPO_DIR\" fetch origin --tags"
run_cmd "git -C \"$REPO_DIR\" checkout \"$REF\""
run_cmd "git -C \"$REPO_DIR\" pull --ff-only origin \"$REF\""

NEW_REV="$(git -C "$REPO_DIR" rev-parse HEAD)"
log "Target revision: $NEW_REV"

if [[ -z "$MODULES" && "$OLD_REV" != "$NEW_REV" ]]; then
  MODULES="$(bash "$REPO_DIR/scripts/deploy/detect_changed_modules.sh" "$OLD_REV" "$NEW_REV" "$REPO_DIR" || true)"
fi

if [[ "$OLD_REV" == "$NEW_REV" && -z "$MODULES" ]]; then
  log "No code change and no explicit modules. Nothing to deploy."
  exit 0
fi

if [[ -n "$MODULES" ]]; then
  log "Upgrading modules: $MODULES"
  run_odoo_upgrade "$MODULES"
else
  log "No module upgrade required (no changed manifests detected)."
fi

if [[ "$SKIP_ASSET_CLEAR" != "true" ]]; then
  log "Clearing web assets cache from database $DB_NAME"
  run_asset_clear
else
  log "Skip assets clear by request."
fi

if [[ "$SKIP_RESTART" != "true" ]]; then
  log "Restarting service: $ODOO_SERVICE"
  run_cmd "systemctl restart \"$ODOO_SERVICE\""
  run_cmd "systemctl --no-pager --full status \"$ODOO_SERVICE\" | sed -n '1,12p'"
else
  log "Skip service restart by request."
fi

run_cmd "mkdir -p \"$REPO_DIR/.deploy\""
run_cmd "printf '%s,%s,%s,%s\\n' \"$(date -u +'%Y-%m-%dT%H:%M:%SZ')\" \"$OLD_REV\" \"$NEW_REV\" \"$MODULES\" >> \"$REPO_DIR/.deploy/releases.log\""

log "Deploy completed."
