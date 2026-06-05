#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════
# CrossWave PostgreSQL 自动备份
# 用法: bash scripts/backup-db.sh [output_dir]
# 默认备份到 backups/ 目录
# 保留最近 7 天备份, 自动清理旧文件
# ═══════════════════════════════════════════════════════
set -euo pipefail

OUTPUT_DIR="${1:-backups}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="${OUTPUT_DIR}/nocobase_${TIMESTAMP}.sql.gz"
LATEST_LINK="${OUTPUT_DIR}/nocobase_latest.sql.gz"

echo "── CrossWave PostgreSQL Backup ──"
echo "Output: $BACKUP_FILE"

# Dump NocoBase database (running container)
docker exec hq-postgres-1 pg_dump -U nocobase --clean --if-exists | gzip > "$BACKUP_FILE"

# Update latest link
ln -sf "$(basename "$BACKUP_FILE")" "$LATEST_LINK"

# Show result
SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "Done: $SIZE — $(date '+%Y-%m-%d %H:%M:%S')"

# Clean up backups older than 7 days
find "$OUTPUT_DIR" -name "nocobase_*.sql.gz" -mtime +7 -delete 2>/dev/null || true
echo "Cleaned: backups older than 7 days"

TABLE_COUNT=$(zcat "$BACKUP_FILE" 2>/dev/null | grep -c "CREATE TABLE" || echo "?")
echo "Tables exported: $TABLE_COUNT"
echo ""
