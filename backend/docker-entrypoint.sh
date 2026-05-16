#!/bin/sh
set -e

echo "Waiting for database..."
until python -c "
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings
engine = create_engine(str(settings.DATABASE_URL), pool_pre_ping=True)
with engine.connect() as conn:
    conn.execute(text('SELECT 1'))
" 2>/dev/null; do
  sleep 2
done

echo "Initializing database schema..."
python -c "from app.core.database import init_db; init_db()"

echo "Starting API server..."
exec "$@"
