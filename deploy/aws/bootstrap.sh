#!/usr/bin/env bash
# First boot of the Python Trainer server, run as root by the AWS stack's
# user data (deploy/aws/python-trainer.yml). Safe to run again:
#   sudo /opt/python-trainer/deploy/aws/bootstrap.sh
#
# Reads /etc/python-trainer.env (written by the user data): DOMAIN (empty
# for plain HTTP on the server's IP), IMAGE_REPO, BACKUP_S3_URI, REPO_URL, BRANCH.
#
# Installs Docker, the AWS CLI and a swap file, writes deploy/.env with new
# random secrets (they never leave this server), and schedules nightly
# backups. It doesn't start the site: the first deploy from GitHub does.

set -euxo pipefail

# shellcheck source=/dev/null
. /etc/python-trainer.env
: "${DOMAIN:=}" "${IMAGE_REPO:?}" "${REPO_URL:?}" "${BRANCH:=main}" "${BACKUP_S3_URI:=}"
APP=/opt/python-trainer
export DEBIAN_FRONTEND=noninteractive

# The Elastic IP is attached while this runs, which can cut downloads off.
retry() {
    local n
    for n in 1 2 3 4 5 6; do
        "$@" && return 0
        echo "Retrying in $((n * 10)) s: $*"
        sleep $((n * 10))
    done
    return 1
}

# --- Packages -----------------------------------------------------------------------
# Ubuntu's own Docker packages get security updates from unattended-upgrades.
retry apt-get update -q
retry apt-get install -y -q docker.io docker-compose-v2 git curl openssl unattended-upgrades
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{"log-driver": "json-file", "log-opts": {"max-size": "20m", "max-file": "5"}}
EOF
systemctl enable docker
systemctl restart docker
command -v aws > /dev/null || [ -x /snap/bin/aws ] || retry snap install aws-cli --classic
# On every PATH (cron, Systems Manager and Session Manager shells included).
[ -e /usr/local/bin/aws ] || ln -s /snap/bin/aws /usr/local/bin/aws

# Some headroom for small servers (Postgres, Django and Caddy share 1-2 GB).
if ! swapon --show | grep -q /swapfile; then
    [ -f /swapfile ] || { fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile; }
    swapon /swapfile
    grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# --- The deploy files (each deploy checks out its own commit) -------------------------
[ -d "$APP/.git" ] || retry git clone --branch "$BRANCH" "$REPO_URL" "$APP"

# --- Settings, with secrets made here -------------------------------------------------------
if [ ! -f "$APP/deploy/.env" ]; then
    umask 077
    cat > "$APP/deploy/.env" <<EOF
# Made by deploy/aws/bootstrap.sh. The secrets were generated on this server.
# The address settings (DOMAIN and friends) come from deploy/set-address.sh.
DJANGO_SECRET_KEY=$(openssl rand -hex 32)
POSTGRES_DB=trainer
POSTGRES_USER=trainer
POSTGRES_PASSWORD=$(openssl rand -hex 24)
GUNICORN_WORKERS=3
IMPORT_CONTENT_ON_START=true
BACKUP_S3_URI=$BACKUP_S3_URI
# Where CI puts the images, and the version running now (deploy.sh sets it).
IMAGE_REPO=$IMAGE_REPO
IMAGE_TAG=
EOF
    umask 022
    "$APP/deploy/set-address.sh" "$DOMAIN"
fi

# --- Nightly backups to S3 at 03:15 UTC ---------------------------------------------------
mkdir -p /var/backups/python-trainer
cat > /etc/cron.d/python-trainer-backup <<EOF
15 3 * * * root $APP/deploy/backup.sh >> /var/log/python-trainer-backup.log 2>&1
EOF

mkdir -p /var/lib/python-trainer
date -u > /var/lib/python-trainer/bootstrapped
echo "Python Trainer server is ready for its first deploy."
