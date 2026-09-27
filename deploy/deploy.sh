#!/usr/bin/env bash
# Deploy one version of Python Trainer on this server, or go back to one.
#
#   sudo deploy/deploy.sh <version>
#
# <version> is a git commit that CI built images for:
# $IMAGE_REPO/web:<version> and $IMAGE_REPO/caddy:<version> (IMAGE_REPO is
# in deploy/.env). The CD pipeline checks out that commit and runs this over
# AWS Systems Manager. It also works by hand, e.g. to go back to an older version.
#
# 1. Back up the database.
# 2. Download the new images and restart the web app and Caddy with them.
# 3. Wait until Django answers /api/health with the new version, and Caddy answers.
# 4. If that doesn't happen in time, go back to the version that was running,
#    and fail. (Database migrations stay; this project's migrations only add.)
#
# Everything is inside main(), which bash reads in full before running it, so
# checking out older files during a rollback can't change the script mid-way.

set -euo pipefail
# Systems Manager runs commands with a short PATH and no HOME; the AWS CLI is a snap.
export PATH="$PATH:/usr/local/bin:/snap/bin" HOME=${HOME:-/root}

main() {
    local version=${1:-}
    [[ $version =~ ^[0-9a-f]{7,40}$ ]] || fail "usage: deploy.sh <git commit>"

    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    root=$(dirname "$here")
    cd "$here"
    [[ -f .env ]] || fail "deploy/.env is missing (see docs/DEPLOY.md)."
    unset IMAGE_REPO IMAGE_TAG # .env decides, not the caller's environment

    exec 9>/tmp/python-trainer-deploy.lock
    flock -w 600 9 || fail "Another deploy is still running."

    local repo previous
    repo=$(env_value IMAGE_REPO)
    [[ -n $repo ]] || fail "Set IMAGE_REPO in deploy/.env to the image registry, e.g. <account>.dkr.ecr.<region>.amazonaws.com/python-trainer."
    previous=$(env_value IMAGE_TAG)
    log "Deploying $version (running now: ${previous:-nothing})"

    registry_login "$repo"

    if [[ -n $(compose ps -q db 2>/dev/null) ]]; then
        log "Backing up the database"
        BACKUP_LABEL=before-$version ./backup.sh || fail "The backup failed, so nothing was changed."
    fi

    set_tag "$version"
    log "Downloading the images"
    if ! compose pull --quiet web caddy; then
        set_tag "$previous"
        fail "Couldn't download the images for $version. Did CI build and push them?"
    fi

    log "Starting $version"
    compose up -d --no-build --remove-orphans
    if wait_until_live "$version"; then
        record "$version" "deployed"
        tidy_images "$repo" "$version" "$previous"
        log "✔ $version is live."
        return 0
    fi

    log "✖ $version didn't come up. Its logs:"
    compose logs --tail 60 web caddy >&2 || true
    record "$version" "failed"
    if [[ -z $previous ]]; then
        fail "Nothing to go back to: this was the first deploy."
    fi
    log "Going back to $previous"
    set_tag "$previous"
    git -C "$root" checkout --quiet --force --detach "$previous" 2>/dev/null ||
        log "(Couldn't check out $previous's files; using the current ones.)"
    compose up -d --no-build --remove-orphans
    if wait_until_live "$previous"; then
        record "$previous" "rolled back to"
        fail "Deploying $version failed. $previous is running again."
    fi
    fail "Deploying $version failed, and $previous didn't come back up either. Check: docker compose logs"
}

log() { printf '%s  %s\n' "$(date -u +%H:%M:%S)" "$*"; }
fail() { log "ERROR: $*" >&2; exit 1; }
compose() { docker compose "$@"; }

# A value from .env (the last one wins, like Compose), without running the file.
env_value() { sed -n "s/^$1=//p" .env | tail -n 1 | tr -d '"'"'"; }

set_tag() {
    if grep -q '^IMAGE_TAG=' .env; then
        sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$1/" .env
    else
        printf 'IMAGE_TAG=%s\n' "$1" >> .env
    fi
}

registry_login() {
    local registry=${1%%/*}
    if [[ $registry =~ ^[0-9]+\.dkr\.ecr\.([a-z0-9-]+)\.amazonaws\.com$ ]]; then
        # The server's IAM role lets it pull from Amazon ECR.
        aws ecr get-login-password --region "${BASH_REMATCH[1]}" |
            docker login --username AWS --password-stdin "$registry" > /dev/null
    fi
}

# Django reports the version it runs, and Caddy answers on port 80.
wait_until_live() {
    local version=$1 running http
    local deadline=$((SECONDS + ${DEPLOY_TIMEOUT:-300}))
    while ((SECONDS < deadline)); do
        running=$(compose exec -T web python -c "
import json, urllib.request
print(json.load(urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4))['version'])
" 2> /dev/null || true)
        http=$(curl -s -o /dev/null -w '%{http_code}' --max-time 4 "http://127.0.0.1:$(env_value HTTP_PORT | grep . || echo 80)/" || true)
        if [[ $running == "$version" && $http =~ ^[23] ]]; then
            return 0
        fi
        sleep 3
    done
    return 1
}

record() {
    local line
    line="$(date -u +%Y-%m-%dT%H:%M:%SZ) $2 $1"
    { echo "$line" >> /var/log/python-trainer-deploys.log; } 2> /dev/null || true
}

# Keep the images for this version and the one before; delete older ones.
tidy_images() {
    local repo=$1 keep=$2 before=${3:-none}
    docker image ls --format '{{.Repository}}:{{.Tag}}' |
        grep -E "^${repo//./\\.}/(web|caddy):" |
        grep -v -e ":$keep\$" -e ":$before\$" |
        xargs -r docker image rm > /dev/null 2>&1 || true
    docker image prune -f > /dev/null || true
}

main "$@"
