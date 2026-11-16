#!/usr/bin/env bash
# MUST HealthConnect - one-time setup on macOS / Linux:  bash setup.sh
set -e
cd "$(dirname "$0")"
[ -x mustvenv/bin/python ] || python3 -m venv mustvenv
./mustvenv/bin/python -m pip install --upgrade pip --quiet
./mustvenv/bin/python -m pip install -r requirements.txt
if [ ! -f .env ]; then
  key=$(./mustvenv/bin/python -c "import secrets; print(secrets.token_urlsafe(50))")
  sed "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$key|" .env.example > .env
  echo "Created .env with a new secret key."
fi
cat <<'EOF'

Setup done. Next steps:
  1. psql -U postgres -h localhost -f docs/setup.sql   (only once)
  2. source mustvenv/bin/activate
  3. python manage.py migrate
  4. python manage.py seed_demo
  5. python manage.py createsuperuser
  6. python manage.py runserver
EOF
