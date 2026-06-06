# Root server quickstart

## 1. Upload and unpack

Clone or upload the OnionLens package to your root server and enter the project directory:

```bash
git clone https://github.com/<owner>/onionlens.git
cd onionlens
```

## 2. Configure secrets

```bash
cp .env.example .env
nano .env
```

Change at least:

```text
POSTGRES_PASSWORD=
MEILI_MASTER_KEY=
USER_AGENT=
PUBLIC_BACKEND_URL=
BACKEND_CORS_ORIGINS=
STATS_API_KEY=
```

Do not expose PostgreSQL, Meilisearch, or Tor publicly. The default Compose file binds PostgreSQL, Meilisearch, and the backend API to `127.0.0.1`.

## 3. Start on one dedicated server

```bash
docker compose up -d --build --scale crawler=4 crawler indexer backend frontend
```

Check:

```bash
docker compose ps
docker compose logs --tail 120 crawler
docker compose logs --tail 120 indexer
```

Open:

```text
http://SERVER-IP:3000
```

Check stats on the server or through your protected reverse proxy:

```bash
curl http://127.0.0.1:8000/stats
```

## 4. Recommended reverse proxy

Expose only:

- frontend on HTTPS
- backend API on HTTPS, ideally behind `/api`, rate-limited, and with `STATS_API_KEY` set

Keep these internal:

- PostgreSQL
- Meilisearch
- Tor proxy

## 5. Swarm later

See:

```text
docs/SWARM_DEPLOYMENT.md
deploy/swarm-stack.yml
```

Start with the dedicated-server deployment first. Move to Swarm after storage, backups, crawl rate, and legal processes are clear.
