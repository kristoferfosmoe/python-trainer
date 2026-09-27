#!/bin/sh
# Start Django: update the database, load the lessons from content/, serve.
set -e

python manage.py migrate --noinput

if [ "${IMPORT_CONTENT_ON_START:-true}" = "true" ]; then
    # Checks every lesson first; if any lesson has a problem, nothing is
    # imported and the site keeps serving the lessons it already had.
    python manage.py import_content || echo "WARNING: lessons were not updated (see the problems above)."
fi

exec gunicorn trainer.wsgi \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 120 \
    --access-logfile - \
    --forwarded-allow-ips "*"
