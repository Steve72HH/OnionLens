# Seed expansion plan

OnionLens should grow through staged, traceable seed sets instead of large unverified dumps.

## Current stage

Public releases ship with empty seed files. This avoids prescribing crawl targets and keeps the repository suitable for review and reuse.

For a private deployment, start with a small set of official public-interest onion services that you have manually reviewed from their clearnet source pages.

## Growth path to 100,000+ known URLs

1. Start with `MAX_SITES=1000` and `MAX_DEPTH=2`.
2. Add new seed files in `seed_sources/` by category:
   - `20_news_verified.txt`
   - `30_research_security.txt`
   - `40_software_docs.txt`
   - `50_user_reviewed_directories.txt`
   - `20_topic_discovery.txt` for search-query based discovery pages
3. Only add seeds that are manually reviewed or come from an official clearnet source.
4. Avoid raw hidden-service dump lists. They create noisy results and high legal-review load.
5. Watch `/stats` and crawler logs as each category is added.

## Topic discovery

Topic discovery pages can quickly expand the crawl graph. Add them only after manual review, keep the topic list narrow, and document why each discovery source is appropriate for your deployment.

## Useful commands

```powershell
docker compose up -d crawler indexer
docker compose logs --tail 120 crawler
```

Open stats:

```text
http://localhost:8000/stats
```

Open the search UI:

```text
http://localhost:3000
```

For a larger private crawl target, run:

```powershell
docker compose up -d --scale crawler=4 indexer backend frontend
```

Start with 2-4 crawler workers on Docker Desktop. Increase slowly while watching Tor timeouts, database CPU, memory, and Meilisearch indexing lag.
