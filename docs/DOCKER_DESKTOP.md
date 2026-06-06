# Docker Desktop test run

OnionLens V0.1 is designed to run as a local Docker Desktop stack.

## Services

- `onionlens-tor`: Tor SOCKS proxy for crawler traffic
- `onionlens-db`: PostgreSQL crawl state and sanitized page records
- `onionlens-search`: Meilisearch keyword index
- `onionlens-backend`: FastAPI search and stats API
- `crawler`: horizontally scalable HTML-only onion crawler
- `onionlens-indexer`: PostgreSQL to Meilisearch sync
- `onionlens-frontend`: Web search UI

## Start

```powershell
cp .env.example .env
docker compose up --build
```

For the larger 24/7 crawl target, run multiple crawler workers:

```powershell
docker compose up -d --scale crawler=4
```

Open:

- Frontend: <http://localhost:3000>
- API health: <http://localhost:8000/health>
- Meilisearch: <http://localhost:7700>

## Seeds

Add manually reviewed initial onion URLs to:

```text
crawler/seeds.txt
```

For staged expansion, add curated seed files to:

```text
seed_sources/
```

Seed files are mounted into the crawler containers, so changing them only requires restarting the crawler workers:

```powershell
docker compose up -d --scale crawler=4
```

The crawler discovers additional `.onion` links from crawled pages up to `MAX_DEPTH`. Public defaults are intentionally small:

```text
MAX_DEPTH=2
MAX_SITES=1000
INDEX_BATCH_SIZE=3000
INDEX_INTERVAL_SECONDS=30
```

For a larger private test crawl, adjust this in `.env`:

```text
MAX_DEPTH=4
MAX_SITES=10000
```

The crawler pauses once the database contains that many stored pages.

## Onion Service Publishing

Publishing OnionLens itself as an onion service should be configured after the local stack is stable, with a separate Tor service and persistent hidden-service directory.
