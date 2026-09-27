#!/bin/sh
# Back up the database to S3. Run nightly from cron on the EC2 host:
#   15 3 * * * /home/ubuntu/python-trainer/deploy/backup.sh >> /var/log/trainer-backup.log 2>&1
# Needs the AWS CLI and an instance role that may write to the bucket
# (see docs/DEPLOY.md). Keeps 14 days of local copies too.
set -eu

cd "$(dirname "$0")"
. ./.env

STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
LOCAL_DIR=/var/backups/python-trainer
FILE="$LOCAL_DIR/trainer-$STAMP.sql.gz"
mkdir -p "$LOCAL_DIR"

docker compose -f docker-compose.yml exec -T db \
    pg_dump --clean --if-exists -U "${POSTGRES_USER:-trainer}" "${POSTGRES_DB:-trainer}" | gzip > "$FILE"

if [ -n "${BACKUP_S3_URI:-}" ]; then
    aws s3 cp --only-show-errors "$FILE" "$BACKUP_S3_URI/"
fi

find "$LOCAL_DIR" -name 'trainer-*.sql.gz' -mtime +14 -delete
echo "$(date -u) backed up to $FILE"
