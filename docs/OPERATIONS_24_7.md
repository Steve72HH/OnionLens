# OnionLens 24/7 operation notes

OnionLens can run as a continuous crawler/indexer stack. Public defaults are intentionally small:

```text
MAX_SITES=1000
MAX_DEPTH=2
INDEX_BATCH_SIZE=3000
INDEX_INTERVAL_SECONDS=30
```

## Start the larger local run

```powershell
docker compose up -d --scale crawler=4 indexer backend frontend
```

The crawler service is horizontally scalable. PostgreSQL frontier locking uses `FOR UPDATE SKIP LOCKED`, so workers take different queued URLs.

## Watch progress

```powershell
docker compose logs --tail 120 crawler
docker compose logs --tail 120 indexer
```

Open:

```text
http://localhost:8000/stats
http://localhost:3000
```

## Repair stored encoding glitches

If pages show mojibake such as `lÃ­nea`, `Î...`, or `Ù¾...`, run:

```powershell
docker compose --profile tools run --rm tools
docker compose restart indexer
```

The repair marks changed rows for re-indexing.

## Scaling guidance

- Start with 4 crawler workers on Docker Desktop.
- Move to 8 only after the queue is stable and Tor timeouts are acceptable.
- Increase `MAX_SITES`, `MAX_DEPTH`, and `MAX_QUEUED_PER_HOST` gradually.
- If Meilisearch lags, increase CPU/RAM before increasing crawler count.
- Add seed files gradually under `seed_sources/`.
- Keep binary downloads disabled and keep response size limits active.

## Production gaps before public launch

- Admin authentication
- Protected stats endpoint with `STATS_API_KEY`
- Abuse/takedown workflow
- Legal review for Germany/EU operation
- Per-host rate limiting
- Better language detection
- Quarantine workflow for high-risk labels
- Onion service publishing with persistent hidden-service keys
