#!/bin/sh
# Run a Django management command in the web container, for example:
#   sudo deploy/manage.sh createsuperuser
#   sudo deploy/manage.sh create_coach coach_kim --team "Brick Builders"
set -e
cd "$(dirname "$0")"
exec docker compose exec web python manage.py "$@"
