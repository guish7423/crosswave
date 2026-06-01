#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# CrossWave DB Backup Automation
# Backs up all production SQLite databases with timestamp rotation.
#
# Usage:
#   bash scripts/backup-db.sh                  # One-shot backup
#   bash scripts/backup-db.sh --cron           # Cron mode (log to file)
#   bash scripts/backup-db.sh --list           # List all backups
#   bash scripts/backup-db.sh --restore <file> # Restore from backup
#
# Config file: $REPO_ROOT/.backup-config (auto-generated if missing)
# Cron: 0 3 * * * /path/to/backup-db.sh --cron
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$REPO_ROOT/.backup-config"
BACKUP_DIR=""       # set by load_config
RETENTION_DAYS=""   # set by load_config
TIMESTAMP=$(date +%Y-%m-%d-%H%M%S)
LOG_FILE="$REPO_ROOT/backup.log"

# === Color output ===
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn()  { echo -e "${YELLOW}[!]${NC} $*"; }
err()   { echo -e "${RED}[✗]${NC} $*" >&2; }

# === Default DBs (relative to workspace root) ===
WORKSPACE_ROOT="$HOME/.opencode-workspace"
DEFAULT_DBS=(
  "$WORKSPACE_ROOT/projects/polsia-fork/polsia.db"
  "$WORKSPACE_ROOT/projects/ai-blog-engine/blog.db"
  "$WORKSPACE_ROOT/projects/ai-content-bridge/content_bridge.db"
)

# =============================================================================
# Config Management
# =============================================================================
load_config() {
  if [ ! -f "$CONFIG_FILE" ]; then
    cat > "$CONFIG_FILE" <<CONF
# CrossWave Backup Configuration
# Generated: $(date -I)

# Backup directory (absolute path)
BACKUP_DIR=$REPO_ROOT/backups

# Retention period in days
RETENTION_DAYS=7

# Additional DB paths (one per line, absolute paths)
# EXTRA_DBS=(
#   /path/to/extra.db
# )
CONF
    echo "    Created config: $CONFIG_FILE" >&2
    echo "    Edit it to customize backup location or retention." >&2
  fi

  # shellcheck source=/dev/null
  source "$CONFIG_FILE"

  BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups}"
  RETENTION_DAYS="${RETENTION_DAYS:-7}"
  mkdir -p "$BACKUP_DIR"

  # Read extra DBs from config if defined via sourcing pattern
  EXTRA_DBS=()
  if grep -q "^EXTRA_DBS=" "$CONFIG_FILE" 2>/dev/null; then
    eval "$(grep "^EXTRA_DBS=" "$CONFIG_FILE")" 2>/dev/null || true
  fi
}

# =============================================================================
# Core Backup Logic
# =============================================================================
backup_db() {
  local db_path="$1"
  if [ ! -f "$db_path" ]; then
    warn "DB not found: $db_path (skipping)"
    return 0
  fi

  local db_name
  db_name=$(basename "$(dirname "$db_path")")_$(basename "$db_path" .db)
  local backup_file="$BACKUP_DIR/${db_name}-${TIMESTAMP}.db"
  local backup_size

  # Use sqlite3 backup if available (safe for live DB), else cp
  if command -v sqlite3 &>/dev/null; then
    sqlite3 "$db_path" ".backup '$backup_file'" 2>/dev/null || cp "$db_path" "$backup_file"
  else
    cp "$db_path" "$backup_file"
  fi

  backup_size=$(stat -c%s "$backup_file" 2>/dev/null || stat -f%z "$backup_file" 2>/dev/null || echo "?")
  local size_hr
  if [ "$backup_size" != "?" ]; then
    size_hr=$(numfmt --to=iec "$backup_size" 2>/dev/null || echo "${backup_size}B")
  else
    size_hr="?B"
  fi

  info "Backed up: $(basename "$db_path") → $backup_file (${size_hr})"
}

# =============================================================================
# Rotation (delete backups older than RETENTION_DAYS)
# =============================================================================
rotate_backups() {
  local count
  count=$(find "$BACKUP_DIR" -name "*.db" -type f -mtime "+$RETENTION_DAYS" 2>/dev/null | wc -l)
  if [ "$count" -gt 0 ]; then
    find "$BACKUP_DIR" -name "*.db" -type f -mtime "+$RETENTION_DAYS" -delete
    info "Rotated $count backup(s) older than $RETENTION_DAYS days"
  else
    info "No backups older than $RETENTION_DAYS days to rotate"
  fi
}

