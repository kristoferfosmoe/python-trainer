#!/bin/sh
# Back up the database to S3. Runs nightly from cron on the server (the AWS
# stack sets that up), and before every deploy:
#   15 3 * * * /opt/python-trainer/deploy/backup.sh >> /var/log/python-trainer-backup.log 2>&1
# Needs the AWS CLI and an instance role that may write to the bucket
# (see docs/DEPLOY.md). Keeps 14 days of local copies too.
set -eu
# cron and Systems Manager start with a short PATH; the AWS CLI is a snap.
PATH="$PATH:/usr/local/bin:/snap/bin"

cd "$(dirname "$0")"
# shellcheck source=/dev/null
. ./.env

STAMP=$(date -u +%Y-%m-%dT%H%M%SZ)
LOCAL_DIR=/var/backups/python-trainer
# deploy.sh sets BACKUP_LABEL (e.g. before-<commit>) for its backups.
FILE="$LOCAL_DIR/trainer-$STAMP${BACKUP_LABEL:+-$BACKUP_LABEL}.sql.gz"
mkdir -p "$LOCAL_DIR"

docker compose -f docker-compose.yml exec -T db \
    pg_dump --clean --if-exists -U "${POSTGRES_USER:-trainer}" "${POSTGRES_DB:-trainer}" | gzip > "$FILE"

if [ -n "${BACKUP_S3_URI:-}" ]; then
    aws s3 cp --only-show-errors "$FILE" "$BACKUP_S3_URI/"
fi

find "$LOCAL_DIR" -name 'trainer-*.sql.gz' -mtime +14 -delete
echo "$(date -u) backed up to $FILE"
