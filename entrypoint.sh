#!/bin/sh
# Apply database migrations, then start the app. Runs on every deploy.
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --timeout 120
