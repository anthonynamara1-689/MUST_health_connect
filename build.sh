#!/usr/bin/env bash
# Render runs this on every deploy. Stops at the first error.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input
python manage.py grant_report_access

if [ "${HC_SEED_DEMO:-True}" = "True" ]; then
  python manage.py seed_demo
fi

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ]; then
  python manage.py createsuperuser --no-input 2>/dev/null || echo "Admin user already exists."
fi