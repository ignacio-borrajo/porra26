#!/usr/bin/env bash
set -euo pipefail
set -a; [ -f ~/apuestas-interna/.env ] && . ~/apuestas-interna/.env; set +a
mkdir -p ~/backups
DATE=$(date +%F)
mysqldump -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -h "$MYSQL_HOST" "$MYSQL_NAME" | gzip > ~/backups/porra26-$DATE.sql.gz
find ~/backups -name "porra26-*.sql.gz" -mtime +30 -delete
echo "Backup OK · porra26-$DATE.sql.gz"
