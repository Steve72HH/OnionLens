# OnionLens

![OnionLens GitHub thumbnail](docs/assets/onionlens-github-thumbnail.png)

OnionLens is a controlled Tor/onion search prototype. It crawls reviewed onion seed URLs through Tor, extracts text-only metadata, stores searchable summaries, and indexes documents in Meilisearch.

The project is intentionally built with operational guardrails:

- HTML/text-only crawling
- no image, archive, executable, document, or media downloads
- configurable response size, timeout, depth, queue, and crawl-delay limits
- warning labels for sensitive content categories
- auditable crawl frontier and page status tables
- separate crawler, indexer, API, search, database, Tor, and frontend services

## Stack

- Tor SOCKS proxy
- PostgreSQL for crawl state and sanitized page records
- Meilisearch for keyword search
- FastAPI backend
- Node/Express frontend

## Quick Start

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Change at least `POSTGRES_PASSWORD`, `MEILI_MASTER_KEY`, and `USER_AGENT` in `.env`.

3. Add manually reviewed onion seed URLs to `crawler/seeds.txt` or files in `seed_sources/`.

4. Start the local stack:

```bash
docker compose up --build
```

Open:

- Frontend: <http://localhost:3000>
- Backend API health: <http://localhost:8000/health>
- Backend stats: <http://localhost:8000/stats>

By default PostgreSQL, Meilisearch, and the backend API bind to `127.0.0.1`. The frontend is published on port `3000`.

## Safety Model

OnionLens does not download binary content. The crawler only accepts `text/html`, `text/plain`, and XHTML responses under the configured size limit. Raw HTML is not stored; only sanitized text metadata, extracted keywords, warning labels, and crawl state are persisted.

Public releases intentionally ship without active onion seeds. Add only reviewed seeds that you are allowed to crawl, keep an abuse contact in your user agent, and avoid broad crawl lists without legal and operational review.

For production in Germany/EU, add legal review, abuse handling, deletion workflows, stronger content policy rules, admin authentication, monitoring, and documented reporting procedures before running broad crawls.

## Development Checks

```bash
cp .env.example .env
docker compose --env-file .env.example config
python -m compileall backend crawler indexer tools
cd frontend && npm ci
```

The GitHub workflow in `.github/workflows/ci.yml` runs the non-runtime checks used for merge validation.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Docker Desktop](docs/DOCKER_DESKTOP.md)
- [Root server quickstart](docs/ROOT_SERVER_QUICKSTART.md)
- [Operations](docs/OPERATIONS_24_7.md)
- [Seed expansion](docs/SEED_EXPANSION.md)
- [Swarm deployment](docs/SWARM_DEPLOYMENT.md)
- [Public release checklist](docs/PUBLIC_RELEASE_CHECKLIST.md)

## License

MIT. See [LICENSE](LICENSE).