# =============================================================================
# List Backups
# =============================================================================
list_backups() {
  if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -A "$BACKUP_DIR"/*.db 2>/dev/null)" ]; then
    echo "No backups found in: $BACKUP_DIR"
    exit 0
  fi

  echo ""
  echo "=== Backups ($BACKUP_DIR) ==="
  echo ""

  # Group by DB name
  for f in "$BACKUP_DIR"/*.db; do
    [ -f "$f" ] || continue
    local name size date
    name=$(basename "$f")
    size=$(stat -c%s "$f" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "?")
    date=$(stat -c%y "$f" 2>/dev/null | cut -d. -f1 || echo "?")
    printf "  %-60s %8s  %s\n" "$name" "$size" "$date"
  done | sort

  echo ""
  local total total_hr
  total=$(find "$BACKUP_DIR" -name "*.db" -type f -exec stat -c%s {} + 2>/dev/null | paste -sd+ | bc 2>/dev/null || echo 0)
  total_hr=$(numfmt --to=iec "$total" 2>/dev/null || echo "${total}B")
  echo "  Total: $(find "$BACKUP_DIR" -name '*.db' -type f | wc -l) files, ${total_hr}"
  echo ""
}

# =============================================================================
# Restore
# =============================================================================
restore_backup() {
  local backup_file="$1"
  if [ ! -f "$backup_file" ]; then
    err "Backup file not found: $backup_file"
    exit 1
  fi

  # Infer original DB name from backup filename
  local base_name
  base_name=$(basename "$backup_file" .db)
  # Remove timestamp suffix: name-YYYY-MM-DD-HHMMSS → name
  local db_key="${base_name%-[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]}"

  # Find matching DB in DEFAULT_DBS + EXTRA_DBS
  local target_db=""
  local all_dbs=("${DEFAULT_DBS[@]}" "${EXTRA_DBS[@]}")
  for db in "${all_dbs[@]}"; do
    local match_name
    match_name=$(basename "$(dirname "$db")")_$(basename "$db" .db)
    if [ "$match_name" = "$db_key" ]; then
      target_db="$db"
      break
    fi
  done

  if [ -z "$target_db" ]; then
    warn "Could not auto-detect target DB for '$db_key'"
    echo "    Available DBs:"
    for db in "${all_dbs[@]}"; do
      echo "      - $db"
    done
    read -rp "    Enter target path manually: " target_db
  fi

  if [ ! -f "$target_db" ]; then
    warn "Target DB does not exist (will be created): $target_db"
  fi

  # Ask for confirmation
  local backup_size file_date
  backup_size=$(stat -c%s "$backup_file" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "?")
  file_date=$(stat -c%y "$backup_file" 2>/dev/null | cut -d. -f1 || echo "?")
  echo ""
  echo "  Restore: $backup_file (${backup_size}, ${file_date})"
  echo "  Target:  $target_db"
  echo ""
  read -rp "  Confirm restore? This OVERWRITES the current database. (y/N): " confirm
  if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    info "Restore cancelled"
    exit 0
  fi

  cp "$backup_file" "$target_db"
  info "Restored: $backup_file → $target_db"
}

# =============================================================================
# Main
# =============================================================================
main() {
  load_config

  case "${1:-}" in
    --cron)
      echo "[$(date -Iseconds)] Backup started" >> "$LOG_FILE"
      for db in "${DEFAULT_DBS[@]}"; do backup_db "$db"; done
      for db in "${EXTRA_DBS[@]}"; do backup_db "$db"; done
      rotate_backups
      echo "[$(date -Iseconds)] Backup completed" >> "$LOG_FILE"
      ;;
    --list)
      list_backups
      ;;
    --restore)
      if [ -z "${2:-}" ]; then err "Usage: backup-db.sh --restore <backup_file>"; exit 1; fi
      restore_backup "$2"
      ;;
    "")
      echo "=== CrossWave DB Backup ==="
      echo "  Timestamp: $TIMESTAMP"
      echo "  Backup dir: $BACKUP_DIR"
      echo "  Retention: $RETENTION_DAYS days"
      echo ""
      for db in "${DEFAULT_DBS[@]}"; do backup_db "$db"; done
      for db in "${EXTRA_DBS[@]}"; do backup_db "$db"; done
      rotate_backups
      echo ""
      info "Backup complete. Use --list to see all backups."
      ;;
    *)
      echo "Usage: backup-db.sh [--cron | --list | --restore <file>]"
      exit 1
      ;;
  esac
}

main "$@"
