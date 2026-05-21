#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/odoo/custom_addons"
TARGET_REF=""
DB_NAME="odoo19"
ODOO_BIN="/opt/odoo/odoo-bin"
ODOO_CONF="/etc/odoo.conf"
ODOO_SERVICE="odoo.service"
ODOO_USER="odoo"
PSQL_USER="postgres"
MODULES=""
DRY_RUN="false"

usage() {
  cat <<'USAGE'
Usage:
  rollback_odoo19.sh --to <tag|commit> [options]

Options:
  --to <tag|commit>             Target revision to rollback to (required)
  --modules <m1,m2,...>         Modules to force-upgrade after rollback
  --db <db_name>                Odoo database name (default: odoo19)
  --repo <path>                 Repository directory (default: /opt/odoo/custom_addons)
  --odoo-bin <path>             odoo-bin path (default: /opt/odoo/odoo-bin)
  --odoo-conf <path>            Odoo config path (default: /etc/odoo.conf)
  --service <name>              systemd service name (default: odoo.service)
  --odoo-user <user>            User to run odoo-bin upgrade command (default: odoo)
  --psql-user <user>            User to run psql command (default: postgres)
  --dry-run <true|false>        Print actions without changing system
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
    --to) TARGET_REF="$2"; shift 2 ;;
    --modules) MODULES="$2"; shift 2 ;;
    --db) DB_NAME="$2"; shift 2 ;;
    --repo) REPO_DIR="$2"; shift 2 ;;
    --odoo-bin) ODOO_BIN="$2"; shift 2 ;;
    --odoo-conf) ODOO_CONF="$2"; shift 2 ;;
    --service) ODOO_SERVICE="$2"; shift 2 ;;
    --odoo-user) ODOO_USER="$2"; shift 2 ;;
    --psql-user) PSQL_USER="$2"; shift 2 ;;
    --dry-run) DRY_RUN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$TARGET_REF" ]]; then
  echo "--to is required." >&2
  usage
  exit 1
fi

if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
  echo "Repository has uncommitted changes. Commit or stash first." >&2
  exit 1
fi

run_cmd "git -C \"$REPO_DIR\" fetch origin --tags"
run_cmd "git -C \"$REPO_DIR\" checkout \"$TARGET_REF\""

if [[ -n "$MODULES" ]]; then
  run_odoo_upgrade "$MODULES"
fi

run_asset_clear
run_cmd "systemctl restart \"$ODOO_SERVICE\""
run_cmd "systemctl --no-pager --full status \"$ODOO_SERVICE\" | sed -n '1,12p'"

log "Rollback completed to: $TARGET_REF"
