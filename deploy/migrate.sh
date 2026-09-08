#!/usr/bin/env bash
# Apply migrations and seed the catalogue against a deployed database.
#
#   DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/forexmatch' ./deploy/migrate.sh
#
# Run this as a deliberate step before or after a deploy — never on container
# start, so that scaling to several instances cannot race on the schema.
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is not set." >&2
  exit 1
fi

cd "$(dirname "$0")/../backend"

echo "==> Applying migrations"
alembic upgrade head

echo "==> Seeding the card catalogue"
python scripts/seed_cards.py

echo "==> Done"
