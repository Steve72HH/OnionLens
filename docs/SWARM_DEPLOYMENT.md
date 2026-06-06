# OnionLens on Docker Swarm

## Recommended rollout path

Start on one dedicated server first, then move into the Swarm once the data volume, crawl rate, and legal/process requirements are stable.

## Architecture

Stateless or near-stateless services can be replicated:

- `frontend`: 3 replicas
- `backend`: 3 replicas
- `crawler`: 4-10 replicas depending on Tor/database load

Stateful services should not be blindly replicated:

- `db`: PostgreSQL starts as 1 primary service with a persistent volume
- `meilisearch`: starts as 1 persistent search node
- `indexer`: starts as 1 worker to avoid duplicate indexing pressure

The crawler is safe to scale because `crawl_frontier` uses row locking with `FOR UPDATE SKIP LOCKED`.

## Dedicated server first

On the dedicated server:

```bash
git clone https://github.com/<owner>/onionlens.git
cd onionlens
cp .env.example .env
docker compose up -d --scale crawler=4 crawler indexer backend frontend
```

For a public reverse proxy, expose only:

- frontend, usually behind HTTPS
- backend API, ideally under `/api` and rate-limited
- set `STATS_API_KEY` before routing `/stats`

Do not expose PostgreSQL, Meilisearch, or Tor publicly.

## Swarm preparation

Label the node that should hold persistent state:

```bash
docker node update --label-add onionlens.stateful=true <node-name>
```

Build and push images:

```bash
docker build -t registry.example.com/onionlens/backend:0.1.0 backend
docker build -t registry.example.com/onionlens/crawler:0.1.0 crawler
docker build -t registry.example.com/onionlens/indexer:0.1.0 indexer
docker build -t registry.example.com/onionlens/frontend:0.1.0 frontend

docker push registry.example.com/onionlens/backend:0.1.0
docker push registry.example.com/onionlens/crawler:0.1.0
docker push registry.example.com/onionlens/indexer:0.1.0
docker push registry.example.com/onionlens/frontend:0.1.0
```

Deploy:

```bash
cd deploy
cp .env.swarm.example .env.swarm
set -a
. ./.env.swarm
set +a
docker stack deploy -c swarm-stack.yml onionlens
```

## Scaling commands

```bash
docker service scale onionlens_crawler=8
docker service scale onionlens_backend=5
docker service scale onionlens_frontend=5
```

Scale crawlers gradually. Watch PostgreSQL, Tor timeouts, Meilisearch indexing lag, and disk usage.

## Toward true high availability

The first Swarm stack is redundant for stateless services, not fully HA for state.

For real HA:

- PostgreSQL: use a managed PostgreSQL service or Patroni/CloudNativePG outside plain Compose semantics
- Search: evaluate OpenSearch for shard/replica support once Meilisearch becomes the bottleneck
- Indexing: keep one indexer per target search cluster, or introduce partitioned indexing jobs
- Seeds/configs: manage via Swarm configs or a GitOps deploy flow
- Backups: schedule PostgreSQL dumps plus volume snapshots

## Distributed load model

Good first distribution:

- Many crawler replicas across Swarm workers
- One shared PostgreSQL frontier
- One indexer consuming changed rows
- One search index serving all frontend/backend replicas

Later distribution:

- shard frontier by onion host hash
- separate crawler pools per shard
- switch from Meilisearch to OpenSearch for distributed indexing
- add a queue such as Redis Streams or RabbitMQ if DB polling becomes too heavy

## Security checklist

- Use strong secrets, not `.env` defaults
- Put frontend/backend behind TLS reverse proxy
- Restrict backend admin endpoints before adding them
- Keep PostgreSQL and Meilisearch private
- Add abuse/takedown process before public launch
- Add legal review for Germany/EU operation
