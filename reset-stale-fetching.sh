#!/usr/bin/env bash
set -euo pipefail

cd /opt/onionlens

docker compose exec -T db sh -lc 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "
UPDATE crawl_frontier
SET status = '\''retry'\'',
    last_error = '\''reset stale fetching by maintenance job'\'',
    next_attempt_at = NOW(),
    updated_at = NOW()
WHERE status = '\''fetching'\''
  AND updated_at < NOW() - INTERVAL '\''45 minutes'\'';
"'
